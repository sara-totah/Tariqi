# tests/services/test_storage_service.py

import pytest
from unittest.mock import MagicMock, call # Import call
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from uuid import uuid4
from datetime import datetime

# Import the service functions and schemas/models
from app.services.storage_service import (
    save_verified_incident,
    save_verified_incidents_batch
)
from app import schemas, models

# --- Fixtures --- 

@pytest.fixture
def db_session_mock():
    """Provides a mocked SQLAlchemy Session."""
    # Configure mock methods as needed for testing saves
    return MagicMock(spec=Session)

@pytest.fixture
def sample_verified_incident():
    """Provides a sample VerifiedIncident schema object."""
    return schemas.VerifiedIncident(
        id=uuid4(),
        representative_text="ازدحام شديد جدا",
        location=schemas.LocationInfo(text='شارع جمال عبد الناصر'),
        time=None,
        event_type='traffic',
        contributing_report_count=3,
        first_report_at=datetime.utcnow(),
        last_report_at=datetime.utcnow()
    )

@pytest.fixture
def sample_verified_incident_list(sample_verified_incident): # Depends on single sample
    """Provides a list of sample VerifiedIncident schema objects."""
    incident2 = schemas.VerifiedIncident(
        id=uuid4(),
        representative_text="حادث عند دوار الساعة",
        location=schemas.LocationInfo(text='دوار الساعة'),
        time=schemas.TimeInfo(text='الان'),
        event_type='accident',
        contributing_report_count=2,
        first_report_at=datetime.utcnow(),
        last_report_at=datetime.utcnow()
    )
    return [sample_verified_incident, incident2]

# --- Test Cases --- 

def test_save_verified_incident_success(db_session_mock, sample_verified_incident):
    """Tests successful saving of a single incident."""
    saved_report = save_verified_incident(db_session_mock, sample_verified_incident)

    # Verify DB interactions
    db_session_mock.add.assert_called_once()
    db_session_mock.commit.assert_called_once()
    db_session_mock.refresh.assert_called_once()
    db_session_mock.rollback.assert_not_called()

    # Verify the object added was a VerifiedReport model instance
    added_object = db_session_mock.add.call_args[0][0]
    assert isinstance(added_object, models.VerifiedReport)
    assert added_object.id == sample_verified_incident.id
    assert added_object.representative_text == sample_verified_incident.representative_text
    assert added_object.location_text == sample_verified_incident.location.text
    assert added_object.time_text is None # Based on fixture
    assert added_object.event_type == sample_verified_incident.event_type
    assert added_object.contributing_report_count == sample_verified_incident.contributing_report_count
    assert added_object.first_report_at == sample_verified_incident.first_report_at
    assert added_object.last_report_at == sample_verified_incident.last_report_at

    # Verify the returned object
    assert saved_report is not None
    assert saved_report.id == sample_verified_incident.id

def test_save_verified_incident_db_error(db_session_mock, sample_verified_incident):
    """Tests handling of SQLAlchemyError during save."""
    # Configure commit to raise an error
    db_session_mock.commit.side_effect = SQLAlchemyError("Test DB Commit Error")

    saved_report = save_verified_incident(db_session_mock, sample_verified_incident)

    # Verify DB interactions
    db_session_mock.add.assert_called_once()
    db_session_mock.commit.assert_called_once()
    db_session_mock.refresh.assert_not_called() # Should not be called if commit fails
    db_session_mock.rollback.assert_called_once() # Rollback should be called

    # Verify None is returned
    assert saved_report is None

def test_save_verified_incidents_batch_success(db_session_mock, sample_verified_incident_list):
    """Tests successful saving of a batch of incidents."""
    num_saved = save_verified_incidents_batch(db_session_mock, sample_verified_incident_list)

    # Verify count
    assert num_saved == len(sample_verified_incident_list)

    # Verify DB interactions: add called for each, commit called for each
    assert db_session_mock.add.call_count == len(sample_verified_incident_list)
    assert db_session_mock.commit.call_count == len(sample_verified_incident_list)
    db_session_mock.rollback.assert_not_called()

    # Optionally check args passed to add for each call
    call_args_list = db_session_mock.add.call_args_list
    assert len(call_args_list) == 2
    assert isinstance(call_args_list[0][0][0], models.VerifiedReport)
    assert call_args_list[0][0][0].id == sample_verified_incident_list[0].id
    assert isinstance(call_args_list[1][0][0], models.VerifiedReport)
    assert call_args_list[1][0][0].id == sample_verified_incident_list[1].id

def test_save_verified_incidents_batch_partial_failure(db_session_mock, sample_verified_incident_list):
    """Tests saving a batch where one commit fails."""
    # Configure commit to fail only on the second call
    db_session_mock.commit.side_effect = [None, SQLAlchemyError("Batch DB Commit Error")]

    num_saved = save_verified_incidents_batch(db_session_mock, sample_verified_incident_list)

    # Verify count (only the first one should succeed)
    assert num_saved == 1

    # Verify DB interactions: add called for both, commit attempted for both, rollback called once
    assert db_session_mock.add.call_count == len(sample_verified_incident_list)
    assert db_session_mock.commit.call_count == len(sample_verified_incident_list)
    db_session_mock.rollback.assert_called_once() # Called after the second commit fails

def test_save_verified_incidents_batch_empty(db_session_mock):
    """Tests saving an empty batch."""
    num_saved = save_verified_incidents_batch(db_session_mock, [])
    assert num_saved == 0
    db_session_mock.add.assert_not_called()
    db_session_mock.commit.assert_not_called()
    db_session_mock.rollback.assert_not_called() 