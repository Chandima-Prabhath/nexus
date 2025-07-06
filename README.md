# Nexus File Hosting System

Nexus is a Telegram-based file hosting system with a FastAPI web dashboard for administration. It allows an admin to forward files to a Telegram bot, which then stores metadata and provides unique shareable links. The dashboard allows viewing and managing these file records.

## Features

*   **Telegram Bot:**
    *   Admin-only file uploads by forwarding to the bot.
    *   Generates unique `t.me/YOUR_BOT?start=TOKEN` links for each file.
    *   Serves files when a valid link is accessed.
    *   Handles documents, photos, videos, and audio.
    *   Uses Supabase (PostgreSQL) for storing file metadata.
*   **FastAPI Admin Dashboard:**
    *   Passcode protected login (supports plain text or bcrypt hashed passcodes).
    *   View all hosted file records.
    *   Delete file records (invalidates the shareable link).
    *   Search for files by filename.
    *   Utility to hash passcodes for secure storage.

## Project Structure

```
.
├── admin_dashboard/        # FastAPI web application
│   ├── static/
│   │   └── style.css
│   ├── templates/
│   │   ├── dashboard.html
│   │   ├── login.html
│   │   └── hash_passcode.html
│   └── app.py              # FastAPI app logic
├── .env.example            # Example environment variables
├── .gitignore
├── supabase_utils.py       # Shared Supabase database utilities
├── LICENSE
├── main.py                 # Root script to run both bot and dashboard
├── nexus_bot.py            # Telegram bot logic
├── README.md               # This file
└── requirements.txt        # Python dependencies
```

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd nexus-file-hosting
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    *   Copy `.env.example` to a new file named `.env`:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file with your actual values:
        *   `TELEGRAM_BOT_TOKEN`: Your Telegram Bot token from BotFather.
        *   `ADMIN_USER_ID`: Your numerical Telegram User ID.
        *   `TELEGRAM_BOT_USERNAME`: Your Telegram Bot's username (without `@`).
        *   `SUPABASE_URL`: Your Supabase project URL.
        *   `SUPABASE_KEY`: Your Supabase project `anon` key (or `service_role` key if RLS is not configured for anon key to perform these operations - using `anon` key with proper RLS policies is recommended).
        *   `ADMIN_DASHBOARD_PASSCODE`: Passcode for the admin dashboard.
        *   `FASTAPI_SECRET_KEY`: Secret key for session cookies. Generate with `openssl rand -hex 32`.

4.  **Supabase Database Setup:**
    *   Go to your Supabase project dashboard.
    *   Navigate to the "SQL Editor" or "Table Editor".
    *   Create a new table named `hosted_files` with the following schema:
        *   `id`: `bigint` (Primary Key, auto-incrementing, is_identity=true)
        *   `file_id`: `text` (Set as UNIQUE)
        *   `unique_token`: `text` (Set as UNIQUE)
        *   `original_filename`: `text` (nullable)
        *   `uploader_id`: `bigint`
        *   `uploaded_at`: `timestamptz` (Default value: `now()`)
    *   **Row Level Security (RLS):** For a production setup, ensure RLS is enabled for the `hosted_files` table.
        *   If using the `anon` key from the backend, you might need to create policies that allow the `anon` role to perform select, insert, and delete operations as needed by the bot and dashboard. Alternatively, use the `service_role` key in your `.env` (this key bypasses RLS but should be kept very secure). For simplicity in this project, using the `service_role` key might be easier if you don't want to configure detailed RLS policies immediately. **However, for true security, RLS with the `anon` key is preferred.** The example `.env.example` refers to `SUPABASE_ANON_KEY_HERE` which implies an expectation of RLS or that the anon key has broad permissions for this table.

## Running the System

The recommended way to run the system for development is using the root `main.py` script, which starts both the Telegram bot and the FastAPI web dashboard.

**1. Running Both Services (Recommended for Development):**

*   Ensure your `.env` file is correctly configured with all required variables.
*   From the project's root directory, run:
    ```bash
    python main.py
    ```
*   This command will:
    *   Start the Telegram bot (`nexus_bot.py`) as a background process.
    *   Start the FastAPI web dashboard using Uvicorn (typically on `http://localhost:8000`).
*   To stop both services, press `Ctrl+C` in the terminal where `main.py` is running. This should gracefully shut down both the Uvicorn server and the bot process.

*   **Bot Usage:**
    *   Create a private Telegram channel.
    *   Upload files to this channel.
    *   Forward the messages containing the files from the channel to your bot (in a private chat with the bot).
    *   The bot will reply with a unique shareable link.

*   **Dashboard Usage:**
    *   Access the dashboard in your browser, typically at `http://localhost:8000`. You will be redirected to `/login`.
    *   Log in using the `ADMIN_DASHBOARD_PASSCODE` from your `.env` file.
    *   **Hashing Passcode (First Time/Security Upgrade):**
        *   If you set a plain text `ADMIN_DASHBOARD_PASSCODE` in `.env`, the application startup log (when running `python main.py`) will show you its bcrypt hash. Copy this hash and update `ADMIN_DASHBOARD_PASSCODE` in your `.env` file for better security.
        *   Alternatively, once the dashboard is running, you can navigate to `http://localhost:8000/utility/hash_passcode`, enter your desired passcode, and it will display the hashed version for you to copy into your `.env` file.

**2. Running Bot and Dashboard Separately (Alternative/Production):**

For more robust control or in production environments, you might prefer to run the bot and the web dashboard as separate processes (e.g., using systemd, Docker Compose, or separate terminal sessions):

*   **Terminal 1 (Bot):**
    ```bash
    python nexus_bot.py
    ```
*   **Terminal 2 (Dashboard):**
    ```bash
    uvicorn admin_dashboard.app:app --host 0.0.0.0 --port 8000
    ```
    *(Note: `admin_dashboard.app:app` refers to the `app` instance in `admin_dashboard/app.py`)*

## Database

*   The system now uses a [Supabase](https://supabase.com/) project (PostgreSQL) as its database.
*   You must create the `hosted_files` table in your Supabase project as described in the Setup section.
*   All file metadata is stored in this Supabase table.

## Important Security Notes

*   **`ADMIN_DASHBOARD_PASSCODE`**: Always use a strong, unique passcode. For production, ensure it is the bcrypt hashed version stored in your `.env` file.
*   **`FASTAPI_SECRET_KEY`**: This key is critical for session security. Ensure it is a long, random, and unique string. Do not commit your actual secret key to version control.
*   **`.env` File**: Keep your `.env` file secure. It contains sensitive keys for Telegram, Supabase, and session management. **Never** commit it to public version control.
*   **Supabase Keys**:
    *   The `SUPABASE_KEY` in your `.env` file grants access to your database. If using the `service_role` key, it has full admin access and bypasses Row Level Security (RLS). Handle it with extreme care.
    *   If using the `anon` key, ensure appropriate RLS policies are in place on your Supabase tables to restrict access.
*   **Deployment**: For actual deployment, consider running Uvicorn behind a reverse proxy like Nginx or Traefik, and always use HTTPS.
*   **File Deletion**: Deleting a file record from the dashboard only removes its metadata from the Supabase database, thereby invalidating the shareable link. It **does not** delete the actual file from Telegram's servers.
