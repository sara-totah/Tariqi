import os
from telethon.sync import TelegramClient

from app.settings import settings

# Determine session path: use /tmp in Lambda, otherwise local dir
if os.getenv("AWS_LAMBDA_FUNCTION_NAME"): # Check if running in Lambda
    SESSION_PATH = os.path.join("/tmp", settings.telegram_session_name)
else:
    SESSION_PATH = settings.telegram_session_name # Local file like 'session'

def get_telethon_client() -> TelegramClient:
    """Initializes and returns a synchronous Telethon client instance.

    Uses API credentials and session name from the application settings.
    Adjusts session file path for Lambda environment.

    Returns:
        TelegramClient: An initialized Telethon client.
    """
    print(f"DEBUG: Using session path: {SESSION_PATH}.session")
    client = TelegramClient(
        session=SESSION_PATH,
        api_id=settings.telegram_api_id,
        api_hash=settings.telegram_api_hash,
    )
    return client


# Example usage (optional, for testing connection)
if __name__ == "__main__":
    print("Attempting to connect to Telegram...")
    client = get_telethon_client()
    with client:
        me = client.get_me()
        print(f"Successfully connected as: {me.first_name} {me.last_name} (@{me.username})")
        print(f"Session file: {SESSION_PATH}.session")
    print("Connection closed.") 