import logging

from app.db import engine, Base
from app.models import RawGroupMessage, RawUserReport, VerifiedReport  # Import your models here

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database_tables():
    """Creates all defined tables in the database."""
    logger.info("Attempting to create database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tables created successfully (if they didn't exist)." + 
                    " Models included: RawGroupMessage, RawUserReport, VerifiedReport") # List models here
    except Exception as e:
        logger.error(f"Error creating tables: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    create_database_tables() 