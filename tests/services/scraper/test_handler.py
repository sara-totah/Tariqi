# Placeholder for scraper handler tests 

import pytest
from unittest.mock import MagicMock, patch, call, AsyncMock
from datetime import datetime, timezone
import json

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from telethon.sync import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, ChannelPrivateError, 
    ChatAdminRequiredError, RPCError
)

# Function to test
from app.services.scraper import handler as scraper_handler
from app.services.scraper.handler import save_message, fetch_and_save_messages, DB_SAVE_RETRIES, DB_SAVE_RETRY_DELAY
from app.models import RawGroupMessage
from app.settings import settings # Import settings

# Sample message data for testing
SAMPLE_MSG_DATA = {
    'source_group_id': -100123456,
    'message_id': 98765,
    'reply_to_message_id': None,
    'text': 'This is a test message',
    'timestamp': datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    'raw_payload': {'some': 'data'}
}

# Mock message object structure for iter_messages
@pytest.fixture
def mock_telegram_message():
    msg = MagicMock()
    msg.id = 12345
    msg.chat_id = -100999
    msg.reply_to_msg_id = None
    msg.text = "Fetched message text"
    msg.date = datetime(2024, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
    # Simulate to_json returning a valid JSON string
    msg.to_json.return_value = json.dumps({
        "id": msg.id, 
        "chat_id": msg.chat_id, 
        "text": msg.text, 
        # Add other fields needed by save_message if raw_payload is used more deeply
    })
    return msg

@pytest.fixture
def mock_db_session():
    """Provides a reusable MagicMock for the DB Session."""
    session = MagicMock(spec=Session)
    # Default: message does not exist
    session.query.return_value.filter.return_value.first.return_value = None
    return session

@pytest.fixture
def mock_save(mocker):
    """Fixture to mock the save_message function."""
    return mocker.patch('app.services.scraper.handler.save_message', return_value=True)

# --- Test Cases for save_message --- 

def test_save_message_success_new(mocker, mock_db_session):
    """Test successfully saving a new message."""
    # Mock get_db to yield the session mock
    mocker.patch('app.services.scraper.handler.get_db', return_value=iter([mock_db_session]))

    result = save_message(SAMPLE_MSG_DATA)

    assert result is True
    mock_db_session.query.return_value.filter.return_value.first.assert_called_once()
    mock_db_session.add.assert_called_once()
    # Check that the added object has the correct attributes
    added_obj = mock_db_session.add.call_args[0][0]
    assert isinstance(added_obj, RawGroupMessage)
    assert added_obj.message_id == SAMPLE_MSG_DATA['message_id']
    assert added_obj.text == SAMPLE_MSG_DATA['text']
    mock_db_session.commit.assert_called_once()
    mock_db_session.rollback.assert_not_called()
    mock_db_session.close.assert_called_once()

def test_save_message_skip_existing(mocker, mock_db_session):
    """Test skipping save if message already exists."""
    # Simulate message existing
    mock_db_session.query.return_value.filter.return_value.first.return_value = RawGroupMessage(**SAMPLE_MSG_DATA)

    mocker.patch('app.services.scraper.handler.get_db', return_value=iter([mock_db_session]))

    result = save_message(SAMPLE_MSG_DATA)

    assert result is False
    mock_db_session.query.return_value.filter.return_value.first.assert_called_once()
    # Add and commit should not be called
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()
    mock_db_session.rollback.assert_not_called()
    mock_db_session.close.assert_called_once()

def test_save_message_integrity_error(mocker, mock_db_session):
    """Test handling IntegrityError (e.g., race condition)."""
    # Simulate commit failing with IntegrityError
    mock_db_session.commit.side_effect = IntegrityError("mocked integrity error", params={}, orig=None)

    mocker.patch('app.services.scraper.handler.get_db', return_value=iter([mock_db_session]))

    result = save_message(SAMPLE_MSG_DATA)

    assert result is False
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.rollback.assert_called_once() # Should rollback on IntegrityError
    mock_db_session.close.assert_called_once()

def test_save_message_db_error_retry_success(mocker, mock_db_session):
    """Test successful save after retrying on OperationalError."""
    mock_time_sleep = mocker.patch('time.sleep') # Mock time.sleep
    # Fail first time, succeed second time
    mock_db_session.commit.side_effect = [OperationalError("mocked db error", params={}, orig=None), None]

    # Need to provide the session mock multiple times for the retry loop
    mock_get_db = mocker.patch('app.services.scraper.handler.get_db')
    mock_get_db.side_effect = [iter([mock_db_session]), iter([mock_db_session])] # Yield session on first 2 calls

    result = save_message(SAMPLE_MSG_DATA)

    assert result is True
    assert mock_db_session.commit.call_count == 2 # Called twice (fail, success)
    assert mock_db_session.rollback.call_count == 1 # Rolled back on first attempt
    assert mock_time_sleep.call_count == 1 # Slept once before retry
    assert mock_db_session.close.call_count == 2 # Closed after each attempt

def test_save_message_db_error_retry_fail(mocker, mock_db_session):
    """Test permanent failure after exhausting retries on OperationalError."""
    mock_time_sleep = mocker.patch('time.sleep')
    # Fail all attempts
    mock_db_session.commit.side_effect = OperationalError("mocked db error", params={}, orig=None)

    # Provide session for all attempts using a function side_effect
    mocker.patch('app.services.scraper.handler.get_db', side_effect=lambda: iter([mock_db_session]))

    result = save_message(SAMPLE_MSG_DATA)

    assert result is False
    assert mock_db_session.commit.call_count == DB_SAVE_RETRIES
    assert mock_db_session.rollback.call_count == DB_SAVE_RETRIES
    assert mock_time_sleep.call_count == DB_SAVE_RETRIES - 1 # Slept between retries
    assert mock_db_session.close.call_count == DB_SAVE_RETRIES

def test_save_message_other_exception(mocker, mock_db_session):
    """Test handling of other exceptions during save."""
    # Simulate a non-DB error during commit
    mock_db_session.commit.side_effect = ValueError("Something else went wrong")

    mocker.patch('app.services.scraper.handler.get_db', return_value=iter([mock_db_session]))

    result = save_message(SAMPLE_MSG_DATA)

    assert result is False
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.rollback.assert_called_once() # Should rollback
    mock_db_session.close.assert_called_once()

# --- Test Cases for fetch_and_save_messages --- 

def test_fetch_save_happy_path(mocker, mock_save, mock_telegram_message):
    """Test the normal successful flow of fetching and saving."""
    # Create mock client inside test
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.is_connected.return_value = True
    mock_client.is_user_authorized.return_value = True
    mock_client.get_me.return_value = MagicMock(first_name="Test", username="testuser")
    mock_client.get_entity.return_value = MagicMock(title="Test Group")
    mock_client.iter_messages = MagicMock(return_value=[mock_telegram_message])
    mocker.patch('app.services.scraper.handler.get_telethon_client', return_value=mock_client)
    
    mocker.patch.object(settings, 'telegram_group_ids', [-100999])
    
    scraper_handler.fetch_and_save_messages(limit=10)
    
    mock_client.connect.assert_called_once()
    mock_client.is_user_authorized.assert_called_once()
    mock_client.get_me.assert_called_once()
    mock_client.get_entity.assert_called_with(-100999)
    mock_client.iter_messages.assert_called_once()
    mock_save.assert_called_once()
    call_args = mock_save.call_args[0][0]
    assert call_args['message_id'] == mock_telegram_message.id
    assert call_args['text'] == mock_telegram_message.text
    mock_client.disconnect.assert_called_once()

def test_fetch_save_get_entity_permission_error(mocker, mock_save, mock_telegram_message):
    """Test skipping a group if get_entity raises permissions error."""
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.is_connected.return_value = True
    mock_client.is_user_authorized.return_value = True
    mock_client.get_me.return_value = MagicMock(first_name="Test", username="testuser")
    mock_client.get_entity.side_effect = [ChannelPrivateError(request=None), MagicMock(title="Good Group")]
    mock_client.iter_messages = MagicMock(return_value=[mock_telegram_message])
    mocker.patch('app.services.scraper.handler.get_telethon_client', return_value=mock_client)
    
    mocker.patch.object(settings, 'telegram_group_ids', [-100998, -100999])

    scraper_handler.fetch_and_save_messages(limit=10)
    
    assert mock_client.get_entity.call_count == 2
    mock_client.iter_messages.assert_called_once()
    mock_save.assert_called_once()
    mock_client.disconnect.assert_called_once()

def test_fetch_save_get_entity_value_error(mocker, mock_save, mock_telegram_message):
    """Test skipping a group if get_entity raises ValueError (bad ID)."""
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.is_connected.return_value = True
    mock_client.is_user_authorized.return_value = True
    mock_client.get_me.return_value = MagicMock(first_name="Test", username="testuser")
    mock_client.get_entity.side_effect = [ValueError("Cannot find entity"), MagicMock(title="Good Group")]
    mock_client.iter_messages = MagicMock(return_value=[mock_telegram_message])
    mocker.patch('app.services.scraper.handler.get_telethon_client', return_value=mock_client)
    
    mocker.patch.object(settings, 'telegram_group_ids', [-100998, -100999])

    scraper_handler.fetch_and_save_messages(limit=10)
    
    assert mock_client.get_entity.call_count == 2
    mock_client.iter_messages.assert_called_once()
    mock_save.assert_called_once()
    mock_client.disconnect.assert_called_once()

def test_fetch_save_iter_messages_error(mocker, mock_save):
    """Test handling errors during message iteration."""
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.is_connected.return_value = True
    mock_client.is_user_authorized.return_value = True
    mock_client.get_me.return_value = MagicMock(first_name="Test", username="testuser")
    mock_client.get_entity.return_value = MagicMock(title="Test Group")
    mock_client.iter_messages.side_effect = RPCError(request=None, code=400, message="Test RPC Error")
    mocker.patch('app.services.scraper.handler.get_telethon_client', return_value=mock_client)
    
    mocker.patch.object(settings, 'telegram_group_ids', [-100999])
    
    scraper_handler.fetch_and_save_messages(limit=10)
    
    mock_client.get_entity.assert_called_once()
    mock_client.iter_messages.assert_called_once()
    mock_save.assert_not_called()
    mock_client.disconnect.assert_called_once()

def test_fetch_save_flood_wait_error(mocker, mock_save):
    """Test handling FloodWaitError during message iteration."""
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.is_connected.return_value = True
    mock_client.is_user_authorized.return_value = True
    mock_client.get_me.return_value = MagicMock(first_name="Test", username="testuser")
    mock_client.get_entity.return_value = MagicMock(title="Test Group")
    
    # Create FloodWaitError instance and set seconds attribute manually
    flood_error = FloodWaitError(request=None) # request is often needed
    flood_error.seconds = 1 # Manually set the attribute
    mock_client.iter_messages.side_effect = flood_error
    
    mocker.patch('app.services.scraper.handler.get_telethon_client', return_value=mock_client)
    mock_time_sleep = mocker.patch('time.sleep')
    
    mocker.patch.object(settings, 'telegram_group_ids', [-100999])
    
    scraper_handler.fetch_and_save_messages(limit=10)
    
    mock_client.get_entity.assert_called_once()
    mock_client.iter_messages.assert_called_once()
    mock_time_sleep.assert_called_once_with(1) # Check sleep was called with 1
    mock_save.assert_not_called()
    mock_client.disconnect.assert_called_once()

def test_fetch_save_message_json_decode_error(mocker, mock_save, mock_telegram_message):
    """Test skipping a message if its JSON conversion fails."""
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.is_connected.return_value = True
    mock_client.is_user_authorized.return_value = True
    mock_client.get_me.return_value = MagicMock(first_name="Test", username="testuser")
    mock_client.get_entity.return_value = MagicMock(title="Test Group")
    mock_telegram_message.to_json.side_effect = json.JSONDecodeError("mock error", "", 0)
    mock_client.iter_messages = MagicMock(return_value=[mock_telegram_message])
    mocker.patch('app.services.scraper.handler.get_telethon_client', return_value=mock_client)
    
    mocker.patch.object(settings, 'telegram_group_ids', [-100999])
    
    scraper_handler.fetch_and_save_messages(limit=10)
    
    mock_client.iter_messages.assert_called_once()
    mock_save.assert_not_called()
    mock_client.disconnect.assert_called_once()

def test_fetch_save_skip_on_save_fail(mocker, mock_save, mock_telegram_message):
    """Test that loop continues if save_message returns False."""
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.is_connected.return_value = True
    mock_client.is_user_authorized.return_value = True
    mock_client.get_me.return_value = MagicMock(first_name="Test", username="testuser")
    mock_client.get_entity.return_value = MagicMock(title="Test Group")
    mock_client.iter_messages = MagicMock(return_value=[mock_telegram_message])
    mocker.patch('app.services.scraper.handler.get_telethon_client', return_value=mock_client)
    mock_save.return_value = False
    
    mocker.patch.object(settings, 'telegram_group_ids', [-100999])
    
    scraper_handler.fetch_and_save_messages(limit=10)
    
    mock_client.iter_messages.assert_called_once()
    mock_save.assert_called_once()
    mock_client.disconnect.assert_called_once() 