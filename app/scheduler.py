"""Module for scheduling background tasks, like the verification pipeline."""

import logging
import time
import sys
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy.orm import Session

# Ensure app path is available for imports if running scheduler directly
# This might be needed if running `python app/scheduler.py` from the root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.verification_service import run_verification_pipeline
from app.db import get_db, SessionLocal # Import SessionLocal to create session if needed
from app.settings import settings # Import settings for interval

# Configure logging
LOG_LEVEL = os.getenv("SCHEDULER_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_pipeline_job():
    """Job function that gets a DB session and runs the verification pipeline."""
    logger.info("Scheduler triggered: Running verification pipeline job...")
    db: Session | None = None
    try:
        # Get a new DB session for this job run
        db = SessionLocal() 
        run_verification_pipeline(db)
        logger.info("Verification pipeline job finished successfully.")
    except Exception as e:
        logger.error(f"Error during scheduled verification pipeline run: {e}", exc_info=True)
    finally:
        # Ensure session is closed
        if db:
            db.close()
            logger.debug("Database session closed for pipeline job.")

if __name__ == "__main__":
    logger.info("Initializing scheduler...")
    scheduler = BlockingScheduler(timezone="UTC") # Use UTC timezone

    # Get interval from settings, default to 5 minutes if not set or invalid
    try:
        interval_minutes = int(settings.pipeline_run_interval_minutes)
        if interval_minutes <= 0:
             raise ValueError("Interval must be positive")
    except (AttributeError, ValueError, TypeError):
        logger.warning("Invalid or missing PIPELINE_RUN_INTERVAL_MINUTES setting. Defaulting to 5 minutes.")
        interval_minutes = 5
        
    logger.info(f"Scheduling verification pipeline job to run every {interval_minutes} minutes.")
    scheduler.add_job(
        run_pipeline_job, 
        'interval', 
        minutes=interval_minutes, 
        id='verification_pipeline_job', # Give the job an ID
        replace_existing=True
    )

    # Add other scheduled jobs here if needed
    
    try:
        logger.info("Starting scheduler. Press Ctrl+C to exit.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
        scheduler.shutdown() 