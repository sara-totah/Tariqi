import pytest
from unittest.mock import patch, MagicMock, AsyncMock # Add AsyncMock
from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import Session  # Added this import
from sqlalchemy.exc import SQLAlchemyError

# Import telegram classes needed for mocking
from telegram import Update, User, Message, Chat, Bot
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# Import handlers to test
from app.services.bot.handlers import (
    start,
    help_command,
    latest_incidents,
    check_location,
    format_incident
)

# Import schemas and other dependencies
from app import schemas
from app.services.storage_service import get_latest_verified_incidents, search_verified_incidents_by_location

# --- Fixtures ---

@pytest.fixture
def mock_update(mocker): 
    """Creates a mock Update object."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 12345
    update.effective_user.first_name = "TestUser"
    update.effective_user.mention_html.return_value = "<a href='tg://user?id=12345'>TestUser</a>"
    
    update.message = MagicMock(spec=Message)
    update.message.chat = MagicMock(spec=Chat)
    update.message.chat.id = 67890
    update.message.message_id = 101
    update.message.reply_html = AsyncMock() # Use AsyncMock for awaitable methods
    update.message.reply_text = AsyncMock() # Use AsyncMock
    
    # Mock the message object returned by reply_text for editing later
    mock_sent_message = MagicMock(spec=Message)
    mock_sent_message.chat_id = update.message.chat.id
    mock_sent_message.message_id = 102 # Different ID for the bot's reply
    update.message.reply_text.return_value = mock_sent_message

    return update

@pytest.fixture
def mock_context(mocker): 
    """Creates a mock Context object."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = MagicMock(spec=Bot)
    context.bot.edit_message_text = AsyncMock() # Use AsyncMock
    context.args = [] # Default to no arguments
    return context

@pytest.fixture
def mock_db_session(mocker):
    """Provides a MagicMock for the SQLAlchemy Session."""
    session = MagicMock(spec=Session)
    # Configure necessary mock methods if needed, e.g., query, add, commit, rollback
    return session

@pytest.fixture
def sample_incident():
    """Provides a sample VerifiedIncident schema."""
    return schemas.VerifiedIncident(
        id=uuid4(),
        representative_text="حادث سير في شارع المستشفى",
        location=schemas.LocationInfo(text="شارع المستشفى"),
        time=None,
        event_type="accident",
        contributing_report_count=3,
        first_report_at=datetime.now(),
        last_report_at=datetime.now(),
        db_created_at=datetime.now()
    )

# --- Test Cases ---

@pytest.mark.asyncio
async def test_start_command(mock_update, mock_context):
    """Test the /start command handler."""
    await start(mock_update, mock_context)
    
    mock_update.message.reply_html.assert_awaited_once() 
    # Check that the user mention and basic structure are in the reply
    call_args, _ = mock_update.message.reply_html.call_args
    assert "أهلاً بك يا" in call_args[0]
    assert mock_update.effective_user.mention_html() in call_args[0]
    assert "/help" in call_args[0]

@pytest.mark.asyncio
async def test_help_command(mock_update, mock_context):
    """Test the /help command handler."""
    await help_command(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_awaited_once()
    call_args, _ = mock_update.message.reply_text.call_args
    assert "الأوامر المتاحة" in call_args[0]
    assert "/start" in call_args[0]
    assert "/help" in call_args[0]

@pytest.mark.asyncio
@patch('app.services.bot.handlers.get_db')
@patch('app.services.bot.handlers.get_latest_verified_incidents')
async def test_latest_incidents_success(
    mock_get_latest, mock_get_db, mock_update, mock_context, mock_db_session, sample_incident
): 
    """Test /latest command when incidents are found."""
    mock_get_db.return_value = iter([mock_db_session]) # Mock DB session context
    mock_get_latest.return_value = [sample_incident, sample_incident] # Return 2 incidents
    
    await latest_incidents(mock_update, mock_context)
    
    # Check initial status message
    mock_update.message.reply_text.assert_awaited_once_with(
        "⏳ جاري البحث عن آخر 5 تحديثات مؤكدة..."
    )
    
    # Check database call
    mock_get_latest.assert_called_once_with(db=mock_db_session, limit=5)
    mock_db_session.close.assert_called_once() # Ensure session closed
    
    # Check final message edit
    mock_context.bot.edit_message_text.assert_awaited_once()
    call_args, call_kwargs = mock_context.bot.edit_message_text.call_args
    assert "✅ آخر 2 تحديثات مؤكدة:" in call_kwargs['text']
    assert "شارع المستشفى" in call_kwargs['text'] # Check content from format_incident
    assert call_kwargs['parse_mode'] == ParseMode.MARKDOWN_V2

@pytest.mark.asyncio
@patch('app.services.bot.handlers.get_db')
@patch('app.services.bot.handlers.get_latest_verified_incidents')
async def test_latest_incidents_no_results(
    mock_get_latest, mock_get_db, mock_update, mock_context, mock_db_session
): 
    """Test /latest command when no incidents are found."""
    mock_get_db.return_value = iter([mock_db_session])
    mock_get_latest.return_value = [] # Return empty list
    
    await latest_incidents(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_awaited_once()
    mock_get_latest.assert_called_once()
    mock_db_session.close.assert_called_once()
    mock_context.bot.edit_message_text.assert_awaited_once_with(
        chat_id=mock_update.message.chat.id,
        message_id=mock_update.message.reply_text.return_value.message_id,
        text="لم يتم العثور على تحديثات مؤكدة مؤخراً.",
        parse_mode=ParseMode.MARKDOWN_V2
    )

@pytest.mark.asyncio
@patch('app.services.bot.handlers.get_db')
async def test_latest_incidents_db_error(mock_get_db, mock_update, mock_context): 
    """Test /latest command when there is a database error."""
    mock_get_db.side_effect = Exception("Simulated DB error")
    
    await latest_incidents(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_awaited_once()
    # edit_message should show error message
    mock_context.bot.edit_message_text.assert_awaited_once_with(
        chat_id=mock_update.message.chat.id,
        message_id=mock_update.message.reply_text.return_value.message_id,
        text="حدث خطأ أثناء البحث عن التحديثات. الرجاء المحاولة لاحقاً.",
        parse_mode=ParseMode.MARKDOWN_V2
    )

@pytest.mark.asyncio
@patch('app.services.bot.handlers.get_db')
@patch('app.services.bot.handlers.search_verified_incidents_by_location')
async def test_check_location_success(
    mock_search, mock_get_db, mock_update, mock_context, mock_db_session, sample_incident
): 
    """Test /check command success."""
    location_query = "رام الله"
    mock_context.args = [location_query]
    mock_get_db.return_value = iter([mock_db_session])
    mock_search.return_value = [sample_incident]
    
    await check_location(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_awaited_once()
    mock_search.assert_called_once_with(db=mock_db_session, location_query=location_query, limit=3)
    mock_db_session.close.assert_called_once()
    
    mock_context.bot.edit_message_text.assert_awaited_once()
    call_args, call_kwargs = mock_context.bot.edit_message_text.call_args
    assert f"✅ 1 تحديثات تم العثور عليها للموقع `{location_query}`:" in call_kwargs['text']
    assert "شارع المستشفى" in call_kwargs['text']
    assert call_kwargs['parse_mode'] == ParseMode.MARKDOWN_V2

@pytest.mark.asyncio
async def test_check_location_no_args(mock_update, mock_context): 
    """Test /check command with no location provided."""
    mock_context.args = [] # No arguments passed
    
    await check_location(mock_update, mock_context)
    
    # Should reply immediately with help text, not send a status message
    mock_update.message.reply_text.assert_awaited_once_with(
        "الرجاء تحديد الموقع بعد الأمر. مثال: `/check رام الله`",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    # edit_message should not be called
    mock_context.bot.edit_message_text.assert_not_awaited()

@pytest.mark.asyncio
@patch('app.services.bot.handlers.get_db')
@patch('app.services.bot.handlers.search_verified_incidents_by_location')
async def test_check_location_no_results(
    mock_search, mock_get_db, mock_update, mock_context, mock_db_session
): 
    """Test /check command when no incidents are found."""
    location_query = "مكان_غير_موجود"
    mock_context.args = [location_query]
    mock_get_db.return_value = iter([mock_db_session])
    mock_search.return_value = []
    
    await check_location(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_awaited_once()
    mock_search.assert_called_once()
    mock_db_session.close.assert_called_once()
    
    mock_context.bot.edit_message_text.assert_awaited_once_with(
        chat_id=mock_update.message.chat.id,
        message_id=mock_update.message.reply_text.return_value.message_id,
        text=f"لم يتم العثور على تحديثات مؤكدة للموقع: `{location_query}`",
        parse_mode=ParseMode.MARKDOWN_V2
    )

# Test formatting function separately
def test_format_incident(sample_incident):
    """Test the incident formatting helper."""
    formatted_text = format_incident(sample_incident)
    assert "📍 *الموقع:" in formatted_text
    assert sample_incident.location.text in formatted_text
    assert "🏷️ *نوع الحدث:" in formatted_text
    assert sample_incident.event_type in formatted_text
    assert "📝 *الوصف:" in formatted_text
    assert sample_incident.representative_text in formatted_text
    assert "🕒 *آخر تحديث:" in formatted_text
    assert "📊 *عدد البلاغات:" in formatted_text
    assert str(sample_incident.contributing_report_count) in formatted_text
    # Check that Time is NOT included if None
    assert "⏰ *الوقت:" not in formatted_text 