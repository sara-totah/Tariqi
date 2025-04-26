"""Module for Named Entity Recognition and Classification using CAMeL Tools."""

import logging
import re
from typing import List, Tuple, Optional, Dict

from camel_tools.ner import NERecognizer
from camel_tools.utils.dediac import dediac_ar # May be needed if NER expects dediac input

# Assuming preprocessing functions are available
from .preprocessing import preprocess_text 
from app import schemas # Import the new schemas

# Configure logging
logger = logging.getLogger(__name__)

# Load the NER model once when the module is imported.
# This assumes the 'ner-arabert' model has been downloaded via 'camel_data -i ner-arabert'
# Handling potential errors during model loading.
try:
    logger.info("Loading CAMeL Tools NER model (ner-arabert)... This may take a moment.")
    # You might need to adjust the model path/name if it's not found automatically
    ner_model = NERecognizer.pretrained('arabert') 
    logger.info("CAMeL Tools NER model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load CAMeL Tools NER model: {e}", exc_info=True)
    ner_model = None # Set to None if loading failed

def _extract_entities_from_tokens(tokens: List[str]) -> List[Tuple[str, str]]:
    """Internal helper to run NER prediction on tokens."""
    if ner_model is None:
        logger.error("NER model is not loaded. Cannot extract entities.")
        return []
    if not tokens:
        return []
    try:
        # CAMeL Tools NER often expects pre-segmented sentences (list of words/tokens)
        # Some models might prefer dediacritized input, ensure preprocessing aligns
        # Let's assume the input tokens are already suitably preprocessed (Stage 2)
        
        # Predict tags for the given tokens
        # The predict_sentence method takes a list of strings (tokens)
        tags = ner_model.predict_sentence(tokens)
        
        # Combine tokens and tags
        entities = list(zip(tokens, tags))
        logger.debug(f"NER results for tokens '{tokens}': {entities}")
        return entities

    except Exception as e:
        logger.error(f"Error during NER prediction for tokens '{tokens}': {e}", exc_info=True)
        return []

def _process_ner_tags(tagged_tokens: List[Tuple[str, str]]) -> Dict[str, list]:
    """Processes raw (word, tag) NER output to group consecutive entities.
       Specifically looks for LOC and TIME tags.
    """
    extracted_info = {"locations": [], "times": []}
    current_entity_text = ""
    current_entity_label = None

    for token, tag in tagged_tokens:
        # CAMeL NER uses BIO tagging (B-Begin, I-Inside, O-Outside)
        tag_prefix = tag.split('-')[0] # B, I, or O
        tag_label = tag.split('-')[1] if '-' in tag else None # LOC, TIME, PER, ORG etc. or None if O

        if tag_prefix == 'B': # Start of a new entity
            # If we were tracking a previous entity, store it
            if current_entity_text and current_entity_label:
                if current_entity_label == 'LOC':
                    extracted_info["locations"].append(schemas.LocationInfo(text=current_entity_text.strip()))
                elif current_entity_label in ['TIME', 'DATE']: # Check for TIME or DATE
                    extracted_info["times"].append(schemas.TimeInfo(text=current_entity_text.strip()))
            # Start the new entity
            current_entity_text = token
            current_entity_label = tag_label
        elif tag_prefix == 'I' and tag_label == current_entity_label: # Continuation of the current entity
            current_entity_text += " " + token
        else: # Outside of an entity (O) or start of a different entity type
            # Store the completed entity if any
            if current_entity_text and current_entity_label:
                if current_entity_label == 'LOC':
                    extracted_info["locations"].append(schemas.LocationInfo(text=current_entity_text.strip()))
                elif current_entity_label in ['TIME', 'DATE']:
                     extracted_info["times"].append(schemas.TimeInfo(text=current_entity_text.strip()))
            # Reset for the next entity
            current_entity_text = ""
            current_entity_label = None

    # Add the last entity if it wasn't followed by O
    if current_entity_text and current_entity_label:
         if current_entity_label == 'LOC':
            extracted_info["locations"].append(schemas.LocationInfo(text=current_entity_text.strip()))
         elif current_entity_label in ['TIME', 'DATE']:
             extracted_info["times"].append(schemas.TimeInfo(text=current_entity_text.strip()))
             
    logger.debug(f"Processed NER tags into: {extracted_info}")
    return extracted_info

# --- Relevance Classification ---

# Simple keyword-based relevance classification
# Use NORMALIZED forms of keywords (ة -> ه, أ/إ/آ -> ا)
RELEVANT_KEYWORDS = [
    # Traffic / Congestion
    "ازمه", "ازدحام", "سير", "مرور", "خانقه", "عالق",
    # Accidents
    "حادث", "حوادث", "اصطدام", "انقلاب", "دهس",
    # Road closures / Conditions
    "شارع", "طريق", "مفرق", "دوار", "حاجز", "حواجز", "اغلاق", "مغلق", "مفتوح",
    "عسكري", "جيش", "شرطه", "تفتيش", "منع", "مركبات", "سيارات", 
    # Potential Locations (less reliable, but maybe helpful)
    "مدخل", "مخرج", "جسر", "نفق",
    # Specific event types mentioned in comments might be added here
]
# Pre-compile regex for efficiency
# Ensure regex uses normalized forms if matching against normalized text
RELEVANCE_REGEX = re.compile(r'\b(' + '|'.join(RELEVANT_KEYWORDS) + r')\b', re.IGNORECASE)

def classify_relevance(text: str, locations: List[schemas.LocationInfo]) -> bool:
    """Classifies if the text is relevant to road conditions/traffic.
       Simple rules: checks for keywords OR presence of a location.
    """
    if not text:
        return False
        
    # Rule 1: Check for keywords using regex
    if RELEVANCE_REGEX.search(text):
        logger.debug(f"Text classified as relevant based on keywords: '{text}'")
        return True
        
    # Rule 2: Consider relevant if a location was specifically identified by NER
    # (This might be too broad later, but a starting point)
    if locations:
         logger.debug(f"Text classified as relevant based on identified locations: '{text}'")
         return True

    logger.debug(f"Text classified as NOT relevant: '{text}'")
    return False

# --- Main Service Function ---

# Pre-compile regex for event types for efficiency
EVENT_REGEX_ACCIDENT = re.compile(r'\b(' + '|'.join(["حادث", "حوادث", "اصطدام", "انقلاب", "دهس"]) + r')\b', re.IGNORECASE)
EVENT_REGEX_TRAFFIC = re.compile(r'\b(' + '|'.join(["ازمه", "ازدحام", "خانقه"]) + r')\b', re.IGNORECASE)
EVENT_REGEX_BLOCKADE = re.compile(r'\b(' + '|'.join(["اغلاق", "مغلق", "حاجز", "حواجز"]) + r')\b', re.IGNORECASE)

def extract_and_classify(text: str) -> schemas.ExtractedReportInfo:
    """ 
    Main function to preprocess, extract entities, classify relevance, 
    and structure the information.
    """
    if not text:
        return schemas.ExtractedReportInfo(original_text="")
        
    # 1. Preprocess the text (normalize & tokenize)
    tokens = preprocess_text(text)
    # Reconstruct normalized text for relevance check and event type check
    normalized_text = " ".join(tokens)
    
    # 2. Extract Entities
    tagged_tokens = _extract_entities_from_tokens(tokens)
    
    # 3. Process Tags
    processed_entities = _process_ner_tags(tagged_tokens)
    locations = processed_entities.get("locations", [])
    times = processed_entities.get("times", [])
    
    # 4. Classify Relevance (using normalized text)
    is_relevant = classify_relevance(normalized_text, locations)
    
    # 5. Infer Event Type (Using regex on normalized text)
    event_type = None
    if is_relevant:
        if EVENT_REGEX_ACCIDENT.search(normalized_text):
            event_type = "accident"
        elif EVENT_REGEX_TRAFFIC.search(normalized_text):
             event_type = "traffic"
        elif EVENT_REGEX_BLOCKADE.search(normalized_text):
            event_type = "blockade"
        else:
            event_type = "other" # Default if relevant but no specific keyword matched
            
    # 6. Construct Output Schema
    result = schemas.ExtractedReportInfo(
        original_text=text,
        is_relevant=is_relevant,
        locations=locations,
        times=times,
        event_type=event_type
    )
    
    logger.info(f"Extraction & Classification result for '{text}': {result}")
    return result

# Example Usage (for testing/demonstration)
# if __name__ == "__main__":
#     sample_text_1 = "أزمة سير خانقة في شارع القدس بالقرب من رام الله."
#     sample_text_2 = "وقع حادث سير بين مركبتين على طريق نابلس السريع."
#     sample_text_3 = "صباح الخير يا جماعة"
#     sample_text_4 = "تفتيش على حاجز قلنديا"
#     
#     if ner_model:
#         print(f"\n--- Processing: {sample_text_1} ---")
#         info1 = extract_and_classify(sample_text_1)
#         print(info1)
#         
#         print(f"\n--- Processing: {sample_text_2} ---")
#         info2 = extract_and_classify(sample_text_2)
#         print(info2)
#         
#         print(f"\n--- Processing: {sample_text_3} ---")
#         info3 = extract_and_classify(sample_text_3)
#         print(info3)
#         
#         print(f"\n--- Processing: {sample_text_4} ---")
#         info4 = extract_and_classify(sample_text_4)
#         print(info4)
#         
#     else:
#         print("NER model could not be loaded. Examples cannot run.") 