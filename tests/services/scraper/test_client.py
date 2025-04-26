import pytest
import os
from unittest.mock import patch, MagicMock

# Import the function/object to test
from app.services.scraper.client import get_telethon_client, SESSION_PATH
from app.settings import settings # Import the settings instance
# from telethon.sync import TelegramClient # No longer needed here directly

# No longer needed if settings is imported directly?
# @pytest.fixture(autouse=True)
# def mock_telethon_client(mocker):
#     """Mocks the TelegramClient instantiation globally for these tests."""
#     mocker.patch('telethon.sync.TelegramClient', return_value=MagicMock())


def test_get_telethon_client_local_session(mocker):
    """Test session path uses local name when not in Lambda."""
    # Ensure Lambda env var is not set
    mocker.patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": ""}, clear=True)
    # Mock settings values used
    mocker.patch.object(settings, 'telegram_session_name', 'local_session_test')
    mocker.patch.object(settings, 'telegram_api_id', 123)
    mocker.patch.object(settings, 'telegram_api_hash', 'abc')
    
    # Reload the client module AFTER patching env and settings
    import importlib
    from app.services.scraper import client
    importlib.reload(client)

    # Mock the TelegramClient constructor WITHIN the reloaded client module
    mock_client_constructor = mocker.patch('app.services.scraper.client.TelegramClient')

    _ = client.get_telethon_client()

    # Assert TelegramClient was called with the correct *local* session path
    mock_client_constructor.assert_called_once_with(
        session='local_session_test', 
        api_id=123, 
        api_hash='abc'
    )


def test_get_telethon_client_lambda_session(mocker):
    """Test session path uses /tmp when in Lambda environment."""
    # Set Lambda env var
    mocker.patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "test-lambda"}, clear=True)
    # Mock settings values used
    mocker.patch.object(settings, 'telegram_session_name', 'lambda_session_test')
    mocker.patch.object(settings, 'telegram_api_id', 456)
    mocker.patch.object(settings, 'telegram_api_hash', 'def')
    
    # Reload the client module AFTER patching env and settings
    import importlib
    from app.services.scraper import client
    importlib.reload(client)

    # Mock the TelegramClient constructor WITHIN the reloaded client module
    mock_client_constructor = mocker.patch('app.services.scraper.client.TelegramClient')

    _ = client.get_telethon_client()

    # Assert TelegramClient was called with the correct *lambda* session path
    expected_lambda_path = os.path.join("/tmp", 'lambda_session_test')
    mock_client_constructor.assert_called_once_with(
        session=expected_lambda_path, 
        api_id=456, 
        api_hash='def'
    ) 