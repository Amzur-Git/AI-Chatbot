from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
	__tablename__ = "users"

	id = Column(Integer, primary_key=True, index=True)
	email = Column(String, unique=True, index=True, nullable=False)
	name = Column(String, nullable=False)
	google_id = Column(String, unique=True, nullable=False)
	is_active = Column(Boolean, default=True)
	created_at = Column(DateTime, default=datetime.utcnow)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

	chat_messages = relationship("ChatMessage", back_populates="user")
	credentials = relationship("UserCredential", back_populates="user", uselist=False)


class ChatMessage(Base):
	__tablename__ = "chat_messages"

	id = Column(Integer, primary_key=True, index=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
	role = Column(String, nullable=False)
	content = Column(Text, nullable=False)
	created_at = Column(DateTime, default=datetime.utcnow)

	user = relationship("User", back_populates="chat_messages")


class UserCredential(Base):
	__tablename__ = "user_credentials"

	id = Column(Integer, primary_key=True, index=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
	password_hash = Column(String, nullable=False)
	created_at = Column(DateTime, default=datetime.utcnow)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

	user = relationship("User", back_populates="credentials")
