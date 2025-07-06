import os
import logging
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
import sys

# Add project root to sys.path to allow importing db_utils
# This assumes main.py is in admin_dashboard/ and db_utils.py is in the parent directory (project root)
# This is a common way to handle imports in sub-packages.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db_utils # type: ignore # TODO: Fix this type ignore later if Pylance complains in this structure


# Load environment variables
load_dotenv()

# Configuration
SECRET_KEY = os.getenv("FASTAPI_SECRET_KEY", "a_very_secret_key_for_fastapi_sessions_please_change")
ADMIN_DASHBOARD_PASSCODE = os.getenv("ADMIN_DASHBOARD_PASSCODE")
SESSION_COOKIE_NAME = "nexus_dashboard_session"
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "YOUR_BOT_USERNAME_PLACEHOLDER") # For generating full links

# Initialize FastAPI app
app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Session serializer
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Add SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie=SESSION_COOKIE_NAME)

# Basic Logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


# --- Authentication ---
async def get_current_user(request: Request):
    session_token = request.session.get("user_token")
    if not session_token:
        return None
    try:
        data = serializer.loads(session_token, max_age=3600) # 1 hour session
        if data.get("authenticated") is True:
            return True
    except (SignatureExpired, BadTimeSignature):
        request.session.pop("user_token", None)
    return None

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, passcode: str = Form(...)):
    if not ADMIN_DASHBOARD_PASSCODE:
        logger.error("ADMIN_DASHBOARD_PASSCODE is not set in the environment.")
        return templates.TemplateResponse("login.html", {"request": request, "error": "Admin dashboard not configured."})

    # Check if stored passcode is already hashed
    is_hashed = ADMIN_DASHBOARD_PASSCODE.startswith("$2b$") # Basic bcrypt hash check

    valid_passcode = False
    if is_hashed:
        try:
            valid_passcode = pwd_context.verify(passcode, ADMIN_DASHBOARD_PASSCODE)
        except Exception as e: # Handle potential errors during verify if hash is malformed
            logger.error(f"Error verifying hashed passcode: {e}")
            valid_passcode = False
    else: # Plain text comparison (less secure, for initial setup)
        valid_passcode = (passcode == ADMIN_DASHBOARD_PASSCODE)

    if valid_passcode:
        session_token = serializer.dumps({"authenticated": True})
        request.session["user_token"] = session_token
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid passcode"})

@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user_token", None)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

# --- Hashing Utility ---
@app.get("/utility/hash_passcode", response_class=HTMLResponse, name="hash_passcode_form")
async def hash_passcode_form_page(request: Request):
    return templates.TemplateResponse("hash_passcode.html", {"request": request, "hashed_passcode": None})

@app.post("/utility/hash_passcode", response_class=HTMLResponse, name="process_hash_passcode")
async def process_hash_passcode_submit(request: Request, plain_passcode: str = Form(...)):
    hashed_passcode = pwd_context.hash(plain_passcode)
    return templates.TemplateResponse("hash_passcode.html", {"request": request, "hashed_passcode": hashed_passcode, "original_passcode": plain_passcode})


# --- Dashboard Routes (Protected) ---
@app.get("/", response_class=HTMLResponse)
async def root_redirect(user: bool = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)


@app.get("/dashboard", response_class=HTMLResponse, name="dashboard_page")
async def get_dashboard_page(request: Request, search: str = "", user: bool = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    files = db_utils.get_all_files(search_term=search if search else None)
    files_for_template = [dict(file) for file in files]

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "files": files_for_template,
        "bot_name": "Nexus Bot",
        "bot_username": BOT_USERNAME,
        "search_term": search
    })

@app.post("/delete_file/{db_id}", name="delete_file_route")
async def delete_file_route(request: Request, db_id: int, user: bool = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    success = db_utils.delete_file_by_id(db_id)
    if not success:
        logger.error(f"Failed to delete file with DB ID: {db_id}")
    # Preserve search term on redirect if possible, or just redirect to base dashboard
    # For simplicity, redirecting to base dashboard.
    return RedirectResponse(url=app.url_path_for("get_dashboard_page"), status_code=status.HTTP_302_FOUND)


if __name__ == "__main__":
    import uvicorn
    if not ADMIN_DASHBOARD_PASSCODE:
        logger.warning("ADMIN_DASHBOARD_PASSCODE is not set in .env. Login will not function correctly.")
        logger.warning("Use the /utility/hash_passcode endpoint to generate a hashed passcode once the app is running.")
    elif not ADMIN_DASHBOARD_PASSCODE.startswith("$2b$"):
         logger.warning(f"ADMIN_DASHBOARD_PASSCODE in .env appears to be plain text: '{ADMIN_DASHBOARD_PASSCODE}'.")
         logger.warning(f"For better security, hash it (e.g. using /utility/hash_passcode) and update .env.")
         logger.info(f"If you want to use '{ADMIN_DASHBOARD_PASSCODE}' as your passcode, its hashed version is: {pwd_context.hash(ADMIN_DASHBOARD_PASSCODE)}")

    if not SECRET_KEY or SECRET_KEY == "a_very_secret_key_for_fastapi_sessions_please_change":
        logger.warning("FASTAPI_SECRET_KEY is not set or is using the default insecure value in .env. Please set a strong, random key for session security.")

    logger.info("Database table checked/created via db_utils.")

    # --- Integrated Bot Startup ---
    # This uses FastAPI's lifespan events for cleaner start/stop.
    # Note: When Uvicorn's --reload flag is used, it manages the main process and workers.
    # Lifespan events will run in the main process. Child process management with --reload
    # can be tricky, as Uvicorn might restart workers without cleanly handling children
    # of the old main process if not careful.
    # For production, separate service management (systemd, Docker Compose) is more robust.

    import subprocess
    from typing import Optional # Ensure Optional is imported if not already

    bot_process_global: Optional[subprocess.Popen] = None

    def run_bot_process():
        bot_script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nexus_bot.py")
        logger.info(f"Attempting to start bot from: {bot_script_path}")
        # Ensure PYTHONUNBUFFERED is set so bot logs appear immediately
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        process = subprocess.Popen([sys.executable, bot_script_path], cwd=os.path.dirname(bot_script_path), env=env)
        return process

    @app.on_event("startup")
    async def startup_event():
        nonlocal bot_process_global
        logger.info("FastAPI app starting up, attempting to start Nexus bot...")
        # Only start bot if not in Uvicorn reload worker process
        # This check is a bit of a heuristic. A more robust way might involve checking environment variables
        # set by Uvicorn for its workers, or simply accepting that with --reload, multiple bot instances might
        # try to start if not handled carefully (e.g. by the bot itself having a lock mechanism, which is overkill here).
        # The main Uvicorn process (when --reload is used) doesn't typically run the app itself, but supervises.
        # Let's assume for now this runs once per "actual" app startup.
        # A simpler approach for --reload is to just let it be and understand multiple might start/stop during reloads.
        # Or, don't run the bot if `reload` is true.

        # Check if Uvicorn is in reload mode (this is an approximation)
        if not os.getenv("WORKERS_PER_CORE"): # Uvicorn sets this for workers, not for the reloader process
            bot_process_global = run_bot_process()
            if bot_process_global:
                logger.info(f"Nexus bot process started with PID: {bot_process_global.pid}")
            else:
                logger.error("Failed to start Nexus bot process.")
        else:
            logger.info("Skipping bot startup in Uvicorn worker/reload process.")


    @app.on_event("shutdown")
    async def shutdown_event():
        nonlocal bot_process_global
        logger.info("FastAPI app shutting down, attempting to terminate Nexus bot process...")
        if bot_process_global and bot_process_global.poll() is None:
            logger.info(f"Terminating Nexus bot process PID: {bot_process_global.pid}")
            bot_process_global.terminate() # Send SIGTERM
            try:
                bot_process_global.wait(timeout=5) # Wait for graceful shutdown
                logger.info("Nexus bot process terminated successfully.")
            except subprocess.TimeoutExpired:
                logger.warning("Nexus bot process did not terminate in time, killing.")
                bot_process_global.kill() # Force kill
                logger.info("Nexus bot process killed.")
        elif bot_process_global:
            logger.info(f"Nexus bot process (PID: {bot_process_global.pid}) already terminated or was not started by this instance.")
        else:
            logger.info("No active Nexus bot process to terminate (or was not started by this instance).")

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, app_dir="admin_dashboard")
