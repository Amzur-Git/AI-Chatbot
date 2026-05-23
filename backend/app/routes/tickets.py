"""
Ticket Management API Routes
Handles ticket creation, retrieval, and management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
import logging

from app.database import get_db
from app.models import Ticket, User
from app.auth import get_current_user
from app.services.email_notifications import EmailNotificationService
from app.services.ticket_automation import TicketAutomationService, TicketValidator

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================================
# Pydantic Schemas (Request/Response Models)
# ============================================================================

class TicketCreateRequest(BaseModel):
    """Request model for creating a ticket"""
    user_email: Optional[EmailStr] = Field(default=None, description="Requester email")
    issue: Optional[str] = Field(default=None, min_length=10, max_length=5000, description="Issue description")
    message: Optional[str] = Field(default=None, min_length=10, max_length=5000, description="Alias for issue description")
    
    class Config:
        json_schema_extra = {
            "example": {
                "action": "create",
                "user_email": "user@example.com",
                "message": "Login button not working on mobile devices"
            }
        }


class TicketResponse(BaseModel):
    """Response model for ticket creation"""
    ticket_id: int
    issue: Optional[str]
    category: Optional[str]
    priority: Optional[str]
    summary: Optional[str]
    response: Optional[str]
    assigned_team: Optional[str]
    status: str
    created_at: Optional[datetime]


class TicketListResponse(BaseModel):
    """Response model for ticket in list"""
    ticket_id: int
    issue: Optional[str]
    category: Optional[str]
    priority: Optional[str]
    summary: Optional[str]
    response: Optional[str]
    assigned_team: Optional[str]
    status: str
    created_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class TicketDetailResponse(BaseModel):
    """Response model for detailed ticket view"""
    ticket_id: int
    issue: Optional[str]
    category: Optional[str]
    priority: Optional[str]
    summary: Optional[str]
    response: Optional[str]
    assigned_team: Optional[str]
    status: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class TicketStatusUpdateRequest(BaseModel):
    """Request model for updating ticket status"""
    status: str = Field(..., description="New status: open, in_progress, resolved, closed")


class TicketStatusUpdateResponse(TicketDetailResponse):
    """Response model for ticket status updates, including email delivery state."""
    email_sent: Optional[bool] = None
    email_message: Optional[str] = None


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/tickets/create",
    response_model=TicketResponse,
    summary="Create a new ticket via AI workflow",
    description="Submit an issue that will be processed by n8n workflow for AI metadata extraction"
)
async def create_ticket(
    request: TicketCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new ticket through the AI workflow automation.
    
    The issue is sent to n8n which:
    1. Validates the secret
    2. Extracts metadata using GPT-4o
    3. Stores in PostgreSQL
    4. Sends email confirmation
    5. Returns structured response
    """
    
    issue_text = (request.issue or request.message or "").strip()
    if not issue_text:
        raise HTTPException(status_code=400, detail="Either 'issue' or 'message' is required")

    requester_email = (request.user_email or current_user.email or "").strip().lower()
    if not requester_email:
        raise HTTPException(status_code=400, detail="user_email is required")

    # Validate issue
    try:
        TicketValidator.validate_issue(issue_text)
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    # Call n8n workflow
    try:
        service = TicketAutomationService()
        n8n_response = await service.create_ticket_via_n8n(
            user_email=requester_email,
            user_name=current_user.name or "User",
            user_id=current_user.id,
            issue_description=issue_text,
            request_id=f"req-{current_user.id}"
        )
    except Exception as e:
        logger.error(f"n8n workflow failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ticket via workflow")
    
    # Validate n8n response
    try:
        parsed_response = await TicketAutomationService.parse_n8n_response(n8n_response)
    except ValueError as e:
        # Some workflows return only partial metadata. Fall back to defaults and
        # locate/insert the ticket using DB data.
        logger.warning(f"Response parsing warning, using fallback mapping: {e}")
        parsed_response = {
            "ticket_id": n8n_response.get("ticket_id"),
            "category": n8n_response.get("category") or "support",
            "priority": n8n_response.get("priority") or "medium",
            "summary": n8n_response.get("summary") or "",
            "response": n8n_response.get("response") or "",
            "assigned_team": n8n_response.get("assigned_team") or "support",
            "execution_id": n8n_response.get("execution_id"),
        }
    
    # Store in database
    try:
        ticket = None
        ticket_id_raw = parsed_response.get("ticket_id")

        if ticket_id_raw not in (None, ""):
            try:
                ticket_id = int(ticket_id_raw)
                existing_result = await db.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))
                ticket = existing_result.scalar_one_or_none()
            except (TypeError, ValueError):
                logger.warning("Non-numeric ticket_id from workflow; falling back to latest-user-ticket lookup")

        if ticket is None:
            # n8n returned no ticket_id — create a fresh record in the backend.
            generated_ticket_id = int(datetime.utcnow().timestamp() * 1000)
            ticket = Ticket(
                ticket_id=generated_ticket_id,
                user_email=requester_email,
                issue=issue_text,
                category=parsed_response.get("category"),
                priority=parsed_response.get("priority"),
                summary=parsed_response.get("summary") or "",
                response=parsed_response.get("response") or "",
                assigned_team=parsed_response.get("assigned_team"),
                status="open"
            )
            db.add(ticket)
            await db.commit()
            await db.refresh(ticket)
        else:
            # n8n inserted the row — ensure issue text and correct status are saved.
            needs_update = False
            if not ticket.issue:
                ticket.issue = issue_text
                needs_update = True
            if not ticket.user_email:
                ticket.user_email = requester_email
                needs_update = True
            if hasattr(ticket, "summary") and not getattr(ticket, "summary", None):
                ticket.summary = parsed_response.get("summary") or ""
                needs_update = True
            if hasattr(ticket, "response") and not getattr(ticket, "response", None):
                ticket.response = parsed_response.get("response") or ""
                needs_update = True
            if ticket.status and ticket.status.lower() in ("closed", "resolved"):
                ticket.status = "open"
                needs_update = True
            if needs_update:
                await db.commit()
                await db.refresh(ticket)
        
        logger.info(f"Ticket created: {ticket.ticket_id}")
        
        return TicketResponse(
            ticket_id=ticket.ticket_id,
            issue=ticket.issue,
            category=ticket.category,
            priority=ticket.priority,
            summary=getattr(ticket, "summary", None),
            response=getattr(ticket, "response", None),
            assigned_team=ticket.assigned_team,
            status=ticket.status,
            created_at=ticket.created_at,
        )
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to store ticket")


@router.get(
    "/tickets",
    response_model=List[TicketListResponse],
    summary="List user's tickets",
    description="Get all tickets created by the current user"
)
async def list_tickets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all tickets for the current user.
    Returns tickets ordered by most recent first.
    """
    try:
        result = await db.execute(
            select(Ticket)
            .where(Ticket.user_email == current_user.email)
            .order_by(desc(Ticket.created_at))
        )
        tickets = result.scalars().all()
        
        logger.info(f"Listed {len(tickets)} tickets for user {current_user.id}")
        return tickets
        
    except Exception as e:
        logger.error(f"Error listing tickets: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tickets")


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
    summary="Get ticket details",
    description="Retrieve detailed information about a specific ticket"
)
async def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific ticket.
    Only returns if the ticket belongs to the current user.
    """
    try:
        result = await db.execute(
            select(Ticket)
            .where(
                (Ticket.ticket_id == ticket_id) &
                (Ticket.user_email == current_user.email)
            )
        )
        ticket = result.scalar_one_or_none()
        
        if not ticket:
            logger.warning(f"Ticket not found: {ticket_id} for user {current_user.id}")
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        logger.info(f"Retrieved ticket: {ticket_id}")
        return ticket
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving ticket: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve ticket")


@router.patch(
    "/tickets/{ticket_id}/status",
    response_model=TicketStatusUpdateResponse,
    summary="Update ticket status",
    description="Update status for a specific ticket owned by the current user"
)
async def update_ticket_status(
    ticket_id: int,
    request: TicketStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update ticket status for the current user's ticket."""
    normalized_status = request.status.strip().lower()
    allowed_statuses = {"open", "in_progress", "resolved", "closed"}

    if normalized_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{request.status}'. Allowed values: {', '.join(sorted(allowed_statuses))}"
        )

    try:
        result = await db.execute(
            select(Ticket).where(
                (Ticket.ticket_id == ticket_id) &
                (Ticket.user_email == current_user.email)
            )
        )
        ticket = result.scalar_one_or_none()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        previous_status = (ticket.status or "").strip().lower()
        ticket.status = normalized_status
        await db.commit()
        await db.refresh(ticket)

        email_sent: Optional[bool] = None
        email_message: Optional[str] = None
        if normalized_status == "closed" and previous_status != "closed":
            email_sent, email_message = await EmailNotificationService.send_ticket_closed_email(
                user_email=current_user.email,
                user_name=current_user.name,
                ticket_id=ticket.ticket_id,
                issue=ticket.issue,
            )

        logger.info(f"Updated ticket {ticket_id} status to {normalized_status} for user {current_user.id}")
        return TicketStatusUpdateResponse(
            ticket_id=ticket.ticket_id,
            issue=ticket.issue,
            category=ticket.category,
            priority=ticket.priority,
            summary=getattr(ticket, "summary", None),
            response=getattr(ticket, "response", None),
            assigned_team=ticket.assigned_team,
            status=ticket.status,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            email_sent=email_sent,
            email_message=email_message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating ticket status: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update ticket status")


# ============================================================================
# Health Check
# ============================================================================

@router.get(
    "/tickets/health",
    summary="Health check for tickets service",
    description="Verify the tickets service is running"
)
async def tickets_health():
    """Health check endpoint for tickets service"""
    return {
        "status": "healthy",
        "service": "tickets",
        "version": "1.0.0"
    }
