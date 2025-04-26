# tests/services/nlp/test_entity_extraction.py

import pytest
from unittest.mock import patch

from app.services.nlp.entity_extraction import (
    _process_ner_tags,
    classify_relevance,
    extract_and_classify
)
from app import schemas

# --- Test Cases for _process_ner_tags ---

def test_process_ner_tags_basic():
    """Tests grouping basic B-LOC, I-LOC, O tags."""
    tagged_tokens = [
        ('ازمه', 'O'), ('في', 'O'), ('شارع', 'O'), ('صلاح', 'B-LOC'), ('الدين', 'I-LOC'), ('وسط', 'O'), ('القدس', 'B-LOC'), ('.', 'O')
    ]
    expected_output = {
        "locations": [schemas.LocationInfo(text='صلاح الدين'), schemas.LocationInfo(text='القدس')],
        "times": []
    }
    assert _process_ner_tags(tagged_tokens) == expected_output

def test_process_ner_tags_with_time():
    """Tests grouping LOC and TIME tags."""
    tagged_tokens = [
        ('الحادث', 'O'), ('وقع', 'O'), ('الساعه', 'B-TIME'), ('7', 'I-TIME'), ('مساء', 'I-TIME'), ('في', 'O'), ('نابلس', 'B-LOC')
    ]
    expected_output = {
        "locations": [schemas.LocationInfo(text='نابلس')],
        "times": [schemas.TimeInfo(text='الساعه 7 مساء')]
    }
    assert _process_ner_tags(tagged_tokens) == expected_output

def test_process_ner_tags_no_entities():
    """Tests input with only O tags."""
    tagged_tokens = [('صباح', 'O'), ('الخير', 'O')]
    expected_output = {"locations": [], "times": []}
    assert _process_ner_tags(tagged_tokens) == expected_output

def test_process_ner_tags_consecutive_diff_entities():
    """Tests handling of consecutive entities of different types."""
    tagged_tokens = [('اجتماع', 'O'), ('في', 'O'), ('رام', 'B-LOC'), ('الله', 'I-LOC'), ('الساعه', 'B-TIME'), ('10', 'I-TIME')]
    expected_output = {
        "locations": [schemas.LocationInfo(text='رام الله')],
        "times": [schemas.TimeInfo(text='الساعه 10')]
    }
    assert _process_ner_tags(tagged_tokens) == expected_output

def test_process_ner_tags_empty():
    """Tests empty input."""
    tagged_tokens = []
    expected_output = {"locations": [], "times": []}
    assert _process_ner_tags(tagged_tokens) == expected_output

# --- Test Cases for classify_relevance ---

@pytest.mark.parametrize(
    "text, locations, expected_relevance",
    [
        ("ازمه سير خانقه", [], True), # Keyword match
        ("حادث مروع على الطريق", [], True), # Keyword match
        ("شارع صلاح الدين مغلق", [], True), # Keyword match
        ("يوجد حاجز على مدخل المدينه", [], True), # Keyword match
        ("فريق العمل يجتمع الان", [], False), # No keywords, no location
        ("الجو جميل اليوم", [], False), # No keywords, no location
        ("الاحتلال يقتحم نابلس", [schemas.LocationInfo(text='نابلس')], True), # Location match
        ("اجتماع في بلديه الخليل", [schemas.LocationInfo(text='الخليل')], True), # Location match
        ("", [], False), # Empty text
    ]
)
def test_classify_relevance(text, locations, expected_relevance):
    assert classify_relevance(text, locations) == expected_relevance

# --- Test Cases for extract_and_classify ---

# Mock NER output for specific inputs
MOCK_NER_OUTPUTS = {
    "ازمه سير خانقه في شارع صلاح الدين وسط القدس .": [
        ('ازمه', 'O'), ('سير', 'O'), ('خانقه', 'O'), ('في', 'O'), ('شارع', 'O'), ('صلاح', 'B-LOC'), ('الدين', 'I-LOC'), ('وسط', 'O'), ('القدس', 'B-LOC'), ('.', 'O')
    ],
    "وقع حادث مروع الساعه 7 مساء في نابلس .": [
        ('وقع', 'O'), ('حادث', 'O'), ('مروع', 'O'), ('الساعه', 'B-TIME'), ('7', 'I-TIME'), ('مساء', 'I-TIME'), ('في', 'O'), ('نابلس', 'B-LOC'), ('.', 'O')
    ],
     "صباح الخير يا جماعه": [
        ('صباح', 'O'), ('الخير', 'O'), ('يا', 'O'), ('جماعه', 'O')
    ]
}

# Mock preprocessing function for consistent tokenization in tests
# (Assumes simple space splitting for mock NER input keys)
def mock_preprocess(text):
    return text.split()

@patch('app.services.nlp.entity_extraction.preprocess_text', side_effect=mock_preprocess)
@patch('app.services.nlp.entity_extraction._extract_entities_from_tokens')
def test_extract_and_classify_traffic(mock_extract_entities, mock_prep,):
    """Tests the full pipeline for a relevant traffic report."""
    original_text = "ازمه سير خانقه في شارع صلاح الدين وسط القدس ."
    mock_extract_entities.return_value = MOCK_NER_OUTPUTS[original_text]

    result = extract_and_classify(original_text)

    assert isinstance(result, schemas.ExtractedReportInfo)
    assert result.original_text == original_text
    assert result.is_relevant is True
    assert result.event_type == "traffic"
    assert result.locations == [schemas.LocationInfo(text='صلاح الدين'), schemas.LocationInfo(text='القدس')]
    assert result.times == []
    mock_prep.assert_called_once_with(original_text)
    mock_extract_entities.assert_called_once_with(mock_preprocess(original_text))

@patch('app.services.nlp.entity_extraction.preprocess_text', side_effect=mock_preprocess)
@patch('app.services.nlp.entity_extraction._extract_entities_from_tokens')
def test_extract_and_classify_accident(mock_extract_entities, mock_prep):
    """Tests the full pipeline for a relevant accident report."""
    original_text = "وقع حادث مروع الساعه 7 مساء في نابلس ."
    mock_extract_entities.return_value = MOCK_NER_OUTPUTS[original_text]

    result = extract_and_classify(original_text)

    assert isinstance(result, schemas.ExtractedReportInfo)
    assert result.original_text == original_text
    assert result.is_relevant is True
    assert result.event_type == "accident"
    assert result.locations == [schemas.LocationInfo(text='نابلس')]
    assert result.times == [schemas.TimeInfo(text='الساعه 7 مساء')]
    mock_prep.assert_called_once_with(original_text)
    mock_extract_entities.assert_called_once_with(mock_preprocess(original_text))

@patch('app.services.nlp.entity_extraction.preprocess_text', side_effect=mock_preprocess)
@patch('app.services.nlp.entity_extraction._extract_entities_from_tokens')
def test_extract_and_classify_irrelevant(mock_extract_entities, mock_prep):
    """Tests the full pipeline for an irrelevant message."""
    original_text = "صباح الخير يا جماعه"
    mock_extract_entities.return_value = MOCK_NER_OUTPUTS[original_text]

    result = extract_and_classify(original_text)

    assert isinstance(result, schemas.ExtractedReportInfo)
    assert result.original_text == original_text
    assert result.is_relevant is False
    assert result.event_type is None
    assert result.locations == []
    assert result.times == []
    mock_prep.assert_called_once_with(original_text)
    mock_extract_entities.assert_called_once_with(mock_preprocess(original_text))

@patch('app.services.nlp.entity_extraction.preprocess_text', return_value=[])
@patch('app.services.nlp.entity_extraction._extract_entities_from_tokens', return_value=[])
def test_extract_and_classify_empty_input(mock_extract_entities, mock_prep):
    """Tests the full pipeline with empty input text."""
    original_text = ""
    result = extract_and_classify(original_text)

    assert isinstance(result, schemas.ExtractedReportInfo)
    assert result.original_text == ""
    assert result.is_relevant is False
    assert result.event_type is None
    assert result.locations == []
    assert result.times == []
    # Ensure preprocessing is NOT called due to early return
    mock_prep.assert_not_called()
    # NER extraction should also not be called
    mock_extract_entities.assert_not_called() 