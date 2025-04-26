import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import List
from pydantic import field_validator, Field
import json # Import json

# Load .env file for local development, Lambda uses environment variables directly
# Put this check *before* class definition if you run locally without Lambda context
if os.getenv("AWS_LAMBDA_FUNCTION_NAME") is None:
    load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    Handles potential string inputs from Lambda env vars.
    """
    # Read as string first, validator will convert
    telegram_api_id_str: str = Field(alias="TELEGRAM_API_ID") 
    telegram_api_hash: str
    telegram_session_name: str = "session"
    # Read as string first, validator will convert
    telegram_group_ids_str: str = Field(alias="TELEGRAM_GROUP_IDS") 
    database_url: str # Mandatory, read from .env
    telegram_phone_number: str # Added for potential interactive login
    telegram_bot_token: str # Added for Telegram Bot API access
    webhook_url: str = Field(alias="WEBHOOK_URL") # URL for FastAPI webhook

    # Scheduler settings
    pipeline_run_interval_minutes: int = Field(default=5, alias="PIPELINE_RUN_INTERVAL_MINUTES")

    # Parsed values (populated by validators)
    telegram_api_id: int = 0 # Default needed temporarily
    telegram_group_ids: List[int] = [] # Default needed temporarily

    @field_validator('telegram_api_id', mode='before')
    @classmethod
    def _parse_api_id(cls, v, values):
        """Parse API ID from string."""
        api_id_str = values.data.get('telegram_api_id_str')
        if api_id_str:
            try:
                return int(api_id_str)
            except ValueError:
                raise ValueError("Invalid TELEGRAM_API_ID: Must be an integer")
        raise ValueError("Missing TELEGRAM_API_ID")

    @field_validator('telegram_group_ids', mode='before')
    @classmethod
    def _parse_group_ids(cls, v, values):
        """Parse group IDs from JSON list string OR comma-separated string."""
        group_ids_str = values.data.get('telegram_group_ids_str')
        if not group_ids_str:
             raise ValueError("Missing TELEGRAM_GROUP_IDS")
        
        try:
            # First, try parsing as JSON list (e.g., '[123, 456]')
            ids = json.loads(group_ids_str)
            if isinstance(ids, list) and all(isinstance(i, int) for i in ids):
                return ids
            else:
                 raise ValueError("Invalid JSON format for TELEGRAM_GROUP_IDS")
        except json.JSONDecodeError:
            # If JSON fails, try parsing as comma-separated string (e.g., '123,456')
            try:
                return [int(gid.strip()) for gid in group_ids_str.split(',') if gid.strip()]
            except ValueError:
                 raise ValueError("Invalid comma-separated integer format for TELEGRAM_GROUP_IDS")
        except Exception as e:
             raise ValueError(f"Error parsing TELEGRAM_GROUP_IDS: {e}")

    class Config:
        # Pydantic-settings automatically reads from os.environ if .env load fails or is skipped
        # We don't strictly need env_file specified if we rely only on Lambda env vars,
        # but keep it for local dev consistency.
        env_file = ".env"
        env_file_encoding = "utf-8"

# Instantiate settings. This will load from .env locally or Lambda env vars when deployed.
settings = Settings() 