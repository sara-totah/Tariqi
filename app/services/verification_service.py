"""
Service responsible for orchestrating the incident verification pipeline.

Fetches raw data, preprocesses, extracts info, deduplicates, verifies,
and stores verified incidents.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # Import SQLAlchemyError
from typing import List, Union

from app import models, schemas # Import schemas
from app.services.nlp.entity_extraction import extract_and_classify # Import extraction/classification function
from app.services.nlp.deduplication import process_batch_for_deduplication # Import deduplication function
from app.services.storage_service import save_verified_incidents_batch # Import storage function
# from app.db import get_db

logger = logging.getLogger(__name__)

def _fetch_unprocessed_reports(db: Session, limit: int = 100) -> List[Union[models.RawGroupMessage, models.RawUserReport]]:
    """Fetches a batch of unprocessed reports from the database."""
    group_messages = db.query(models.RawGroupMessage).filter(models.RawGroupMessage.processed == False).limit(limit // 2).all()
    user_reports = db.query(models.RawUserReport).filter(models.RawUserReport.processed == False).limit(limit // 2).all()
    # Combine and potentially sort by timestamp if needed, though processing order might not strictly matter here
    return group_messages + user_reports

def run_verification_pipeline(db: Session):
    """
    Runs the full incident verification pipeline.

    1. Fetches unprocessed raw reports.
    2. Preprocesses text.
    3. Extracts entities and classifies relevance.
    4. Deduplicates reports and verifies incidents.
    5. Stores verified incidents.
    6. Marks raw reports as processed.
    """
    logger.info("Starting verification pipeline run...")

    # --- 1. Fetch Unprocessed Reports ---
    raw_reports = _fetch_unprocessed_reports(db)
    logger.info(f"Fetched {len(raw_reports)} unprocessed reports.")
    if not raw_reports:
        logger.info("No unprocessed reports found. Pipeline run finished.")
        return

    # Store reports in a map for later reference (e.g., marking as processed)
    report_map = {report.id: report for report in raw_reports}

    # --- 2. Extract Entities & Classify ---
    # This step now includes preprocessing internally
    logger.info(f"Extracting entities and classifying relevance for {len(raw_reports)} reports...")
    extracted_info_list: List[schemas.ExtractedReportInfo] = []
    for report in raw_reports:
        report_text = report.text or "" # Handle None text
        if not report_text.strip():
            logger.debug(f"Skipping report ID {report.id} due to empty text.")
            continue # Skip reports with no text content

        extracted_data = extract_and_classify(report_text)
        # Attach the original report ID for linking if needed later
        extracted_data.original_report_id = report.id 
        # Attach the original report timestamp
        extracted_data.report_timestamp = report.timestamp
        extracted_info_list.append(extracted_data)
        
        # Optional: Log irrelevant reports?
        # if not extracted_data.is_relevant:
        #     logger.debug(f"Report ID {report.id} classified as irrelevant.")

    logger.info(f"Entity extraction and classification complete. Found {len(extracted_info_list)} reports with text.")

    # Filter out irrelevant reports before deduplication
    relevant_reports = [info for info in extracted_info_list if info.is_relevant]
    logger.info(f"Proceeding with {len(relevant_reports)} relevant reports for deduplication.")
    
    if not relevant_reports:
        logger.info("No relevant reports found to deduplicate. Skipping deduplication and storage.")
        # Still need to mark fetched reports as processed below
        verified_incidents = []
    else:
        # --- 3. Deduplicate & Verify (using Stage 4 service) ---
        logger.info(f"Starting deduplication and verification for {len(relevant_reports)} reports...")
        verified_incidents = process_batch_for_deduplication(relevant_reports)
        logger.info(f"Deduplication complete. Found {len(verified_incidents)} verified incidents.")

    # --- 4. Store Verified Incidents (using Stage 5 service) ---
    if verified_incidents:
        logger.info(f"Attempting to save {len(verified_incidents)} verified incidents...")
        saved_count = save_verified_incidents_batch(db=db, incidents=verified_incidents)
        logger.info(f"Successfully saved {saved_count} verified incidents to the database.")
    else:
        logger.info("No verified incidents to save.")

    # --- 5. Mark Raw Reports as Processed ---
    processed_report_ids = list(report_map.keys())
    if not processed_report_ids:
        logger.info("No reports were fetched, skipping marking step.")
    else:
        logger.info(f"Attempting to mark {len(processed_report_ids)} raw reports as processed...")
        try:
            # Update RawGroupMessage table
            db.query(models.RawGroupMessage)\
                .filter(models.RawGroupMessage.id.in_(processed_report_ids))\
                .update({models.RawGroupMessage.processed: True}, synchronize_session=False)

            # Update RawUserReport table
            db.query(models.RawUserReport)\
                .filter(models.RawUserReport.id.in_(processed_report_ids))\
                .update({models.RawUserReport.processed: True}, synchronize_session=False)

            db.commit()
            logger.info(f"Successfully marked {len(processed_report_ids)} reports as processed.")
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error marking reports as processed: {e}", exc_info=True)
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error marking reports as processed: {e}", exc_info=True)

    logger.info("Verification pipeline run completed.")

# Example usage or trigger mechanism could go here or in a separate scheduler module
# if __name__ == "__main__":
#     db_session = next(get_db())
#     run_verification_pipeline(db_session) 