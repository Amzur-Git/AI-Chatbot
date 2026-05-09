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
	attachments = relationship("Attachment", back_populates="user")
	image_generations = relationship("ImageGeneration", back_populates="user")
	credentials = relationship("UserCredential", back_populates="user", uselist=False)


class ChatMessage(Base):
	__tablename__ = "chat_messages"

	id = Column(Integer, primary_key=True, index=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
	thread_id = Column(Integer, nullable=True, index=True)
	role = Column(String, nullable=False)
	content = Column(Text, nullable=False)
	created_at = Column(DateTime, default=datetime.utcnow)

	user = relationship("User", back_populates="chat_messages")
	attachments = relationship("Attachment", back_populates="chat_message")
	image_generations_as_request = relationship(
		"ImageGeneration",
		back_populates="requested_by_message",
		foreign_keys="ImageGeneration.requested_by_message_id",
	)
	image_generations_as_result = relationship(
		"ImageGeneration",
		back_populates="result_message",
		foreign_keys="ImageGeneration.result_message_id",
	)


class Attachment(Base):
	__tablename__ = "attachments"

	id = Column(Integer, primary_key=True, index=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
	chat_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True, index=True)
	thread_id = Column(Integer, nullable=True, index=True)
	storage_key = Column(String, unique=True, nullable=False, index=True)
	original_name = Column(String, nullable=False)
	mime_type = Column(String, nullable=False)
	category = Column(String, nullable=False)
	file_size = Column(Integer, nullable=False)
	text_content = Column(Text, nullable=True)
	created_at = Column(DateTime, default=datetime.utcnow)

	user = relationship("User", back_populates="attachments")
	chat_message = relationship("ChatMessage", back_populates="attachments")
	image_generation = relationship("ImageGeneration", back_populates="attachment", uselist=False)


class ImageGeneration(Base):
	__tablename__ = "image_generations"

	id = Column(Integer, primary_key=True, index=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
	thread_id = Column(Integer, nullable=True, index=True)
	requested_by_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True, index=True)
	result_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True, index=True)
	attachment_id = Column(Integer, ForeignKey("attachments.id"), nullable=True, index=True)
	prompt = Column(Text, nullable=False)
	status = Column(String, nullable=False, default="pending", index=True)
	error_message = Column(Text, nullable=True)
	created_at = Column(DateTime, default=datetime.utcnow)
	completed_at = Column(DateTime, nullable=True)

	user = relationship("User", back_populates="image_generations")
	requested_by_message = relationship(
		"ChatMessage",
		back_populates="image_generations_as_request",
		foreign_keys=[requested_by_message_id],
	)
	result_message = relationship(
		"ChatMessage",
		back_populates="image_generations_as_result",
		foreign_keys=[result_message_id],
	)
	attachment = relationship("Attachment", back_populates="image_generation")


class UserCredential(Base):
	__tablename__ = "user_credentials"

	id = Column(Integer, primary_key=True, index=True)
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
	password_hash = Column(String, nullable=False)
	created_at = Column(DateTime, default=datetime.utcnow)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

	user = relationship("User", back_populates="credentials")
