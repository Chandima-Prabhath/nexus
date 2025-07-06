import logging
# Removed sqlite3 import
import os
import sys
import uuid
from typing import Optional, cast # cast might not be needed anymore
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message, User
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from telegram.constants import ParseMode
import supabase_utils # Import the new Supabase utility module

# Load environment variables. This is important for Supabase client in supabase_utils too.
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID_STR = os.getenv("ADMIN_USER_ID")

ADMIN_USER_ID: Optional[int] = None
if ADMIN_USER_ID_STR:
    try:
        ADMIN_USER_ID = int(ADMIN_USER_ID_STR)
    except ValueError:
        logging.error("ADMIN_USER_ID in .env is not a valid integer.")
        sys.exit(1)
else:
    logging.error("ADMIN_USER_ID not found in .env file.")
    sys.exit(1)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: CallbackContext) -> None:
    """Handles the /start command and deep linking."""
    assert update.message is not None, "update.message should not be None for CommandHandler"
    user = update.effective_user
    assert user is not None, "update.effective_user should not be None for CommandHandler"
    args = context.args

    if not args:
        await update.message.reply_html(
            rf"Hi {user.mention_html()}! This is Nexus File Hosting Bot.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("How to use", callback_data="help_general")]])
        )
        return

    token = args[0]
    file_record = supabase_utils.get_file_by_token(token)

    if file_record:
        # Supabase returns a dictionary
        tg_file_id = file_record.get("file_id")
        original_filename = file_record.get("original_filename")

        if not tg_file_id:
            logger.error(f"No file_id found in Supabase record for token {token}.")
            await update.message.reply_text("Error: File record is incomplete.")
            return

        try:
            # Consider storing file_type in DB to avoid this cascade
            await context.bot.send_document(chat_id=user.id, document=tg_file_id, filename=original_filename)
        except Exception:
            try:
                await context.bot.send_photo(chat_id=user.id, photo=tg_file_id, caption=original_filename)
            except Exception:
                try:
                    await context.bot.send_video(chat_id=user.id, video=tg_file_id, caption=original_filename)
                except Exception:
                    try:
                        await context.bot.send_audio(chat_id=user.id, audio=tg_file_id, caption=original_filename)
                    except Exception as e_final:
                        logger.error(f"All attempts to send file failed for token {token}, file_id {tg_file_id}: {e_final}")
                        await update.message.reply_text("Sorry, I couldn't send this file. It might be a type I can't handle or it's no longer available.")
    else:
        await update.message.reply_text("Invalid or expired file link.")


async def help_command(update: Update, context: CallbackContext) -> None:
    """Displays help message."""
    assert update.message is not None, "update.message should not be None for CommandHandler"
    # Ensure message.chat_id is used
    await show_help_message(update.message.chat_id, context.bot, message_id=None) # Pass message_id as None explicitly if new

async def show_help_message(chat_id: int, bot, message_id: Optional[int] = None) -> None: # Added bot type hint later if needed
    """Sends or edits the help message."""
    text = (
        "**Nexus File Hosting Bot Help**\n\n"
        "**For Admins:**\n"
        "1. Create a private Telegram channel.\n"
        "2. Add this bot to the channel as an administrator (optional, but helps if you want the bot to see messages without being explicitly tagged).\n"
        "3. Upload files to your private channel.\n"
        "4. Forward those files from the channel to me (the bot) in this private chat.\n"
        "5. I will reply with a unique shareable link for each file.\n\n"
        "**For Users:**\n"
        "Simply click on a shareable link provided by an admin. I will send you the file.\n\n"
        "**Commands:**\n"
        "/start - Welcome message or retrieve a file if a token is provided.\n"
        "/help - Shows this help message."
    )
    keyboard = [[InlineKeyboardButton("Close", callback_data="help_close")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if message_id: # If message_id is provided, edit the existing message
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    else: # Otherwise, send a new message
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def button_callback_handler(update: Update, context: CallbackContext) -> None:
    """Handles button presses from inline keyboards."""
    query = update.callback_query
    assert query is not None, "update.callback_query should not be None for CallbackQueryHandler"
    await query.answer()

    assert isinstance(query.message, Message), "query.message is not a Message instance or is None"

    if query.data == "help_general":
        # When "How to use" is clicked, edit the current message to show full help
        await show_help_message(query.message.chat_id, context.bot, query.message.message_id)
    elif query.data == "help_close":
        # When "Close" is clicked, remove the keyboard (or delete message)
        await query.edit_message_reply_markup(reply_markup=None)


async def handle_file(update: Update, context: CallbackContext) -> None:
    """Handles forwarded files from the admin."""
    assert update.message is not None, "update.message should not be None for MessageHandler"
    user = update.effective_user
    assert user is not None, "update.effective_user should not be None for MessageHandler"

    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("Sorry, only the admin can upload files.")
        logger.warning(f"Unauthorized file upload attempt by user {user.id} ({user.username})")
        return

    message = update.message
    tg_file_id: Optional[str] = None # Renamed to avoid confusion with db id
    original_filename: Optional[str] = None

    if message.document:
        tg_file_id = message.document.file_id
        original_filename = message.document.file_name
    elif message.photo:
        tg_file_id = message.photo[-1].file_id
        original_filename = f"photo_{message.photo[-1].file_unique_id}.jpg"
    elif message.video:
        tg_file_id = message.video.file_id
        original_filename = message.video.file_name if message.video.file_name else f"video_{message.video.file_unique_id}.mp4"
    elif message.audio:
        tg_file_id = message.audio.file_id
        original_filename = message.audio.file_name if message.audio.file_name else f"audio_{message.audio.file_unique_id}.mp3"
    else:
        await update.message.reply_text("Unsupported file type received despite filters. Please report this.")
        return

    if not tg_file_id:
        await update.message.reply_text("Could not get file information. Please try again.")
        return

    # Check if file already exists in Supabase by Telegram's file_id
    existing_file = supabase_utils.get_file_by_telegram_id(tg_file_id)
    bot_username = (await context.bot.get_me()).username

    if existing_file:
        existing_token = existing_file.get("unique_token")
        share_link = f"https://t.me/{bot_username}?start={existing_token}"
        await update.message.reply_text(f"This file seems to be already stored. Link:\n{share_link}")
        return

    # If not existing, generate a new token and add record
    unique_token = str(uuid.uuid4().hex[:16])
    added_record = supabase_utils.add_file_record(
        file_id=tg_file_id,
        unique_token=unique_token,
        original_filename=original_filename,
        uploader_id=user.id
    )

    if added_record:
        share_link = f"https://t.me/{bot_username}?start={unique_token}"
        await update.message.reply_text(f"File stored! Your shareable link is:\n{share_link}")
        logger.info(f"File {original_filename} (TG_ID: {tg_file_id}) stored by admin {user.id}. Token: {unique_token}")
    else:
        # This means insertion failed, possibly due to a unique token collision (extremely rare) or other DB error
        await update.message.reply_text("Error storing file. There might have been a database issue or a rare token collision. Please try again.")
        logger.error(f"Failed to add file record to Supabase for TG_ID {tg_file_id}. Token collision for {unique_token} or other DB error.")


def main() -> None:
    """Start the bot."""
    if not supabase_utils.supabase:
        logger.critical("Supabase client failed to initialize. Bot cannot start.")
        sys.exit(1)

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in .env file!")
        sys.exit(1)

    logger.info(f"Admin User ID set to: {ADMIN_USER_ID}")
    logger.info("Supabase client seems okay. Bot is attempting to start.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(
        (filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO) & filters.ChatType.PRIVATE,
        handle_file
    ))
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    logger.info("Bot starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
