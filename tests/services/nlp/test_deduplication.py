# tests/services/nlp/test_deduplication.py

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4

# Import the service functions and schemas
from app.services.nlp.deduplication import (
    vectorize_texts,
    calculate_similarity,
    group_similar_reports,
    verify_groups,
    process_batch_for_deduplication,
    DEFAULT_SIMILARITY_THRESHOLD
)
from app import schemas

# Import sparse matrix for type checking/mocking
from scipy.sparse import csr_matrix
import numpy as np

# --- Fixtures --- 

@pytest.fixture
def sample_reports():
    """Provides a list of ExtractedReportInfo objects with timestamps."""
    now = datetime.now()
    return [
        # Group 1 (Traffic, similar, close in time)
        schemas.ExtractedReportInfo(
            original_text="ازدحام شديد في شارع صلاح الدين", is_relevant=True,
            locations=[schemas.LocationInfo(text="صلاح الدين")], times=[], event_type="traffic",
            report_timestamp=now - timedelta(minutes=10) # Add timestamp
        ),
        schemas.ExtractedReportInfo(
            original_text="ازمة سير كبيرة شارع صلاح الدين", is_relevant=True,
            locations=[schemas.LocationInfo(text="صلاح الدين")], times=[], event_type="traffic",
            report_timestamp=now - timedelta(minutes=5) # Add timestamp
        ),
        # Separate report (Traffic, less similar, older)
        schemas.ExtractedReportInfo(
            original_text="شارع صلاح الدين مزدحم جدا", is_relevant=True,
            locations=[schemas.LocationInfo(text="صلاح الدين")], times=[], event_type="traffic",
            report_timestamp=now - timedelta(hours=3) # Add timestamp (outside default window)
        ),
        # Group 2 (Accident, similar, close in time)
        schemas.ExtractedReportInfo(
            original_text="حادث سير بسيط قرب دوار المنارة", is_relevant=True,
            locations=[schemas.LocationInfo(text="دوار المنارة")], times=[schemas.TimeInfo(text="قبل قليل")], event_type="accident",
            report_timestamp=now - timedelta(hours=1, minutes=30) # Add timestamp
        ),
        schemas.ExtractedReportInfo(
            original_text="سيارة انقلبت عند دوار المنارة", is_relevant=True,
            locations=[schemas.LocationInfo(text="دوار المنارة")], times=[], event_type="accident",
            report_timestamp=now - timedelta(hours=1, minutes=25) # Add timestamp
        ),
        # Irrelevant report
        schemas.ExtractedReportInfo(
            original_text="طقس جميل في فلسطين اليوم", is_relevant=False,
            locations=[schemas.LocationInfo(text="فلسطين")], times=[schemas.TimeInfo(text="اليوم")], event_type=None,
            report_timestamp=now # Add timestamp
        ),
    ]

# --- Test Cases for Individual Functions ---

# Note: Testing vectorize_texts and calculate_similarity accurately is complex
# as it depends heavily on the specific TF-IDF output. 
# We'll focus on integration testing via process_batch_for_deduplication
# and add basic sanity checks here.

def test_vectorize_texts_basic(sample_reports):
    """Basic test for vectorize_texts return type and shape."""
    # Use normalized text
    texts = [report.original_text for report in sample_reports] # Pretend already normalized for this test
    tfidf_matrix = vectorize_texts(texts)
    assert isinstance(tfidf_matrix, csr_matrix) 
    assert tfidf_matrix.shape[0] == len(texts)
    assert tfidf_matrix.shape[1] > 0 # Should have some features

def test_calculate_similarity_basic(sample_reports):
    """Basic test for calculate_similarity return type and shape."""
    texts = [report.original_text for report in sample_reports]
    tfidf_matrix = vectorize_texts(texts)
    similarity_matrix = calculate_similarity(tfidf_matrix)
    assert isinstance(similarity_matrix, np.ndarray)
    assert similarity_matrix.shape == (len(texts), len(texts))
    assert np.all(similarity_matrix >= 0) # Similarities should be non-negative
    assert np.all(similarity_matrix <= 1.01) # Allow for floating point inaccuracies

# Mock similarity matrix for testing grouping and verification logic directly
@pytest.fixture
def mock_similarity_matrix():
    """Provides a sample similarity matrix corresponding to sample_reports."""
    # Adjusted slightly to reflect potential grouping differences
    return np.array([
        [1.00, 0.90, 0.60, 0.10, 0.10, 0.00],
        [0.90, 1.00, 0.50, 0.10, 0.10, 0.00],
        [0.60, 0.50, 1.00, 0.20, 0.20, 0.00],
        [0.10, 0.10, 0.20, 1.00, 0.85, 0.00],
        [0.10, 0.10, 0.20, 0.85, 1.00, 0.00],
        [0.00, 0.00, 0.00, 0.00, 0.00, 1.00],
    ])

def test_group_similar_reports_default_threshold(sample_reports, mock_similarity_matrix):
    """Test grouping with default threshold and time window."""
    # Reports 0, 1 are similar (0.90 >= 0.8) and within 2 hours
    # Report 2 is outside time window for 0, 1
    # Reports 3, 4 are similar (0.85 >= 0.8) and within 2 hours
    # Report 5 is dissimilar
    groups = group_similar_reports(sample_reports, mock_similarity_matrix)
    expected_groups_sets = [{0, 1}, {2}, {3, 4}, {5}]
    result_groups_sets = [set(g) for g in groups]
    assert len(result_groups_sets) == len(expected_groups_sets)
    for expected_set in expected_groups_sets:
        assert expected_set in result_groups_sets

def test_group_similar_reports_custom_threshold(sample_reports, mock_similarity_matrix):
    """Test grouping with a lower threshold."""
    # With threshold 0.55:
    # Report 0 groups with 1 (0.90) and 2 (0.60), all within default 2hr window?
    # Check timestamps: 0 (-10m), 1 (-5m), 2 (-3h). 0 and 2 diff > 2hr. Group {0, 1}
    # Report 2 processed next, no similarities >= 0.55 within 2hrs. Group {2}
    # Report 3 groups with 4 (0.85). Group {3, 4}
    # Report 5 groups with nothing. Group {5}
    groups = group_similar_reports(sample_reports, mock_similarity_matrix, threshold=0.55)
    expected_groups_sets = [{0, 1}, {2}, {3, 4}, {5}]
    result_groups_sets = [set(g) for g in groups]
    assert len(result_groups_sets) == len(expected_groups_sets)
    for expected_set in expected_groups_sets:
        assert expected_set in result_groups_sets

def test_group_similar_reports_custom_time_window(sample_reports, mock_similarity_matrix):
    """Test grouping with a larger time window."""
    # With time_window 4 hours:
    # Report 0 groups with 1 (0.90) and 2 (0.60). All within 4 hours. Threshold 0.8. Group {0, 1}
    # Report 2 processed next, sim 0.6 < 0.8. Group {2}
    # Report 3 groups with 4 (0.85). Group {3, 4}
    # Report 5 groups with nothing. Group {5}
    groups = group_similar_reports(sample_reports, mock_similarity_matrix, time_window=timedelta(hours=4))
    expected_groups_sets = [{0, 1}, {2}, {3, 4}, {5}]
    result_groups_sets = [set(g) for g in groups]
    assert len(result_groups_sets) == len(expected_groups_sets)
    for expected_set in expected_groups_sets:
        assert expected_set in result_groups_sets

def test_verify_groups(sample_reports):
    """Test the verification logic and aggregation."""
    # Use groups expected from default run
    groups_indices = [[0, 1], [2], [3, 4], [5]]
    verified_incidents = verify_groups(groups_indices, sample_reports)

    assert len(verified_incidents) == 2 # Only groups [0, 1] and [3, 4] should be verified

    # Check first verified group (reports 0, 1)
    incident1 = verified_incidents[0]
    assert isinstance(incident1, schemas.VerifiedIncident)
    assert incident1.representative_text == sample_reports[0].original_text
    assert incident1.location.text == 'صلاح الدين' # Most common
    assert incident1.event_type == 'traffic' # Most common
    assert incident1.contributing_report_count == 2
    assert incident1.first_report_at == sample_reports[0].report_timestamp # Use correct attribute
    assert incident1.last_report_at == sample_reports[1].report_timestamp # Use correct attribute
    assert incident1.time is None # No TimeInfo in reports 0, 1

    # Check second verified group (reports 3, 4)
    incident2 = verified_incidents[1]
    assert isinstance(incident2, schemas.VerifiedIncident)
    assert incident2.representative_text == sample_reports[3].original_text
    assert incident2.location.text == 'دوار المنارة'
    assert incident2.event_type == 'accident'
    assert incident2.contributing_report_count == 2
    assert incident2.first_report_at == sample_reports[3].report_timestamp # Use correct attribute
    assert incident2.last_report_at == sample_reports[4].report_timestamp # Use correct attribute
    assert incident2.time is not None
    assert incident2.time.text == 'قبل قليل' # From earliest report (report 3)

# --- Test Case for Main Function (Integration) ---

# Patch the underlying functions for the main integration test
@patch('app.services.nlp.deduplication.vectorize_texts')
@patch('app.services.nlp.deduplication.calculate_similarity')
@patch('app.services.nlp.deduplication.normalize_arabic_text', side_effect=lambda x: x) # Mock normalization
def test_process_batch_for_deduplication(
    mock_normalize, mock_calc_sim, mock_vectorize,
    sample_reports, mock_similarity_matrix
):
    """Test the full deduplication pipeline integration."""
    # Configure mocks
    mock_vectorize.return_value = "mock_tfidf_matrix" # Doesn't matter, calc_sim is mocked
    mock_calc_sim.return_value = mock_similarity_matrix

    verified_incidents = process_batch_for_deduplication(sample_reports)

    # Verify calls
    assert mock_normalize.call_count == len(sample_reports)
    mock_vectorize.assert_called_once()
    mock_calc_sim.assert_called_once_with("mock_tfidf_matrix")

    # Verify output - Check properties without assuming order
    assert len(verified_incidents) == 2
    
    traffic_incidents = [inc for inc in verified_incidents if inc.event_type == 'traffic']
    accident_incidents = [inc for inc in verified_incidents if inc.event_type == 'accident']
    
    assert len(traffic_incidents) == 1
    assert len(accident_incidents) == 1
    
    # Check properties of the traffic incident (from group [0, 1])
    assert traffic_incidents[0].location.text == 'صلاح الدين'
    assert traffic_incidents[0].contributing_report_count == 2
    assert traffic_incidents[0].first_report_at == sample_reports[0].report_timestamp
    assert traffic_incidents[0].last_report_at == sample_reports[1].report_timestamp
    
    # Check properties of the accident incident (from group [3, 4])
    assert accident_incidents[0].location.text == 'دوار المنارة'
    assert accident_incidents[0].contributing_report_count == 2
    assert accident_incidents[0].first_report_at == sample_reports[3].report_timestamp
    assert accident_incidents[0].last_report_at == sample_reports[4].report_timestamp 