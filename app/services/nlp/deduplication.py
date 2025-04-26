# app/services/nlp/deduplication.py

"""Module for validating and deduplicating extracted report information."""

import logging
from typing import List, Dict, Any # Use Any for now for complex structures
from datetime import datetime, timedelta # Ensure timedelta is imported
from statistics import mode as statistics_mode # For finding most common element
from collections import Counter

# Assuming ExtractedReportInfo schema is available
from app import schemas 
# Assuming preprocessing is needed for TF-IDF input
from .preprocessing import normalize_arabic_text 

# Import sklearn components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Configure logging
logger = logging.getLogger(__name__)

# --- Constants ---
# Default threshold, can be made configurable later
DEFAULT_SIMILARITY_THRESHOLD = 0.8 

# --- Placeholder Functions ---

def vectorize_texts(texts: List[str]) -> Any:
    """Computes TF-IDF vectors for a list of texts."""
    if not texts:
        logger.warning("Received empty list of texts for vectorization.")
        # Return an empty structure compatible with cosine_similarity input if needed
        # For now, let's return None or raise an error, caller should handle
        from scipy.sparse import csr_matrix
        return csr_matrix((0, 0)) # Return empty sparse matrix

    logger.info(f"Vectorizing {len(texts)} texts using TF-IDF...")
    # Using default analyzer='word', default token pattern.
    # Default TF-IDF settings are often a good starting point.
    # We are vectorizing normalized text passed from the main function.
    # Consider adding stop_words='arabic' if needed, but test impact.
    try:
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(texts)
        logger.info(f"TF-IDF vectorization complete. Matrix shape: {tfidf_matrix.shape}")
        # Return the TF-IDF matrix (usually a sparse matrix)
        return tfidf_matrix
    except Exception as e:
        logger.error(f"Error during TF-IDF vectorization: {e}", exc_info=True)
        # Return empty matrix on error
        from scipy.sparse import csr_matrix
        return csr_matrix((0, 0)) 

def calculate_similarity(tfidf_matrix: Any) -> Any:
    """Calculates the cosine similarity matrix from TF-IDF vectors."""
    logger.info("Calculating cosine similarity matrix...")
    similarity_matrix = cosine_similarity(tfidf_matrix)
    logger.info("Cosine similarity calculation complete.")
    return similarity_matrix

def group_similar_reports(
    reports: List[schemas.ExtractedReportInfo], 
    similarity_matrix: Any, 
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    time_window: timedelta = timedelta(hours=2) # Add time window parameter
) -> List[List[int]]: # Returns list of groups, each group is a list of report indices
    """Groups reports based on cosine similarity and time window."""
    logger.info(f"Grouping {len(reports)} reports with threshold {threshold}, time window {time_window}...")
    groups = []
    visited = set()
    num_reports = len(reports)

    # Sort reports by timestamp to process chronologically (optional but can help)
    # Assuming ExtractedReportInfo has a timestamp field populated!
    # If timestamps are missing, this sort will fail or be ineffective.
    try:
        # Create index mapping before sort, process based on sorted order
        report_indices_sorted = sorted(range(num_reports), key=lambda k: reports[k].report_timestamp or datetime.min)
    except AttributeError:
         logger.warning("Cannot sort reports by report_timestamp, ExtractedReportInfo might be missing 'report_timestamp'. Proceeding without sorting.")
         report_indices_sorted = list(range(num_reports))

    for i_idx in range(num_reports):
        i = report_indices_sorted[i_idx] # Get original index
        if i in visited:
            continue
            
        # Check timestamp of current report i
        timestamp_i = reports[i].report_timestamp
        if not timestamp_i:
            logger.warning(f"Report index {i} missing report_timestamp, cannot include in time-based groups.")
            continue # Skip reports without timestamps for grouping
            
        current_group_indices = [i] # Start a new group with the current report
        visited.add(i)
        
        # Compare with subsequent reports in the sorted list
        for j_idx in range(i_idx + 1, num_reports):
            j = report_indices_sorted[j_idx] # Get original index
            if j in visited:
                continue

            # Check timestamp of report j
            timestamp_j = reports[j].report_timestamp
            if not timestamp_j:
                continue # Skip reports without timestamps

            # 1. Check Time Window
            if abs(timestamp_i - timestamp_j) <= time_window:
                # 2. Check Similarity Threshold
                # Use original indices i and j for similarity matrix lookup
                if similarity_matrix[i, j] >= threshold:
                    # TODO: Add location checks here if desired
                    current_group_indices.append(j)
                    visited.add(j)
            # Optimization: If sorted, and j is outside time window, later reports will also be.
            # elif timestamp_j > timestamp_i + time_window:
            #     break # No need to check further for report i
        
        # Add the group (even if size 1, verification step will handle it)
        groups.append(current_group_indices)
            
    logger.info(f"Found {len(groups)} potential groups after time/similarity checks.")
    return groups

def verify_groups(
    groups: List[List[int]], 
    reports: List[schemas.ExtractedReportInfo]
) -> List[schemas.VerifiedIncident]: 
    """Applies verification criteria to groups of reports and aggregates info."""
    logger.info(f"Verifying {len(groups)} groups...")
    verified_incidents = []
    min_group_size_for_verification = 2 # Example criterion

    for group_indices in groups:
        if len(group_indices) >= min_group_size_for_verification:
            # This group is considered verified
            logger.info(f"Verified group found with indices: {group_indices}")
            
            # Aggregate information from the group
            group_reports = [reports[i] for i in group_indices]
            
            # Representative text: Use text from the first report in the group (by index)
            # Or could use the one with the earliest timestamp if available
            rep_text = reports[group_indices[0]].original_text 
            
            # Location: Find the most common location text
            all_locations = [loc.text for report in group_reports for loc in report.locations if report.locations]
            most_common_loc_text = None
            if all_locations:
                try:
                    most_common_loc_text = statistics_mode(all_locations)
                except statistics.StatisticsError: # Handle case where there is no unique mode
                    # Fallback: use the first location found
                    most_common_loc_text = all_locations[0]
            final_location = schemas.LocationInfo(text=most_common_loc_text) if most_common_loc_text else None
                
            # Time: Find the earliest timestamp/time info
            # For simplicity, use the TimeInfo from the report with the earliest timestamp
            earliest_report = min(group_reports, key=lambda r: r.report_timestamp or datetime.max)
            latest_report = max(group_reports, key=lambda r: r.report_timestamp or datetime.min)
            final_time = earliest_report.times[0] if earliest_report.times else None
            first_report_at = earliest_report.report_timestamp
            last_report_at = latest_report.report_timestamp

            # Event Type: Find the most common non-'other' event type
            event_types = [r.event_type for r in group_reports if r.event_type and r.event_type != 'other']
            most_common_event = None
            if event_types:
                 try:
                    most_common_event = statistics_mode(event_types)
                 except statistics.StatisticsError: # No unique mode
                     most_common_event = event_types[0] # Fallback
            # If only 'other' or None, keep it as None or 'other'
            final_event_type = most_common_event or next((r.event_type for r in group_reports if r.event_type), None)

            incident = schemas.VerifiedIncident(
                representative_text=rep_text,
                location=final_location,
                time=final_time, 
                event_type=final_event_type,
                contributing_report_count=len(group_indices),
                first_report_at=first_report_at,
                last_report_at=last_report_at
                # Add contributing_raw_report_ids if needed
            )
            verified_incidents.append(incident)
            logger.debug(f"Created verified incident: {incident}")

        else:
             logger.debug(f"Group {group_indices} did not meet verification criteria (size < {min_group_size_for_verification}).")

    logger.info(f"Created {len(verified_incidents)} verified incidents.")
    return verified_incidents

def process_batch_for_deduplication(reports: List[schemas.ExtractedReportInfo]) -> List[schemas.VerifiedIncident]: # Return type TBD
    """Main function to run the deduplication and verification pipeline on a batch of reports."""
    logger.info(f"Starting deduplication process for {len(reports)} reports.")
    if not reports:
        return []

    # 1. Extract text for vectorization (use normalized text for better results)
    # Assuming ExtractedReportInfo contains enough info or we can preprocess again.
    # For simplicity, let's use original_text and normalize it here.
    # A better approach might be to ensure Stage 3 output includes normalized text.
    texts_to_vectorize = [normalize_arabic_text(report.original_text) for report in reports]

    # 2. Vectorize
    tfidf_matrix = vectorize_texts(texts_to_vectorize)

    # 3. Calculate Similarity
    similarity_matrix = calculate_similarity(tfidf_matrix)

    # 4. Group Reports
    report_groups_indices = group_similar_reports(reports, similarity_matrix)

    # 5. Verify Groups
    verified_incidents = verify_groups(report_groups_indices, reports)

    logger.info("Deduplication process complete.")
    return verified_incidents

# --- Schema Definition (Placeholder - move to schemas.py later) ---
# Define schemas.VerifiedIncident here or import if defined elsewhere

# Example:
# class VerifiedIncident(schemas.BaseModel):
#     id: Optional[str] = None # Or UUID
#     representative_text: str
#     location: Optional[schemas.LocationInfo] = None
#     time: Optional[schemas.TimeInfo] = None
#     event_type: Optional[str] = None
#     contributing_report_ids: List[Any] # Store original report IDs (need schema update?)
#     created_at: Optional[datetime] = None 