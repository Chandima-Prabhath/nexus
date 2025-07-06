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
│   └── main.py             # FastAPI app logic
├── .env.example            # Example environment variables
├── .gitignore
├── db_utils.py             # Shared database utilities
├── LICENSE
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

You need to run two separate applications: the Telegram Bot and the FastAPI Web Dashboard.

**1. Running the Telegram Bot:**

*   Ensure your `.env` file is correctly configured, especially `TELEGRAM_BOT_TOKEN` and `ADMIN_USER_ID`.
*   Run the bot:
    ```bash
    python nexus_bot.py
    ```
*   The bot will start polling for updates. To use it:
    *   Create a private Telegram channel.
    *   Upload files to this channel.
    *   Forward the messages containing the files from the channel to your bot (in a private chat with the bot).
    *   The bot will reply with a unique shareable link.

**2. Running the FastAPI Admin Dashboard:**

*   Ensure your `.env` file is correctly configured, especially `ADMIN_DASHBOARD_PASSCODE` and `FASTAPI_SECRET_KEY`.
*   Navigate to the `admin_dashboard` directory if you want to run uvicorn from there, or run from project root specifying the app path.
*   Run the FastAPI app using Uvicorn (from the project root):
    ```bash
    python admin_dashboard/main.py
    ```
    This will start the Uvicorn server for the dashboard (typically on `http://localhost:8000`) and will also attempt to start the `nexus_bot.py` in a background process.

    *   **Note on `--reload` with Integrated Bot:** If you run Uvicorn directly with `--reload` (e.g., `uvicorn admin_dashboard.main:app --reload`), the bot process management might behave unexpectedly due to how Uvicorn handles reloading. Running `python admin_dashboard/main.py` is the recommended way for the integrated startup during development. For production, consider running the bot and web app as separate services.

*   Access the dashboard in your browser, typically at `http://localhost:8000`. You will be redirected to `/login`.
*   **Hashing Passcode (First Time/Security Upgrade):**
    *   If you set a plain text `ADMIN_DASHBOARD_PASSCODE` in `.env`, the FastAPI application startup log (when running `python admin_dashboard/main.py`) will show you its bcrypt hash. Copy this hash and update `ADMIN_DASHBOARD_PASSCODE` in your `.env` file for better security.
    *   Alternatively, once the dashboard is running, you can navigate to `http://localhost:8000/utility/hash_passcode`, enter your desired passcode, and it will display the hashed version for you to copy into your `.env` file.

**2. Running Bot and Dashboard Separately (Alternative/Production):**

For more robust control, especially in production, you might prefer to run them as separate processes:

*   **Terminal 1 (Bot):**
    ```bash
    python nexus_bot.py
    ```
*   **Terminal 2 (Dashboard):**
    ```bash
    uvicorn admin_dashboard.main:app --host 0.0.0.0 --port 8000
    ```

## Database

*   The system uses an SQLite database file named `nexus_files.db` which will be created automatically in the project root directory when either the bot or the dashboard first initializes database utilities.
*   This file stores metadata about the hosted files.

## Important Security Notes

*   **`ADMIN_DASHBOARD_PASSCODE`**: Always use a strong, unique passcode. For production, ensure it is the bcrypt hashed version stored in your `.env` file.
*   **`FASTAPI_SECRET_KEY`**: This key is critical for session security. Ensure it is a long, random, and unique string. Do not commit your actual secret key to version control.
*   **`.env` File**: Keep your `.env` file secure and **never** commit it to version control if it contains real secrets. The `.gitignore` is set up to prevent this.
*   **Deployment**: For actual deployment, consider running Uvicorn behind a reverse proxy like Nginx or Traefik, and use HTTPS. The current setup is for development.
*   **File Deletion**: Deleting a file record from the dashboard only removes it from the database and invalidates the share link. It **does not** delete the file from Telegram's servers.

This `README.md` provides a good overview and setup instructions.
