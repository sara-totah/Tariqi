from fastapi import FastAPI, Request, HTTPException, Depends, Body
import logging
import json
from contextlib import asynccontextmanager # Added for lifespan
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError, Json

# Import local modules
from app import schemas
from app import models
from app.db import get_db
from app.services.bot.utils import set_telegram_webhook # Import the webhook utility

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    logger.info("Application startup: Setting Telegram webhook...")
    success = await set_telegram_webhook()
    if not success:
        # Decide if failure to set webhook should prevent startup
        # For now, just log an error and continue.
        logger.error("Failed to set Telegram webhook on startup. Check settings and connectivity.")
    # App is ready to serve requests
    yield
    # Code to run on shutdown (optional)
    logger.info("Application shutdown.")

app = FastAPI(
    title="Tariqi Bot API",
    description="API for receiving user reports from Telegram Bot",
    version="0.1.0",
    lifespan=lifespan # Register the lifespan context manager
)

@app.get("/")
async def read_root():
    """Root endpoint for basic health check."""
    logger.debug("Health check endpoint '/' called")
    return {"status": "ok", "message": "Tariqi Bot API is running"}

# We accept raw JSON to handle potential validation errors explicitly
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint to receive raw Telegram updates, validate them, and save user reports.
    Handles validation errors explicitly for logging.
    """
    try:
        raw_body = await request.json()
        logger.debug(f"Raw update received: {raw_body}") # Log raw for debugging if needed
        
        # Attempt to validate the raw body using the Pydantic model
        update = schemas.TelegramUpdate.model_validate(raw_body)
        logger.info(f"Successfully validated Telegram update ID: {update.update_id}")

    except json.JSONDecodeError:
        logger.error("Failed to decode JSON body from webhook request.")
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except ValidationError as val_err:
        logger.error(f"Validation error receiving Telegram update: {val_err}", exc_info=True)
        # Pydantic's ValidationError includes detailed error info
        raise HTTPException(status_code=422, detail=f"Validation Error: {val_err}")
    except Exception as e:
        # Catch unexpected errors during initial processing/validation
        logger.error(f"Unexpected error processing webhook request body: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Error processing request body")

    # Proceed only if validation passed and we have a message with user info
    if not update.message or not update.message.from_user:
        logger.info(f"Update ID {update.update_id} is not a relevant message type or is missing user info. Skipping.")
        return {"status": "skipped", "reason": "Not a new message or missing user info"}

    # Extract data from validated Pydantic models
    message = update.message
    user = message.from_user
    
    # Create DB model instance
    db_report = models.RawUserReport(
        user_id=user.id,
        message_id=message.message_id,
        text=message.text,
        raw_payload=update.model_dump_json(by_alias=True), # Store validated model as JSON
        timestamp=message.date
    )

    try:
        logger.debug(f"Attempting to add report to DB session: {db_report}")
        db.add(db_report)
        logger.debug("Attempting to commit DB session.")
        db.commit()
        logger.debug("Attempting to refresh DB object.")
        db.refresh(db_report)
        logger.info(f"Successfully saved user report with DB ID: {db_report.id} from user {db_report.user_id}")
        return {"status": "saved", "report_id": db_report.id}
    except ValidationError as val_err_db:
        # Log unexpected validation errors during DB interaction/serialization
        db.rollback()
        logger.error(f"**Unexpected ValidationError during DB operation** for update ID {update.update_id}: {val_err_db}", exc_info=True)
        # Still treat this as a server error, as it shouldn't happen here
        raise HTTPException(status_code=500, detail="Internal server error during data processing")
    except SQLAlchemyError as db_err:
        db.rollback()
        logger.error(f"Database error saving report for update ID {update.update_id} from user {user.id}: {db_err}", exc_info=True)
        # Re-raise as 500 Internal Server Error
        raise HTTPException(status_code=500, detail="Database error saving report")
    except Exception as e:
        db.rollback()
        # Catch other potential errors during DB interaction
        logger.error(f"Unexpected error saving report for update ID {update.update_id} from user {user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error saving report")

# --- Optional: Add Uvicorn runner for local testing --- 
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000) 