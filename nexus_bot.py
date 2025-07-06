import logging
import sqlite3
import os
import uuid
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID")) # Ensure this is an integer
DB_NAME = "nexus_files.db"

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def db_connect():
    """Create a database connection."""
    conn = sqlite3.connect(DB_NAME)
    return conn

def create_table():
    """Create the hosted_files table if it doesn't exist."""
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hosted_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL UNIQUE,
            unique_token TEXT NOT NULL UNIQUE,
            original_filename TEXT,
            uploader_id INTEGER NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

async def start_command(update: Update, context: CallbackContext) -> None:
    """Handles the /start command and deep linking."""
    user = update.effective_user
    args = context.args

    if not args:
        await update.message.reply_html(
            rf"Hi {user.mention_html()}! This is Nexus File Hosting Bot.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("How to use", callback_data="help_general")]])
        )
        return

    # Deep linking: /start unique_token
    token = args[0]
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, original_filename FROM hosted_files WHERE unique_token = ?", (token,))
    result = cursor.fetchone()
    conn.close()

    if result:
        file_id, original_filename = result
        try:
            # For documents/general files
            await context.bot.send_document(chat_id=user.id, document=file_id, filename=original_filename)
        except Exception as e_doc:
            logger.error(f"Error sending document by file_id {file_id} for token {token}: {e_doc}")
            try:
                # Fallback for photos
                await context.bot.send_photo(chat_id=user.id, photo=file_id, caption=original_filename)
            except Exception as e_photo:
                logger.error(f"Error sending photo by file_id {file_id} for token {token}: {e_photo}")
                try:
                    # Fallback for videos
                    await context.bot.send_video(chat_id=user.id, video=file_id, caption=original_filename)
                except Exception as e_video:
                    logger.error(f"Error sending video by file_id {file_id} for token {token}: {e_video}")
                    try:
                        # Fallback for audio
                        await context.bot.send_audio(chat_id=user.id, audio=file_id, caption=original_filename)
                    except Exception as e_audio:
                        logger.error(f"Error sending audio by file_id {file_id} for token {token}: {e_audio}")
                        await update.message.reply_text("Sorry, I couldn't send this file. It might be a type I can't handle directly or it's no longer available.")
    else:
        await update.message.reply_text("Invalid or expired file link.")


async def help_command(update: Update, context: CallbackContext) -> None:
    """Displays help message."""
    await show_help_message(update.message.chat_id, context.bot)

async def show_help_message(chat_id: int, bot, message_id: int = None):
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

    if message_id:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=reply_markup)


async def button_callback_handler(update: Update, context: CallbackContext) -> None:
    """Handles button presses from inline keyboards."""
    query = update.callback_query
    await query.answer() # Acknowledge callback

    if query.data == "help_general":
        await show_help_message(query.message.chat_id, context.bot, query.message.message_id)
    elif query.data == "help_close":
        await query.edit_message_reply_markup(reply_markup=None) # Remove keyboard
        # Optionally, delete the help message or revert to a simpler start message
        # await query.delete_message()


async def handle_file(update: Update, context: CallbackContext) -> None:
    """Handles forwarded files from the admin."""
    user = update.effective_user

    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("Sorry, only the admin can upload files.")
        logger.warning(f"Unauthorized file upload attempt by user {user.id} ({user.username})")
        return

    message = update.message
    file_id = None
    original_filename = None

    if message.document:
        file_id = message.document.file_id
        original_filename = message.document.file_name
    elif message.photo:
        file_id = message.photo[-1].file_id # Get the largest photo
        original_filename = f"photo_{message.photo[-1].file_unique_id}.jpg"
    elif message.video:
        file_id = message.video.file_id
        original_filename = message.video.file_name if message.video.file_name else f"video_{message.video.file_unique_id}.mp4"
    elif message.audio:
        file_id = message.audio.file_id
        original_filename = message.audio.file_name if message.audio.file_name else f"audio_{message.audio.file_unique_id}.mp3"
    else:
        await update.message.reply_text("Unsupported file type. I can handle documents, photos, videos, and audio.")
        return

    if not file_id: # Should not happen if one of the above conditions met
        await update.message.reply_text("Could not get file information. Please try again.")
        return

    unique_token = str(uuid.uuid4().hex[:16]) # Shorter, still very unique token

    conn = db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO hosted_files (file_id, unique_token, original_filename, uploader_id) VALUES (?, ?, ?, ?)",
            (file_id, unique_token, original_filename, user.id)
        )
        conn.commit()
        bot_username = (await context.bot.get_me()).username
        share_link = f"https://t.me/{bot_username}?start={unique_token}"
        await update.message.reply_text(f"File stored! Your shareable link is:\n{share_link}")
        logger.info(f"File {original_filename} (ID: {file_id}) stored by admin {user.id}. Token: {unique_token}")
    except sqlite3.IntegrityError: # Should catch unique constraint violations
        # This could happen if Telegram reuses file_id for identical files for the same bot
        # Or, highly unlikely, a token collision.
        cursor.execute("SELECT unique_token FROM hosted_files WHERE file_id = ?", (file_id,))
        existing_token_row = cursor.fetchone()
        if existing_token_row:
            existing_token = existing_token_row[0]
            bot_username = (await context.bot.get_me()).username
            share_link = f"https://t.me/{bot_username}?start={existing_token}"
            await update.message.reply_text(f"This file seems to be already stored. Link:\n{share_link}")
        else:
            # This case means token collision, which is extremely rare with UUID hex.
            # Or some other integrity error.
            await update.message.reply_text("Error storing file. It might already exist or there was a database issue. Try renaming and re-uploading if it's a new file.")
            logger.error(f"Integrity error storing file_id {file_id}. Existing token found: {existing_token_row}")
    except Exception as e:
        logger.error(f"Error saving file to DB: {e}")
        await update.message.reply_text("An error occurred while saving the file information.")
    finally:
        conn.close()

def main() -> None:
    """Start the bot."""
    # Create db table if it doesn't exist
    create_table()

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in .env file!")
        return
    if not ADMIN_USER_ID:
        logger.error("ADMIN_USER_ID not found in .env file or is not a valid number!")
        return

    logger.info(f"Admin User ID set to: {ADMIN_USER_ID}")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Message handler for files (documents, photos, videos, audio)
    # Ensure it only triggers on private chats or DMs with the bot
    application.add_handler(MessageHandler(
        (filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO) & filters.ChatType.PRIVATE,
        handle_file
    ))

    # Callback query handler for buttons
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    logger.info("Bot starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
