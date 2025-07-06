# Nexus File Hosting System

Nexus is a Telegram-based file hosting system with a FastAPI web dashboard for administration. It allows an admin to forward files to a Telegram bot, which then stores metadata and provides unique shareable links. The dashboard allows viewing and managing these file records.

## Features

*   **Telegram Bot:**
    *   Admin-only file uploads by forwarding to the bot.
    *   Generates unique `t.me/YOUR_BOT?start=TOKEN` links for each file.
    *   Serves files when a valid link is accessed.
    *   Handles documents, photos, videos, and audio.
    *   SQLite database for storing file metadata.
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
│   └── app.py              # FastAPI app logic (renamed from main.py)
├── .env.example            # Example environment variables
├── .gitignore
├── db_utils.py             # Shared database utilities
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
        *   `ADMIN_USER_ID`: Your numerical Telegram User ID. You can get this by sending `/myid` to a bot like `@userinfobot`.
        *   `TELEGRAM_BOT_USERNAME`: Your Telegram Bot's username (without the `@` symbol, e.g., `MyNexusTestBot`). This is used by the dashboard to generate correct share links.
        *   `ADMIN_DASHBOARD_PASSCODE`: Choose a strong passcode for your admin dashboard.
            *   For initial setup, you can use a plain text passcode. The FastAPI app will log a warning and the bcrypt hash of this passcode when it starts.
            *   For better security, replace the plain passcode with its bcrypt hashed version in the `.env` file. You can use the `/utility/hash_passcode` endpoint on the running dashboard for this.
        *   `FASTAPI_SECRET_KEY`: A strong, random string used for signing session cookies. You can generate one using: `openssl rand -hex 32`.

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

*   The system uses an SQLite database file named `nexus_files.db` which will be created automatically in the project root directory when `db_utils.py` is first imported (e.g., when the bot or dashboard starts).
*   This file stores metadata about the hosted files.

## Important Security Notes

*   **`ADMIN_DASHBOARD_PASSCODE`**: Always use a strong, unique passcode. For production, ensure it is the bcrypt hashed version stored in your `.env` file.
*   **`FASTAPI_SECRET_KEY`**: This key is critical for session security. Ensure it is a long, random, and unique string. Do not commit your actual secret key to version control.
*   **`.env` File**: Keep your `.env` file secure and **never** commit it to version control if it contains real secrets. The `.gitignore` is set up to prevent this.
*   **Deployment**: For actual deployment, consider running Uvicorn behind a reverse proxy like Nginx or Traefik, and use HTTPS. The current setup is for development.
*   **File Deletion**: Deleting a file record from the dashboard only removes it from the database and invalidates the share link. It **does not** delete the file from Telegram's servers.

This `README.md` provides a good overview and setup instructions.
