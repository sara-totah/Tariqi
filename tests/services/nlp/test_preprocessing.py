# tests/services/nlp/test_preprocessing.py

import pytest
from app.services.nlp.preprocessing import (
    normalize_arabic_text,
    tokenize_arabic_text,
    preprocess_text
)

# --- Test Cases for normalize_arabic_text ---

@pytest.mark.parametrize(
    "input_text, expected_output",
    [
        # Basic diacritics removal
        ("السَّلامُ عَلَيْكُمْ", "السلام عليكم"),
        # Alef normalization (أ, إ, آ -> ا)
        ("أَنا إِسْمِي أَحْمَد", "انا اسمي احمد"),
        ("آسِفٌ", "اسف"),
        # Yaa normalization (ى -> ي)
        ("عَلَى الطَّاوِلَةِ", "علي الطاوله"),
        # Haa normalization (ة -> ه)
        ("مَدْرَسَةٌ جَمِيلَةٌ", "مدرسه جميله"),
        # Mixed normalization
        ("أَهْلاً بِكُمْ فِي مَدِينَةِ الْقُدْسِ", "اهلا بكم في مدينه القدس"),
        # Unicode normalization (e.g., different space types if applicable - check CAMeL Tools behavior)
        # (ـ is Tatweel/Kashida - normalization might remove it or keep it depending on config/function)
        ("التاريخ: ١٤٤٥/١٠/٠٥ هـ", "التاريخ: ١٤٤٥/١٠/٠٥ هـ"), # Assuming normalize_unicode keeps Tatweel
        # No changes needed
        ("سلام يا عالم", "سلام يا عالم"),
        # Empty string
        ("", ""),
        # Non-Arabic text
        ("Hello World 123", "Hello World 123"),
    ]
)
def test_normalize_arabic_text(input_text, expected_output):
    """Tests various normalization scenarios using camel-tools."""
    assert normalize_arabic_text(input_text) == expected_output

# --- Test Cases for tokenize_arabic_text ---

@pytest.mark.parametrize(
    "input_text, expected_output",
    [
        # Simple sentence (assuming normalized)
        ("السلام عليكم", ["السلام", "عليكم"]),
        # Sentence with punctuation - camel-tools separates punctuation
        ("اهلا بكم في مدينه القدس.", ["اهلا", "بكم", "في", "مدينه", "القدس", "."]),
        # Sentence with numbers and punctuation
        ("التاريخ: ١٤٤٥/١٠/٠٥ هـ", ["التاريخ", ":", "١٤٤٥", "/", "١٠", "/", "٠٥", "هـ"]),
        # Empty string
        ("", []),
        # Single word
        ("مرحبا", ["مرحبا"]),
        # Non-Arabic with punctuation
        ("Hello World!", ["Hello", "World", "!"]),
    ]
)
def test_tokenize_arabic_text(input_text, expected_output):
    """Tests tokenization scenarios using camel-tools simple_word_tokenize."""
    assert tokenize_arabic_text(input_text) == expected_output

# --- Test Cases for preprocess_text ---

@pytest.mark.parametrize(
    "input_text, expected_output",
    [
        # Combined normalization and tokenization
        ("السَّلامُ عَلَيْكُمْ يا أَصْدِقَائِي", ["السلام", "عليكم", "يا", "اصدقائي"]),
        ("أَهْلاً بِكُمْ فِي مَدِينَةِ الْقُدْسِ.", ["اهلا", "بكم", "في", "مدينه", "القدس", "."]),
        # Empty string
        ("", []),
        # Already normalized text
        ("شكرا جزيلا", ["شكرا", "جزيلا"]),
        # Non-Arabic with number and punctuation
        ("Test 123!", ["Test", "123", "!"]),
    ]
)
def test_preprocess_text(input_text, expected_output):
    """Tests the combined preprocessing pipeline using camel-tools."""
    assert preprocess_text(input_text) == expected_output 