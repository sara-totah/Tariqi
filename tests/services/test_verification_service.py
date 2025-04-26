import pytest
from unittest.mock import patch, MagicMock, call
from typing import List, Union
from uuid import uuid4
from datetime import datetime

# Import the function to test
from app.services.verification_service import run_verification_pipeline, _fetch_unprocessed_reports

# Import relevant models and schemas
from app import models, schemas
from sqlalchemy.orm import Session # Correct import for type hinting

# --- Fixtures ---

@pytest.fixture
def db_session_mock():
    """Provides a MagicMock for the SQLAlchemy Session."""
    session = MagicMock(spec=Session)
    # Mock the query interface
    session.query.return_value.filter.return_value.limit.return_value.all.return_value = [] # Default empty
    session.query.return_value.filter.return_value.update.return_value = None # Mock update
    return session

@pytest.fixture
def sample_raw_group_message():
    """Provides a sample RawGroupMessage model instance."""
    return models.RawGroupMessage(
        id=uuid4(),
        source_group_id=12345,
        message_id=101,
        text="Sample group message text حادث خطير",
        timestamp=datetime.now(),
        processed=False
    )

@pytest.fixture
def sample_raw_user_report():
    """Provides a sample RawUserReport model instance."""
    return models.RawUserReport(
        id=uuid4(),
        user_id=9876,
        message_id=202,
        text="Sample user report ازدحام شديد",
        timestamp=datetime.now(),
        processed=False
    )
    
@pytest.fixture
def sample_empty_raw_report():
    """Provides a sample RawUserReport model instance with empty text."""
    return models.RawUserReport(
        id=uuid4(),
        user_id=9877,
        message_id=203,
        text="    ", # Whitespace only
        timestamp=datetime.now(),
        processed=False
    )

@pytest.fixture
def sample_extracted_info_relevant(sample_raw_group_message):
    """Provides a sample relevant ExtractedReportInfo schema instance."""
    return schemas.ExtractedReportInfo(
        original_text=sample_raw_group_message.text,
        is_relevant=True,
        locations=[schemas.LocationInfo(text="الموقع أ") ],
        times=[],
        event_type="accident",
        original_report_id=sample_raw_group_message.id,
        report_timestamp=sample_raw_group_message.timestamp
    )
    
@pytest.fixture
def sample_extracted_info_irrelevant(sample_raw_user_report):
    """Provides a sample irrelevant ExtractedReportInfo schema instance."""
    return schemas.ExtractedReportInfo(
        original_text=sample_raw_user_report.text,
        is_relevant=False,
        locations=[],
        times=[],
        event_type=None,
        original_report_id=sample_raw_user_report.id,
        report_timestamp=sample_raw_user_report.timestamp
    )

@pytest.fixture
def sample_verified_incident():
    """Provides a sample VerifiedIncident schema instance."""
    return schemas.VerifiedIncident(
        id=uuid4(),
        representative_text="Sample group message text حادث خطير",
        location=schemas.LocationInfo(text="الموقع أ"),
        time=None,
        event_type="accident",
        contributing_report_count=2,
        first_report_at=datetime.now(),
        last_report_at=datetime.now()
    )

# --- Test Cases ---

# Using patch decorators to mock dependencies within the service module
@patch('app.services.verification_service._fetch_unprocessed_reports')
@patch('app.services.verification_service.extract_and_classify')
@patch('app.services.verification_service.process_batch_for_deduplication')
@patch('app.services.verification_service.save_verified_incidents_batch')
def test_run_verification_pipeline_happy_path(
    mock_save_batch,
    mock_deduplicate,
    mock_extract,
    mock_fetch,
    db_session_mock,
    sample_raw_group_message,
    sample_raw_user_report,
    sample_extracted_info_relevant,
    sample_extracted_info_irrelevant, # Use this for the user report
    sample_verified_incident
):
    """Tests the full pipeline execution with mixed relevant/irrelevant reports."""
    # Arrange
    # Mock fetch to return one group message and one user report
    fetched_reports = [sample_raw_group_message, sample_raw_user_report]
    mock_fetch.return_value = fetched_reports
    
    # Mock extract to return one relevant and one irrelevant result
    # Map report text to extracted info for clarity
    extract_results_map = {
        sample_raw_group_message.text: sample_extracted_info_relevant,
        sample_raw_user_report.text: sample_extracted_info_irrelevant
    }
    mock_extract.side_effect = lambda text: extract_results_map.get(text)

    # Mock deduplicate to return one verified incident when called with the relevant report
    mock_deduplicate.return_value = [sample_verified_incident]
    
    # Mock save batch to return the number of incidents it received
    mock_save_batch.return_value = 1

    # Act
    run_verification_pipeline(db_session_mock)

    # Assert
    # 1. Fetch was called
    mock_fetch.assert_called_once_with(db_session_mock)

    # 2. Extract was called for both non-empty reports
    expected_extract_calls = [
        call(sample_raw_group_message.text),
        call(sample_raw_user_report.text)
    ]
    mock_extract.assert_has_calls(expected_extract_calls, any_order=True)
    assert mock_extract.call_count == len(fetched_reports)

    # 3. Deduplicate was called only with the relevant extracted info
    # Ensure the argument matches the relevant report schema
    mock_deduplicate.assert_called_once()
    call_args, _ = mock_deduplicate.call_args
    assert len(call_args[0]) == 1 # Only one relevant report passed
    assert call_args[0][0] == sample_extracted_info_relevant

    # 4. Save batch was called with the result from deduplicate
    mock_save_batch.assert_called_once_with(db=db_session_mock, incidents=[sample_verified_incident])

    # 5. Mark processed was called for ALL fetched reports
    # Check the filter IDs and the update dictionary
    update_calls = db_session_mock.query.return_value.filter.return_value.update.call_args_list
    processed_ids_in_calls = set()
    for update_call in update_calls:
        update_args, update_kwargs = update_call
        # The update dictionary should be the first argument
        assert update_args[0] == {models.RawGroupMessage.processed: True} or update_args[0] == {models.RawUserReport.processed: True}
        # The filter object is harder to inspect directly for IDs, but we can check commit
    
    # Check that commit was called after updates
    db_session_mock.commit.assert_called_once()
    db_session_mock.rollback.assert_not_called()


@patch('app.services.verification_service._fetch_unprocessed_reports')
@patch('app.services.verification_service.extract_and_classify')
@patch('app.services.verification_service.process_batch_for_deduplication')
@patch('app.services.verification_service.save_verified_incidents_batch')
def test_run_verification_pipeline_no_reports(
    mock_save_batch,
    mock_deduplicate,
    mock_extract,
    mock_fetch,
    db_session_mock
):
    """Tests pipeline behavior when no unprocessed reports are fetched."""
    # Arrange
    mock_fetch.return_value = [] # No reports fetched

    # Act
    run_verification_pipeline(db_session_mock)

    # Assert
    mock_fetch.assert_called_once_with(db_session_mock)
    # Ensure other services and DB updates were NOT called
    mock_extract.assert_not_called()
    mock_deduplicate.assert_not_called()
    mock_save_batch.assert_not_called()
    db_session_mock.query.return_value.filter.return_value.update.assert_not_called()
    db_session_mock.commit.assert_not_called()
    db_session_mock.rollback.assert_not_called()
    

@patch('app.services.verification_service._fetch_unprocessed_reports')
@patch('app.services.verification_service.extract_and_classify')
@patch('app.services.verification_service.process_batch_for_deduplication')
@patch('app.services.verification_service.save_verified_incidents_batch')
def test_run_verification_pipeline_only_irrelevant(
    mock_save_batch,
    mock_deduplicate,
    mock_extract,
    mock_fetch,
    db_session_mock,
    sample_raw_user_report, # Use an irrelevant one
    sample_extracted_info_irrelevant
):
    """Tests pipeline when only irrelevant reports are processed."""
    # Arrange
    fetched_reports = [sample_raw_user_report]
    mock_fetch.return_value = fetched_reports
    mock_extract.return_value = sample_extracted_info_irrelevant
    
    # Act
    run_verification_pipeline(db_session_mock)

    # Assert
    mock_fetch.assert_called_once()
    mock_extract.assert_called_once_with(sample_raw_user_report.text)
    # Deduplicate and save should NOT be called
    mock_deduplicate.assert_not_called()
    mock_save_batch.assert_not_called()
    
    # Mark processed SHOULD be called for the fetched report
    db_session_mock.query.return_value.filter.return_value.update.assert_called()
    db_session_mock.commit.assert_called_once()
    db_session_mock.rollback.assert_not_called()
    
@patch('app.services.verification_service._fetch_unprocessed_reports')
@patch('app.services.verification_service.extract_and_classify')
@patch('app.services.verification_service.process_batch_for_deduplication')
@patch('app.services.verification_service.save_verified_incidents_batch')
def test_run_verification_pipeline_empty_text_report(
    mock_save_batch,
    mock_deduplicate,
    mock_extract,
    mock_fetch,
    db_session_mock,
    sample_empty_raw_report # Report with only whitespace
):
    """Tests that reports with empty/whitespace text are skipped by extraction but still marked processed."""
    # Arrange
    fetched_reports = [sample_empty_raw_report]
    mock_fetch.return_value = fetched_reports
    
    # Act
    run_verification_pipeline(db_session_mock)

    # Assert
    mock_fetch.assert_called_once()
    # Extract should NOT be called for empty text
    mock_extract.assert_not_called()
    mock_deduplicate.assert_not_called()
    mock_save_batch.assert_not_called()
    
    # Mark processed SHOULD still be called
    db_session_mock.query.return_value.filter.return_value.update.assert_called()
    db_session_mock.commit.assert_called_once()
    db_session_mock.rollback.assert_not_called()

@patch('app.services.verification_service._fetch_unprocessed_reports')
@patch('app.services.verification_service.extract_and_classify')
@patch('app.services.verification_service.process_batch_for_deduplication')
@patch('app.services.verification_service.save_verified_incidents_batch')
def test_run_verification_pipeline_deduplication_returns_empty(
    mock_save_batch,
    mock_deduplicate,
    mock_extract,
    mock_fetch,
    db_session_mock,
    sample_raw_group_message,
    sample_extracted_info_relevant
):
    """Tests pipeline when deduplication finds no verified incidents."""
    # Arrange
    fetched_reports = [sample_raw_group_message]
    mock_fetch.return_value = fetched_reports
    mock_extract.return_value = sample_extracted_info_relevant
    mock_deduplicate.return_value = [] # Deduplication returns empty list

    # Act
    run_verification_pipeline(db_session_mock)

    # Assert
    mock_fetch.assert_called_once()
    mock_extract.assert_called_once()
    mock_deduplicate.assert_called_once()
    # Save batch should NOT be called
    mock_save_batch.assert_not_called()
    
    # Mark processed SHOULD be called
    db_session_mock.query.return_value.filter.return_value.update.assert_called()
    db_session_mock.commit.assert_called_once()
    db_session_mock.rollback.assert_not_called()
    
# Add test for DB error during final "mark processed" step
@patch('app.services.verification_service._fetch_unprocessed_reports')
@patch('app.services.verification_service.extract_and_classify')
@patch('app.services.verification_service.process_batch_for_deduplication')
@patch('app.services.verification_service.save_verified_incidents_batch')
def test_run_verification_pipeline_mark_processed_db_error(
    mock_save_batch,
    mock_deduplicate,
    mock_extract,
    mock_fetch,
    db_session_mock,
    sample_raw_group_message,
    sample_extracted_info_relevant,
    sample_verified_incident
):
    """Tests pipeline behavior when the final 'mark processed' update fails."""
    # Arrange
    fetched_reports = [sample_raw_group_message]
    mock_fetch.return_value = fetched_reports
    mock_extract.return_value = sample_extracted_info_relevant
    mock_deduplicate.return_value = [sample_verified_incident]
    mock_save_batch.return_value = 1
    
    # Simulate DB error during the update call
    db_session_mock.query.return_value.filter.return_value.update.side_effect = Exception("Simulated DB Error during update")

    # Act
    # Expect the function to handle the exception and not raise it further
    run_verification_pipeline(db_session_mock)

    # Assert
    # Check that the pipeline ran up to the point of failure
    mock_fetch.assert_called_once()
    mock_extract.assert_called_once()
    mock_deduplicate.assert_called_once()
    mock_save_batch.assert_called_once()
    
    # Check that the update was attempted
    db_session_mock.query.return_value.filter.return_value.update.assert_called()
    
    # Check that commit was NOT called, but rollback WAS called
    db_session_mock.commit.assert_not_called()
    db_session_mock.rollback.assert_called_once()

# TODO: Add tests for the helper function _fetch_unprocessed_reports if needed, 
# though its logic is simple and covered by mocking its return value. 