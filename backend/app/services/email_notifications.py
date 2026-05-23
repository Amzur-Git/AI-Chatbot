"""Email notification helpers for ticket events."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Optional, Tuple
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """Sends ticket-related emails through SMTP."""

    @staticmethod
    def is_configured() -> bool:
        """Return True when required SMTP settings are present."""
        smtp_host = settings.smtp_host
        smtp_username = settings.smtp_username
        smtp_password = settings.smtp_password
        smtp_from_email = settings.smtp_from_email or smtp_username
        return bool(smtp_host and smtp_username and smtp_password and smtp_from_email)

    @staticmethod
    async def send_ticket_closed_email(
        user_email: str,
        user_name: Optional[str],
        ticket_id: int,
        issue: Optional[str],
    ) -> Tuple[bool, str]:
        """Send a ticket closed email with SMTP, or n8n fallback when SMTP is missing."""
        smtp_host = settings.smtp_host
        smtp_username = settings.smtp_username
        smtp_password = settings.smtp_password
        smtp_from_email = settings.smtp_from_email or smtp_username

        if not EmailNotificationService.is_configured():
            logger.warning(
                "SMTP not configured; trying n8n fallback for ticket_id=%s",
                ticket_id,
            )
            return await EmailNotificationService.send_ticket_closed_via_n8n(
                user_email=user_email,
                user_name=user_name,
                ticket_id=ticket_id,
                issue=issue,
            )

        subject = "Ticket Closed Successfully"
        recipient_name = user_name or "User"
        body = (
            f"Hello {recipient_name},\n\n"
            "Your support ticket has been closed successfully.\n\n"
            f"Ticket ID: {ticket_id}\n"
            "Status: Closed\n\n"
            "Thanks,\n"
            "Support Team"
        )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = smtp_from_email
        message["To"] = user_email
        message.set_content(body)

        def _send() -> None:
            with smtplib.SMTP(smtp_host, settings.smtp_port, timeout=20) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(message)

        try:
            await asyncio.to_thread(_send)
            logger.info("Closed-ticket email sent for ticket_id=%s to=%s", ticket_id, user_email)
            return True, "Closed status saved and email sent"
        except Exception as exc:
            logger.error(
                "Failed to send closed-ticket email for ticket_id=%s: %s",
                ticket_id,
                exc,
            )
            return False, "Closed status saved, but email could not be sent"

    @staticmethod
    async def send_ticket_closed_via_n8n(
        user_email: str,
        user_name: Optional[str],
        ticket_id: int,
        issue: Optional[str],
    ) -> Tuple[bool, str]:
        """Send closed-ticket notification via a dedicated n8n webhook."""
        webhook_url = settings.n8n_closed_ticket_webhook_url
        if not webhook_url:
            logger.warning(
                "N8N_CLOSED_TICKET_WEBHOOK_URL not configured; cannot send closed-ticket email for ticket_id=%s",
                ticket_id,
            )
            return False, "Closed status saved, but email not sent: SMTP and n8n fallback are not configured"

        payload = {
            "action": "close",
            "event_type": "ticket_closed",
            "ticket_id": ticket_id,
            "user_email": user_email,
            "user_name": user_name or "User",
            "issue": issue or "",
            "status": "closed",
        }
        headers = {
            "Content-Type": "application/json",
        }
        if settings.n8n_webhook_secret:
            headers["X-Webhook-Secret"] = settings.n8n_webhook_secret

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(webhook_url, json=payload, headers=headers)

            if 200 <= response.status_code < 300:
                logger.info(
                    "Closed-ticket notification sent via n8n for ticket_id=%s to=%s",
                    ticket_id,
                    user_email,
                )
                return True, "Closed status saved and email sent"

            logger.error(
                "n8n closed-ticket webhook failed for ticket_id=%s with status=%s body=%s",
                ticket_id,
                response.status_code,
                response.text,
            )
            return False, "Closed status saved, but email could not be sent"
        except Exception as exc:
            logger.error(
                "n8n closed-ticket webhook request failed for ticket_id=%s: %s",
                ticket_id,
                exc,
            )
            return False, "Closed status saved, but email could not be sent"
