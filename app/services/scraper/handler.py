import logging
import json
from datetime import datetime
import time # Import time for FloodWaitError sleep
import os # Import os

from telethon.sync import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, ChannelPrivateError, 
    ChatAdminRequiredError, RPCError
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError, TimeoutError as DBTimeoutError

from app.db import get_db
from app.models import RawGroupMessage
from app.settings import settings
from app.services.scraper.client import get_telethon_client

# Configure logging level (e.g., from env var or setting)
# Use DEBUG for more verbose output during development/debugging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants --- 
# Limit message fetching for testing/local runs. Set to None for production Lambda.
LOCAL_RUN_MESSAGE_LIMIT = 100 
DB_SAVE_RETRIES = 3
DB_SAVE_RETRY_DELAY = 2 # seconds
# -----------------

def save_message(msg_data: dict) -> bool:
    """Saves a single message dictionary to the database, with retries.

    Returns:
        bool: True if saved successfully, False otherwise.
    """
    last_exception = None
    for attempt in range(DB_SAVE_RETRIES):
        db: Session | None = None # Initialize db to None
        try:
            db = next(get_db()) # Get a session for this attempt
            
            # Check if message already exists by message_id
            exists = db.query(RawGroupMessage).filter(RawGroupMessage.message_id == msg_data['message_id']).first()
            if exists:
                logger.debug(f"Message ID {msg_data['message_id']} already exists. Skipping.")
                return False # Indicate skipped, not an error

            # Create new RawGroupMessage object
            db_message = RawGroupMessage(
                source_group_id=msg_data['source_group_id'],
                message_id=msg_data['message_id'],
                reply_to_message_id=msg_data.get('reply_to_message_id'),
                text=msg_data.get('text'),
                raw_payload=msg_data.get('raw_payload'),
                timestamp=msg_data['timestamp']
            )
            
            db.add(db_message)
            db.commit()
            logger.info(f"Saved message ID {db_message.message_id} from group {db_message.source_group_id}")
            return True # Success!
            
        except IntegrityError as e:
            # Duplicate key error - likely already exists (race condition), not a real error
            db.rollback()
            logger.warning(f"IntegrityError saving message ID {msg_data['message_id']} on attempt {attempt + 1}: {e}. Likely race condition.")
            return False # Treat as skipped
            
        except (OperationalError, DBTimeoutError) as e:
            # Database connection/timeout errors - worth retrying
            db.rollback()
            logger.warning(f"Database error saving message ID {msg_data['message_id']} on attempt {attempt + 1}: {e}")
            last_exception = e
            if attempt < DB_SAVE_RETRIES - 1:
                logger.info(f"Retrying DB save in {DB_SAVE_RETRY_DELAY} seconds...")
                time.sleep(DB_SAVE_RETRY_DELAY)
            else:
                logger.error(f"Failed to save message ID {msg_data['message_id']} after {DB_SAVE_RETRIES} attempts due to DB error: {e}", exc_info=True)
                return False # Failed after retries
                
        except Exception as e:
            # Any other exception during DB operation - log and treat as failed save
            db.rollback()
            logger.error(f"Unexpected error saving message ID {msg_data['message_id']} on attempt {attempt + 1}: {e}", exc_info=True)
            last_exception = e
            return False # Failed
        finally:
            # Ensure session is closed after each attempt
            if db:
                db.close()

    # Should only be reached if all retries failed due to OperationalError/Timeout
    logger.error(f"Save failed permanently for message ID {msg_data['message_id']}. Last error: {last_exception}")
    return False

def fetch_and_save_messages(limit: int | None = LOCAL_RUN_MESSAGE_LIMIT):
    """Connects to Telegram, fetches messages, handles errors & retries for saves."""
    logger.info("Starting message fetch process...")
    
    client = get_telethon_client()
    total_saved_count = 0
    total_processed_count = 0
    
    try:
        logger.info("Connecting to Telegram...")
        client.connect()
        if not client.is_user_authorized():
            logger.error("Telegram client not authorized. Please run client.py or handle authorization.")
            # Attempt interactive authorization (will require user input)
            try:
                client.send_code_request(settings.telegram_phone_number) # Assumes phone number in settings
                client.sign_in(settings.telegram_phone_number, input('Enter the code: '))
            except SessionPasswordNeededError:
                 client.sign_in(password=input('Password: ')) # Assumes password input
            except Exception as auth_err:
                 logger.error(f"Failed to authorize interactively: {auth_err}")
                 return # Cannot proceed without authorization
            logger.info("Client authorized successfully.")
            
        me = client.get_me()
        logger.info(f"Connected as: {me.first_name} (@{me.username})")

        for group_id in settings.telegram_group_ids:
            logger.info(f"Fetching messages from group ID: {group_id} (Limit: {limit})")
            processed_in_group = 0
            saved_in_group = 0
            try:
                # Use get_entity to check group validity early
                try:
                    entity = client.get_entity(group_id)
                    logger.debug(f"Successfully resolved group ID {group_id} to entity: {entity.title}")
                except ValueError as e:
                     logger.error(f"Invalid group ID format or cannot find entity for {group_id}: {e}")
                     continue # Skip this group ID
                except (ChatAdminRequiredError, ChannelPrivateError) as e:
                     logger.error(f"Permissions error for group {group_id}: {e}")
                     continue # Skip this group ID
                except Exception as e: # Catch other potential get_entity errors
                     logger.error(f"Error resolving group entity {group_id}: {e}", exc_info=True)
                     continue # Skip this group
                     
                for message in client.iter_messages(entity, limit=limit): # Iterate using resolved entity
                    total_processed_count += 1
                    processed_in_group += 1
                    try: # Add try/except around JSON conversion
                        msg_data = {
                            'source_group_id': message.chat_id,
                            'message_id': message.id,
                            'reply_to_message_id': message.reply_to_msg_id,
                            'text': message.text,
                            'timestamp': message.date,
                            'raw_payload': json.loads(message.to_json())
                        }
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode JSON for message ID {message.id} in group {group_id}: {e}")
                        continue # Skip this message
                    except Exception as e:
                        logger.error(f"Error processing message ID {message.id} in group {group_id}: {e}", exc_info=True)
                        continue # Skip this message
                    
                    # save_message now returns True/False and handles its own retries/logging
                    if save_message(msg_data):
                       saved_in_group += 1
                       total_saved_count += 1
                    
                    # Log progress periodically
                    if processed_in_group % 100 == 0:
                         logger.info(f"Group {group_id}: Processed {processed_in_group} messages...")
                         
            except FloodWaitError as e: # Catch FloodWaitError FIRST
                 logger.warning(f"Flood wait error for group {group_id}. Waiting {e.seconds} seconds...")
                 time.sleep(e.seconds)
            except (ChannelPrivateError, ChatAdminRequiredError) as e:
                logger.error(f"Permissions error while iterating group {group_id}: {e}. Moving to next group.")
            except ConnectionError as e: 
                logger.error(f"Connection error while iterating group {group_id}: {e}. Attempting to continue.")
            except RPCError as e: # Catch other Telegram API errors AFTER specific ones
                logger.error(f"Telegram RPC error while iterating group {group_id}: {e}. Attempting to continue.")
            except Exception as e:
                 logger.error(f"Unexpected error iterating messages from group {group_id}: {e}", exc_info=True)
            
            logger.info(f"Finished group {group_id}. Processed: {processed_in_group}, Saved: {saved_in_group}")

    except ConnectionError as e:
        logger.error(f"Failed to connect to Telegram: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during the fetch process: {e}", exc_info=True)
    finally:
        if client and client.is_connected():
            logger.info("Disconnecting Telegram client.")
            client.disconnect()
            
    logger.info(f"Message fetch process completed. Total processed: {total_processed_count}, Total newly saved: {total_saved_count}")

def lambda_handler(event, context):
    """AWS Lambda entry point.

    Args:
        event: Event data (e.g., from EventBridge). Not used in this simple case.
        context: Lambda runtime information. Not used directly.

    Returns:
        A dictionary with status code and message.
    """
    logger.info("Lambda function execution started.")
    
    # Determine message limit. Could be passed via event if needed.
    # For Lambda, we might want to fetch more or all new messages.
    # Setting limit=None in iter_messages fetches all since last run (if session persists).
    # For safety, let's keep a limit, maybe higher than local.
    message_limit = int(os.getenv("LAMBDA_MESSAGE_LIMIT", "1000")) 
    
    try:
        # Use LAMBDA_MESSAGE_LIMIT from env vars, default to 1000
        fetch_and_save_messages(limit=message_limit)
        logger.info("Lambda function execution finished successfully.")
        return {
            'statusCode': 200,
            'body': json.dumps('Message fetch completed successfully!')
        }
    except Exception as e:
        # Log the exception details properly in CloudWatch
        logger.error(f"Lambda function execution failed: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error during message fetch: {e}')
        }

# Remove the __main__ block, not used by Lambda
# if __name__ == "__main__":
#     ... 