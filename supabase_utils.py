import os
import logging
from typing import Optional, List, Dict, Any
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file for Supabase credentials
load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Supabase client
# These environment variables are expected to be set by the user.
SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
SUPABASE_KEY: Optional[str] = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")
    # You might want to raise an exception or handle this more gracefully
    # depending on how the application should behave if Supabase is not configured.
    supabase: Optional[Client] = None
else:
    try:
        supabase: Optional[Client] = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        supabase = None

TABLE_NAME = "hosted_files"

# Note: Table creation and schema management are typically done via Supabase dashboard or SQL migrations.
# The `create_table_if_not_exists` function is removed as it's not standard practice with Supabase client lib.
# Users should ensure the 'hosted_files' table exists with the correct schema in their Supabase project.
# Schema Reminder:
# - id: BIGINT (Primary Key, auto-incrementing, managed by Supabase)
# - file_id: TEXT (Should be unique)
# - unique_token: TEXT (Should be unique)
# - original_filename: TEXT
# - uploader_id: BIGINT (or INTEGER)
# - uploaded_at: TIMESTAMPTZ (Default: now())


def get_all_files(search_term: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches all files, optionally filtered by a search term on original_filename."""
    if not supabase:
        logger.error("Supabase client not initialized. Cannot fetch files.")
        return []
    try:
        query = supabase.table(TABLE_NAME).select("*").order("uploaded_at", desc=True)
        if search_term:
            # Using 'ilike' for case-insensitive search. 'like' is case-sensitive.
            query = query.ilike("original_filename", f"%{search_term}%")

        response = query.execute()

        if response.data:
            return response.data
        elif response.error:
            logger.error(f"Error fetching files from Supabase: {response.error}")
            return []
        return [] # No data and no error means empty list
    except Exception as e:
        logger.error(f"Exception fetching files from Supabase: {e}")
        return []

def delete_file_by_id(db_id: int) -> bool:
    """Deletes a file record from the database by its primary key (id)."""
    if not supabase:
        logger.error("Supabase client not initialized. Cannot delete file.")
        return False
    try:
        response = supabase.table(TABLE_NAME).delete().eq("id", db_id).execute()
        if response.error:
            logger.error(f"Error deleting file with id {db_id} from Supabase: {response.error}")
            return False
        # Supabase delete typically returns data of the deleted rows.
        # If data is present and no error, it means deletion was successful.
        # The number of deleted rows isn't directly in response.data for delete in the same way as select.
        # We might need to check if response.data is not empty or if there's a count attribute.
        # For now, if no error, assume success. A more robust check might be needed based on API version.
        # Typically, if `execute()` doesn't raise an exception and there's no `response.error`, it's good.
        # The Postgrest response for delete usually includes the deleted items in `data`.
        return True # Assuming success if no error.
    except Exception as e:
        logger.error(f"Exception deleting file with id {db_id} from Supabase: {e}")
        return False

def add_file_record(file_id: str, unique_token: str, original_filename: Optional[str], uploader_id: int) -> Optional[Dict[str, Any]]:
    """Adds a new file record to the database."""
    if not supabase:
        logger.error("Supabase client not initialized. Cannot add file record.")
        return None
    try:
        # `uploaded_at` will be set by default in Supabase if schema is configured with `now()`
        data_to_insert = {
            "file_id": file_id,
            "unique_token": unique_token,
            "original_filename": original_filename,
            "uploader_id": uploader_id
        }
        response = supabase.table(TABLE_NAME).insert(data_to_insert).execute()

        if response.data:
            logger.info(f"File record added to Supabase: {response.data[0]}")
            return response.data[0]
        elif response.error:
            logger.error(f"Error adding file record to Supabase: {response.error}")
            # Specific check for unique constraint violation if possible (error message parsing)
            # Supabase errors for unique violations usually have code "23505"
            if response.error.code == "23505":
                 logger.warning(f"Unique constraint violation for file_id '{file_id}' or token '{unique_token}'.")
            return None
        return None
    except Exception as e:
        logger.error(f"Exception adding file record to Supabase: {e}")
        return None

def get_file_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Retrieves a file record by its unique_token."""
    if not supabase:
        logger.error("Supabase client not initialized. Cannot get file by token.")
        return None
    try:
        response = supabase.table(TABLE_NAME).select("*").eq("unique_token", token).maybe_single().execute()
        if response.data:
            return response.data
        elif response.error:
            logger.error(f"Error fetching file by token '{token}' from Supabase: {response.error}")
            return None
        return None # No data, no error (maybe_single correctly returns None)
    except Exception as e:
        logger.error(f"Exception fetching file by token '{token}' from Supabase: {e}")
        return None

def get_file_by_telegram_id(file_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a file record by its Telegram file_id to check for duplicates."""
    if not supabase:
        logger.error("Supabase client not initialized. Cannot get file by Telegram ID.")
        return None
    try:
        response = supabase.table(TABLE_NAME).select("id, unique_token").eq("file_id", file_id).maybe_single().execute()
        if response.data:
            return response.data
        elif response.error:
            logger.error(f"Error fetching file by Telegram ID '{file_id}' from Supabase: {response.error}")
            return None
        return None
    except Exception as e:
        logger.error(f"Exception fetching file by Telegram ID '{file_id}' from Supabase: {e}")
        return None

# Example of how to ensure the client is ready before use, can be called at app startup
def check_supabase_connection():
    if not supabase:
        logger.critical("Supabase client is not initialized. Application cannot function with DB.")
        return False
    # You could add a simple test query here if needed, e.g., fetching table metadata
    logger.info("Supabase client appears to be initialized.")
    return True

# Call check_supabase_connection on import to log status, but allow app to control flow if it fails.
check_supabase_connection()
