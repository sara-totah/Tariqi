from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from uuid import UUID, uuid4

# Based on Telegram Bot API structure for incoming updates/messages
# We only define fields we strictly need for now

class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: Optional[str] = None
    username: Optional[str] = None

class TelegramChat(BaseModel):
    id: int
    type: str # e.g., "private"
    first_name: Optional[str] = None
    username: Optional[str] = None

class TelegramMessage(BaseModel):
    message_id: int
    from_user: TelegramUser = Field(..., alias='from') # 'from' is a reserved keyword
    chat: TelegramChat
    date: datetime # Unix timestamp converted to datetime by Pydantic
    text: Optional[str] = None
    # Add other fields if needed (e.g., location, photo)

    # Pydantic V2+ configuration using model_config
    model_config = {
        "populate_by_name": True, # Allows using 'from' alias for validation
        "extra": "ignore" # Ignore extra fields not defined in the model
    }

class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[TelegramMessage] = None 
    # Add other update types if needed (edited_message, channel_post, etc.)

# Example of how you might define a schema for saving data
# (Not strictly needed for validation but useful conceptually)
class UserReportCreate(BaseModel):
    user_id: int
    message_id: int
    text: Optional[str]
    raw_payload: dict # Store the full validated update payload
    timestamp: datetime

# Schema for output of Stage 3 (Entity Extraction & Classification)
class LocationInfo(BaseModel):
    text: str # The text identified as a location
    # Potential future fields: latitude, longitude, confidence_score

class TimeInfo(BaseModel):
    text: str # The text identified as time/date
    # Potential future fields: normalized_datetime, confidence_score

class ExtractedReportInfo(BaseModel):
    """Schema for storing extracted information and classification results."""
    original_text: str
    is_relevant: bool = False
    locations: List[LocationInfo] = []
    times: List[TimeInfo] = []
    event_type: Optional[str] = None # E.g., "accident", "traffic", "blockade", "other"
    # Fields added for verification pipeline
    original_report_id: Optional[UUID] = None # Link back to RawGroupMessage or RawUserReport ID
    report_timestamp: Optional[datetime] = None # Timestamp from the original report
    # Could add raw NER tags if needed for debugging
    # raw_entities: List[Tuple[str, str]] = [] 

# Schema for output of Stage 4 (Validation & Deduplication)
class VerifiedIncident(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    representative_text: str # e.g., text from the first report in the group
    location: Optional[LocationInfo] = None # e.g., most common location in the group
    time: Optional[TimeInfo] = None # e.g., earliest time in the group
    event_type: Optional[str] = None # e.g., most common event type in the group
    contributing_report_count: int
    # Optional: Add IDs of raw reports if needed for tracing
    # contributing_raw_report_ids: List[UUID] = [] 
    first_report_at: Optional[datetime] = None
    last_report_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
