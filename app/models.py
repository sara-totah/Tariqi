import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, BigInteger, Text, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.sql.sqltypes import TIMESTAMP

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
    processed = Column(Boolean, default=False, index=True, comment="Flag indicating if the report has been processed by the verification pipeline")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Timestamp when the record was created")

    def __repr__(self):
        return f"<RawGroupMessage(id={self.id}, group={self.source_group_id}, msg={self.message_id})>"


class RawUserReport(Base):
    """SQLAlchemy model for raw reports submitted by users via the Telegram bot."""
    __tablename__ = "raw_user_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, index=True, nullable=False, comment="Telegram user ID of the sender")
    message_id = Column(BigInteger, index=True, nullable=False, comment="Telegram message ID of the report")
    text = Column(Text, nullable=True, comment="Raw text content of the user report")
    raw_payload = Column(JSON, nullable=True, comment="Full JSON payload of the Telegram update object")
    timestamp = Column(DateTime(timezone=True), nullable=False, comment="Timestamp when the message was sent by the user")
    processed = Column(Boolean, default=False, index=True, comment="Flag indicating if the report has been processed by the verification pipeline")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Timestamp when the record was created")

    def __repr__(self):
        return f"<RawUserReport(id={self.id}, user={self.user_id}, msg={self.message_id})>"


# Stage 5 Model
class VerifiedReport(Base):
    """SQLAlchemy model for verified and deduplicated incident reports."""
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    representative_text = Column(Text, nullable=False)
    location_text = Column(Text, nullable=True)
    time_text = Column(Text, nullable=True)
    event_type = Column(String, nullable=True)
    contributing_report_count = Column(Integer, nullable=False)
    first_report_at = Column(DateTime(timezone=True), nullable=True)
    last_report_at = Column(DateTime(timezone=True), nullable=True)
    db_created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    # Add indexes if needed for querying later
    # __table_args__ = (Index('ix_verified_report_location', 'location_text'), )

    def __repr__(self):
        return f"<VerifiedReport(id={self.id}, event={self.event_type}, loc={self.location_text})>"
