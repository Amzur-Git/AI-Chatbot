"""
Ticket Automation Service
Integrates with n8n workflow for AI-powered ticket metadata extraction
"""
import logging
from typing import Optional, Dict, Any
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class TicketValidator:
    """Validates ticket data at multiple layers"""
    
    VALID_CATEGORIES = {
        'bug', 'feature', 'support', 'documentation', 'infrastructure',
        'performance', 'security', 'ui', 'backend', 'api', 'database'
    }
    
    VALID_PRIORITIES = {'low', 'medium', 'high', 'critical'}
    
    @staticmethod
    def validate_issue(issue: str) -> bool:
        """Validate issue text (10-5000 characters)"""
        if not issue or not isinstance(issue, str):
            raise ValueError("Issue must be a non-empty string")
        
        if len(issue) < 10:
            raise ValueError("Issue must be at least 10 characters")
        
        if len(issue) > 5000:
            raise ValueError("Issue must not exceed 5000 characters")
        
        return True
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        if not email or '@' not in email:
            raise ValueError("Invalid email format")
        return True
    
    @staticmethod
    def validate_extracted_ticket(data: Dict[str, Any]) -> bool:
        """Validate extracted ticket data from n8n"""
        required_fields = ['category', 'priority', 'assigned_team']
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        if data.get('category') not in TicketValidator.VALID_CATEGORIES:
            logger.warning(f"Invalid category: {data.get('category')}")
        
        if data.get('priority') not in TicketValidator.VALID_PRIORITIES:
            logger.warning(f"Invalid priority: {data.get('priority')}")
        
        return True


class TicketAutomationService:
    """Handles secure n8n webhook integration for ticket automation"""
    
    def __init__(self):
        """Initialize service with n8n configuration from environment"""
        self.n8n_webhook_url = settings.n8n_webhook_url or 'http://localhost:5678/webhook/ticket-automation'
        self.n8n_webhook_secret = settings.n8n_webhook_secret or ''
        
        if not self.n8n_webhook_secret:
            logger.warning("N8N_WEBHOOK_SECRET not set - webhook validation will fail")
    
    async def create_ticket_via_n8n(
        self,
        user_email: str,
        user_name: str,
        user_id: Optional[int],
        issue_description: str,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create ticket via n8n workflow.
        
        Sends issue to n8n which:
        - Validates webhook secret
        - Extracts metadata using AI
        - Stores in PostgreSQL
        - Sends email confirmation
        - Returns response
        
        Args:
            user_email: User's email address
            user_name: User's name
            user_id: User's internal ID
            issue_description: Natural language issue description
            request_id: Optional request tracking ID
        
        Returns:
            Dictionary with ticket_id, category, priority, assigned_team, etc.
        
        Raises:
            ValueError: If validation fails
            httpx.RequestError: If n8n request fails
            httpx.TimeoutException: If n8n request times out
        """
        
        # Validate inputs
        TicketValidator.validate_issue(issue_description)
        TicketValidator.validate_email(user_email)
        
        # Build secure payload
        payload = {
            'action': 'create',
            'event_type': 'ticket_created',
            'request_id': request_id,
            'user_email': user_email,
            'user_name': user_name,
            'user_id': user_id,
            'issue': issue_description,
            'message': issue_description,
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Secret': self.n8n_webhook_secret
        }
        
        logger.info(f"Calling n8n webhook for ticket: {request_id}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.n8n_webhook_url,
                    json=payload,
                    headers=headers
                )
            
            if response.status_code != 200:
                logger.error(f"n8n returned {response.status_code}: {response.text}")
                raise ValueError(f"n8n workflow failed with status {response.status_code}")
            
            # Some n8n flows return empty body on success — treat as {}
            try:
                result = response.json() if response.text.strip() else {}
            except Exception:
                result = {}
            logger.info(f"n8n response received: {result.get('ticket_id')}")
            return result
            
        except httpx.TimeoutException as e:
            logger.error(f"n8n request timeout: {e}")
            raise ValueError("Request to n8n workflow timed out")
        
        except httpx.RequestError as e:
            logger.error(f"n8n request failed: {e}")
            raise ValueError(f"Failed to connect to n8n workflow: {str(e)}")
    
    @staticmethod
    async def parse_n8n_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and normalize n8n workflow response.
        
        Args:
            response: Raw response from n8n webhook
        
        Returns:
            Normalized dictionary with ticket metadata
        
        Raises:
            ValueError: If response format is invalid
        """
        
        if not isinstance(response, dict):
            raise ValueError("Invalid n8n response format")
        
        # Validate response has required fields
        required_fields = ['ticket_id', 'category', 'priority', 'assigned_team']
        missing_fields = [f for f in required_fields if f not in response]
        
        if missing_fields:
            raise ValueError(f"Missing fields in n8n response: {missing_fields}")
        
        # Normalize values
        normalized = {
            'ticket_id': str(response.get('ticket_id', '')).strip(),
            'category': str(response.get('category', 'support')).lower().strip(),
            'priority': str(response.get('priority', 'medium')).lower().strip(),
            'assigned_team': str(response.get('assigned_team', 'support')).strip(),
            'summary': str(response.get('summary', '')).strip(),
            'response': str(response.get('response', '')).strip(),
            'execution_id': str(response.get('execution_id', '')).strip(),
        }
        
        # Validate normalized data
        TicketValidator.validate_extracted_ticket(normalized)
        
        logger.info(f"Parsed n8n response: ticket_id={normalized['ticket_id']}")
        return normalized
