from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Enum, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class TicketStatus(str, enum.Enum):
    """Ticket status enum."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, enum.Enum):
    """Ticket priority enum."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    google_id = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chat_messages = relationship("ChatMessage", back_populates="user")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    thread_id = Column(Integer, nullable=True, index=True)  # Thread/conversation ID
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to user
    user = relationship("User", back_populates="chat_messages")


class Ticket(Base):
    """Ticket model for workflow automation."""
    __tablename__ = "tickets"

    ticket_id = Column(BigInteger, primary_key=True, index=True)
    user_email = Column(Text, nullable=False, index=True)
    issue = Column(Text, nullable=False)  # Original issue description
    category = Column(String, nullable=False)  # Extracted category (Bug, Feature, Support, etc)
    priority = Column(String, nullable=False)  # Extracted priority (Low, Medium, High, Critical)
    assigned_team = Column(String, nullable=True)  # Extracted assigned team
    status = Column(String, default=TicketStatus.OPEN.value)  # Status: open, in_progress, resolved, closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Tickets are associated by user_email to match the existing Supabase schema.