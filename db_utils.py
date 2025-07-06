import sqlite3
import os
import logging

# Determine DB_NAME - this assumes db_utils.py is in the root directory
# If it's moved, this path logic might need adjustment.
# For now, let's keep it simple and assume nexus_files.db is in the same dir as this script or where the app runs from.
DB_NAME = "nexus_files.db"
logger = logging.getLogger(__name__)

def db_connect() -> sqlite3.Connection:
    """Creates a database connection. The database file will be created if it doesn't exist."""
    # Check if DB_NAME path needs adjustment if this file is in a subdir.
    # For now, assume it's relative to where the main scripts (bot/FastAPI) are run.
    conn = sqlite3.connect(DB_NAME)
    # Use Row factory to access columns by name
    conn.row_factory = sqlite3.Row
    return conn

def create_table_if_not_exists() -> None:
    """Creates the hosted_files table if it doesn't exist."""
    conn = None
    try:
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
        logger.info(f"Table 'hosted_files' checked/created in {DB_NAME}.")
    except sqlite3.Error as e:
        logger.error(f"Database error during table creation: {e}")
    finally:
        if conn:
            conn.close()

def get_all_files(search_term: str = None) -> list[sqlite3.Row]:
    """Fetches all files, optionally filtered by a search term on original_filename."""
    files = []
    conn = None
    try:
        conn = db_connect()
        cursor = conn.cursor()
        query = "SELECT id, file_id, unique_token, original_filename, uploader_id, uploaded_at FROM hosted_files"
        params = []
        if search_term:
            query += " WHERE original_filename LIKE ?"
            params.append(f"%{search_term}%")
        query += " ORDER BY uploaded_at DESC"

        cursor.execute(query, params)
        files = cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Database error fetching files (search: '{search_term}'): {e}")
    finally:
        if conn:
            conn.close()
    return files


def delete_file_by_id(db_id: int) -> bool:
    """Deletes a file record from the database by its primary key (id)."""
    conn = None
    try:
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM hosted_files WHERE id = ?", (db_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error deleting file with id {db_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

create_table_if_not_exists()
