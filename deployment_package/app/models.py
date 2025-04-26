import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, BigInteger, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class RawGroupMessage(Base):
    """SQLAlchemy model for raw messages scraped from Telegram groups."""
    __tablename__ = "raw_group_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_group_id = Column(BigInteger, index=True, comment="Telegram chat ID of the source group")
    message_id = Column(BigInteger, index=True, unique=True, comment="Telegram message ID")
    reply_to_message_id = Column(BigInteger, nullable=True, index=True, comment="ID of the message this one replies to")
    text = Column(Text, nullable=True, comment="Raw text content of the message")
    raw_payload = Column(JSON, nullable=True, comment="Full JSON payload of the Telegram message object")
    timestamp = Column(DateTime(timezone=True), nullable=False, comment="Timestamp when the message was sent")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Timestamp when the record was created")

    def __repr__(self):
        return f"<RawGroupMessage(id={self.id}, group={self.source_group_id}, msg={self.message_id})>"
