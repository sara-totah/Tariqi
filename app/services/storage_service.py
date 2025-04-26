"""Service for saving processed data to the database."""

import logging
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app import models
from app import schemas

# Configure logging
logger = logging.getLogger(__name__)

def save_verified_incident(db: Session, incident: schemas.VerifiedIncident) -> models.VerifiedReport | None:
    """Saves a single verified incident to the database."""
    logger.debug(f"Attempting to save verified incident ID {incident.id}")
    try:
        # Map schema to model
        db_report = models.VerifiedReport(
            id=incident.id,
            representative_text=incident.representative_text,
            location_text=incident.location.text if incident.location else None,
            time_text=incident.time.text if incident.time else None,
            event_type=incident.event_type,
            contributing_report_count=incident.contributing_report_count,
            first_report_at=incident.first_report_at,
            last_report_at=incident.last_report_at
            # db_created_at is handled by server_default
        )
        db.add(db_report)
        db.commit()
        db.refresh(db_report)
        logger.info(f"Successfully saved verified incident ID {db_report.id}")
        return db_report
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error saving verified incident ID {incident.id}: {e}", exc_info=True)
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error saving verified incident ID {incident.id}: {e}", exc_info=True)
        return None

def save_verified_incidents_batch(db: Session, incidents: List[schemas.VerifiedIncident]) -> int:
    """Saves a batch of verified incidents to the database.

    Returns:
        The number of incidents successfully saved.
    """
    saved_count = 0
    logger.info(f"Attempting to save batch of {len(incidents)} verified incidents.")
    # Consider using bulk insert methods for very large batches if performance is critical
    # For now, iterate and save individually with error handling per item
    for incident in incidents:
        db_report = models.VerifiedReport(
             id=incident.id,
             representative_text=incident.representative_text,
             location_text=incident.location.text if incident.location else None,
             time_text=incident.time.text if incident.time else None,
             event_type=incident.event_type,
             contributing_report_count=incident.contributing_report_count,
             first_report_at=incident.first_report_at,
             last_report_at=incident.last_report_at
        )
        db.add(db_report)
        # Commit per item or less frequently? For simplicity, commit per item
        # but handle potential rollback without losing the whole batch.
        try:
            db.commit()
            # db.refresh(db_report) # Refresh might be less critical in batch
            saved_count += 1
            logger.debug(f"Successfully saved verified incident ID {db_report.id} in batch.")
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error saving verified incident ID {incident.id} in batch: {e}", exc_info=True)
            # Continue with the next item in the batch
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error saving verified incident ID {incident.id} in batch: {e}", exc_info=True)
            # Continue with the next item

    logger.info(f"Successfully saved {saved_count} out of {len(incidents)} incidents in batch.")
    return saved_count

def get_latest_verified_incidents(db: Session, limit: int = 5) -> List[schemas.VerifiedIncident]:
    """Fetches the latest verified incidents from the database.

    Args:
        db: The database session.
        limit: The maximum number of incidents to return.

    Returns:
        A list of VerifiedIncident schema objects.
    """
    logger.info(f"Fetching latest {limit} verified incidents...")
    try:
        db_reports = db.query(models.VerifiedReport)\
                      .order_by(models.VerifiedReport.db_created_at.desc())\
                      .limit(limit)\
                      .all()
        
        # Convert model instances to Pydantic schemas
        incidents = [
            schemas.VerifiedIncident(
                id=report.id,
                representative_text=report.representative_text,
                location=schemas.LocationInfo(text=report.location_text) if report.location_text else None,
                time=schemas.TimeInfo(text=report.time_text) if report.time_text else None,
                event_type=report.event_type,
                contributing_report_count=report.contributing_report_count,
                first_report_at=report.first_report_at,
                last_report_at=report.last_report_at,
                db_created_at=report.db_created_at # Include creation time if needed
            )
            for report in db_reports
        ]
        logger.info(f"Successfully fetched {len(incidents)} incidents.")
        return incidents
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching latest incidents: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching latest incidents: {e}", exc_info=True)
        return []

def search_verified_incidents_by_location(
    db: Session, 
    location_query: str, 
    limit: int = 5
) -> List[schemas.VerifiedIncident]:
    """Searches for verified incidents matching a location query string.

    Performs a case-insensitive search on the location_text field.
    Orders results by recency (db_created_at desc).

    Args:
        db: The database session.
        location_query: The search string provided by the user.
        limit: The maximum number of incidents to return.

    Returns:
        A list of matching VerifiedIncident schema objects.
    """
    if not location_query:
        logger.warning("Received empty location_query for search.")
        return []
        
    search_term = f"%{location_query.strip().lower()}%" # Prepare for case-insensitive LIKE
    logger.info(f"Searching for verified incidents with location like '{search_term}' (limit: {limit})...")
    
    try:
        db_reports = db.query(models.VerifiedReport)\
                      .filter(models.VerifiedReport.location_text.ilike(search_term))\
                      .order_by(models.VerifiedReport.db_created_at.desc())\
                      .limit(limit)\
                      .all()
        
        # Convert model instances to Pydantic schemas
        incidents = [
            schemas.VerifiedIncident(
                id=report.id,
                representative_text=report.representative_text,
                location=schemas.LocationInfo(text=report.location_text) if report.location_text else None,
                time=schemas.TimeInfo(text=report.time_text) if report.time_text else None,
                event_type=report.event_type,
                contributing_report_count=report.contributing_report_count,
                first_report_at=report.first_report_at,
                last_report_at=report.last_report_at,
                db_created_at=report.db_created_at
            )
            for report in db_reports
        ]
        logger.info(f"Found {len(incidents)} incidents matching location query '{location_query}'.")
        return incidents
    except SQLAlchemyError as e:
        logger.error(f"Database error searching incidents by location '{location_query}': {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Unexpected error searching incidents by location '{location_query}': {e}", exc_info=True)
        return [] 