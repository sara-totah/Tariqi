"""Handlers for Telegram bot commands."""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackContext
from telegram.constants import ParseMode
from typing import List
from sqlalchemy.orm import Session

from app.db import get_db # Import get_db
from app.services.storage_service import get_latest_verified_incidents, search_verified_incidents_by_location # Import query function and search function
from app.schemas import VerifiedIncident # Import schema for type hint

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    if not user:
        logger.warning("Cannot get user from update in start command")
        return
        
    welcome_message = (
        f"أهلاً بك يا {user.mention_html()} في بوت طريقي!\n\n"
        f"أنا هنا لمساعدتك في معرفة آخر تحديثات الطرق في فلسطين.\n"
        f"يمكنك إرسال أي معلومة لديك عن حالة الطرق وسأقوم بتحليلها.\n\n"
        f"استخدم /help لعرض الأوامر المتاحة."
    )
    if update.message:
        await update.message.reply_html(welcome_message)
    else:
        logger.warning("Update does not have a message attribute in start command")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    help_text = (
        "الأوامر المتاحة:\n"
        "/start - بدء الحوار وعرض رسالة الترحيب\n"
        "/help - عرض هذه الرسالة\n"
        # "/check <موقع> - للبحث عن آخر تحديثات لموقع معين\n"  # Example future command
        # "/latest - لعرض آخر تحديثات تم التحقق منها\n"     # Example future command
        "\n"
        "يمكنك أيضاً إرسال رسالة نصية مباشرة تحتوي على وصف لحالة طريق أو حادث."
    )
    if update.message:
        await update.message.reply_text(help_text)
    else:
        logger.warning("Update does not have a message attribute in help_command")

def format_incident(incident: VerifiedIncident) -> str:
    """Formats a single verified incident for display in Telegram."""
    lines = []
    lines.append(f"📍 *الموقع:* {incident.location.text if incident.location else 'غير محدد'}")
    if incident.event_type:
        lines.append(f"🏷️ *نوع الحدث:* {incident.event_type}") # Consider mapping types to Arabic later
    if incident.time:
        lines.append(f"⏰ *الوقت:* {incident.time.text}")
    lines.append(f"📝 *الوصف:* {incident.representative_text}")
    if incident.last_report_at:
        # Format timestamp nicely
        last_time_str = incident.last_report_at.strftime("%Y-%m-%d %H:%M") 
        lines.append(f"🕒 *آخر تحديث:* {last_time_str}")
    lines.append(f"📊 *عدد البلاغات:* {incident.contributing_report_count}")
    return "\n".join(lines)

async def latest_incidents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /latest command, fetching and displaying recent incidents."""
    logger.info("Received /latest command")
    num_incidents = 5
    sent_message = None
    if update.message:
        message_text = f"⏳ جاري البحث عن آخر {num_incidents} تحديثات مؤكدة..."
        sent_message = await update.message.reply_text(message_text)
    else:
        logger.warning("/latest command received without update.message")
        return
        
    if not sent_message: # Ensure message was sent
        logger.error("Failed to send initial status message for /latest")
        return
        
    db: Session | None = None
    incidents: List[VerifiedIncident] = []
    reply_text = ""
    try:
        db = next(get_db()) # Get session
        incidents = get_latest_verified_incidents(db=db, limit=num_incidents)
        
        if not incidents:
            reply_text = "لم يتم العثور على تحديثات مؤكدة مؤخراً."
        else:
            reply_parts = [f"✅ آخر {len(incidents)} تحديثات مؤكدة:"]
            for i, incident in enumerate(incidents):
                reply_parts.append(f"\n--- {i+1} ---\n{format_incident(incident)}")
            reply_text = "\n".join(reply_parts)
            
    except Exception as e:
        logger.error(f"Error getting DB session or fetching latest incidents: {e}", exc_info=True)
        reply_text = "حدث خطأ أثناء البحث عن التحديثات. الرجاء المحاولة لاحقاً."
    finally:
        if db: # Close session if obtained
            db.close()
            logger.debug("Database session closed for /latest command.")
            
    # Edit the initial message with the results or error text
    try:
        await context.bot.edit_message_text(
            chat_id=sent_message.chat_id, 
            message_id=sent_message.message_id, 
            text=reply_text,
            parse_mode=ParseMode.MARKDOWN_V2 # Use MarkdownV2
        )
    except Exception as edit_err: # Catch potential formatting errors or other issues
        logger.error(f"Error editing message for /latest results: {edit_err}", exc_info=True)
        try:
            # Fallback to plain text if Markdown fails
            plain_text_fallback = ""
            if incidents: # Generate fallback only if incidents were fetched
                 plain_text_fallback = "\n".join([f"- {inc.representative_text}" for inc in incidents])
                 reply_text = "حدث خطأ في عرض النتائج، إليك النص الأساسي:\n" + plain_text_fallback
            # Use the existing error message if incidents weren't fetched
            
            await context.bot.edit_message_text(
                chat_id=sent_message.chat_id, 
                message_id=sent_message.message_id, 
                text=reply_text
            )
        except Exception as fallback_err:
             logger.error(f"Failed to send fallback message for /latest: {fallback_err}", exc_info=True)
             # Cannot communicate error back to user easily here

async def check_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /check command, searching for incidents by location."""
    if not update.message or not update.message.text:
        logger.warning("/check command received without message text")
        return

    # Extract query from command arguments
    if context.args:
        location_query = " ".join(context.args)
        logger.info(f"Received /check command with location query: '{location_query}'")
    else:
        await update.message.reply_text(
            "الرجاء تحديد الموقع بعد الأمر. مثال: `/check رام الله`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    limit = 3 # Show fewer results for specific searches
    message_text = f"⏳ جاري البحث عن تحديثات مؤكدة للموقع: `{location_query}`..."
    sent_message = await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN_V2)

    if not sent_message: 
        logger.error(f"Failed to send initial status message for /check {location_query}")
        return

    db: Session | None = None
    incidents: List[VerifiedIncident] = []
    reply_text = ""
    try:
        db = next(get_db())
        incidents = search_verified_incidents_by_location(
            db=db, location_query=location_query, limit=limit
        )
        
        if not incidents:
            reply_text = f"لم يتم العثور على تحديثات مؤكدة للموقع: `{location_query}`"
        else:
            reply_parts = [f"✅ {len(incidents)} تحديثات تم العثور عليها للموقع `{location_query}`:"]
            for i, incident in enumerate(incidents):
                reply_parts.append(f"\n--- {i+1} ---\n{format_incident(incident)}")
            reply_text = "\n".join(reply_parts)
            
    except Exception as e:
        logger.error(f"Error searching incidents for location '{location_query}': {e}", exc_info=True)
        reply_text = "حدث خطأ أثناء البحث عن التحديثات. الرجاء المحاولة لاحقاً."
    finally:
        if db:
            db.close()
            logger.debug(f"Database session closed for /check {location_query} command.")

    # Edit the initial message
    try:
        # Escape markdown characters in the final reply_text before sending
        # Note: format_incident already uses markdown, so we only need to escape the query part if needed?
        # For simplicity, let's assume format_incident handles its internal escaping if necessary.
        # We might need a more robust escaping mechanism if user query can break markdown.
        await context.bot.edit_message_text(
            chat_id=sent_message.chat_id,
            message_id=sent_message.message_id,
            text=reply_text,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as edit_err:
        logger.error(f"Error editing message for /check results: {edit_err}", exc_info=True)
        try:
            plain_text_fallback = ""
            if incidents:
                plain_text_fallback = "\n".join([f"- {inc.representative_text}" for inc in incidents])
                reply_text = f"حدث خطأ في عرض النتائج للموقع {location_query}، إليك النص الأساسي:\n" + plain_text_fallback
            
            await context.bot.edit_message_text(
                chat_id=sent_message.chat_id,
                message_id=sent_message.message_id,
                text=reply_text # Send plain text on error
            )
        except Exception as fallback_err:
            logger.error(f"Failed to send fallback message for /check: {fallback_err}", exc_info=True)

# Add more command handlers here later 