# app/services/nlp/preprocessing.py

"""Module for preprocessing Arabic text using the CAMeL Tools library."""

import logging

# Import specific utilities from camel_tools
from camel_tools.utils.dediac import dediac_ar
from camel_tools.utils.normalize import (
    normalize_alef_ar, normalize_alef_maksura_ar, normalize_teh_marbuta_ar, normalize_unicode
)
from camel_tools.tokenizers.word import simple_word_tokenize

# Configure logging
logger = logging.getLogger(__name__)


def normalize_arabic_text(text: str) -> str:
    """
    Applies normalization to Arabic text using CAMeL Tools.

    Steps (order can matter):
    1. Normalize Unicode to ensure consistent character representations.
    2. Remove diacritics (Tashkeel).
    3. Normalize Alef forms (أ, إ, آ -> ا).
    4. Normalize Alef Maksura (Yaa) forms (ى -> ي).
    5. Normalize Teh Marbuta (ة -> ه).

    Args:
        text: The raw input Arabic text.

    Returns:
        The normalized text.
    """
    if not text:
        return ""
    try:
        # Apply normalizations in a sensible order
        processed_text = normalize_unicode(text)
        processed_text = dediac_ar(processed_text)
        processed_text = normalize_alef_ar(processed_text)
        processed_text = normalize_alef_maksura_ar(processed_text)
        processed_text = normalize_teh_marbuta_ar(processed_text)
        
        logger.debug(f"Normalized text: '{text}' -> '{processed_text}'")
        return processed_text
    except Exception as e:
        logger.error(f"Error normalizing text '{text}' using camel-tools: {e}", exc_info=True)
        return text # Return original text on error

def tokenize_arabic_text(text: str) -> list[str]:
    """
    Tokenizes Arabic text using CAMeL Tools simple word tokenizer.

    Args:
        text: The input text (ideally already normalized).

    Returns:
        A list of tokens.
    """
    if not text:
        return []
    try:
        tokens = simple_word_tokenize(text)
        logger.debug(f"Tokenized text '{text}' into: {tokens}")
        return tokens
    except Exception as e:
        logger.error(f"Error tokenizing text '{text}' using camel-tools: {e}", exc_info=True)
        return [] # Return empty list on error

def preprocess_text(text: str) -> list[str]:
    """
    Performs full preprocessing: normalization followed by tokenization using CAMeL Tools.

    Args:
        text: The raw input Arabic text.

    Returns:
        A list of normalized tokens.
    """
    normalized = normalize_arabic_text(text)
    tokens = tokenize_arabic_text(normalized)
    return tokens

# Example Usage can remain commented out or updated if needed
# if __name__ == "__main__":
#    ... 