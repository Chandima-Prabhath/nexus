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
# This assumes app.py is in admin_dashboard/ and supabase_utils.py is in the parent directory (project root)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import supabase_utils # Changed from db_utils

# Load environment variables. This is important for Supabase client in supabase_utils too.
load_dotenv()

# Configuration
SECRET_KEY = os.getenv("FASTAPI_SECRET_KEY", "a_very_secret_key_for_fastapi_sessions_please_change")
ADMIN_DASHBOARD_PASSCODE = os.getenv("ADMIN_DASHBOARD_PASSCODE")
SESSION_COOKIE_NAME = "nexus_dashboard_session"
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "YOUR_BOT_USERNAME_PLACEHOLDER")

# Initialize FastAPI app
app = FastAPI()

# Mount static files
# Use os.path.abspath to ensure the path is correct, especially if main.py is run from a different CWD.
_current_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(_current_dir, "static")), name="static")

# Templates
templates = Jinja2Templates(directory=os.path.join(_current_dir, "templates"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Session serializer
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Add SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie=SESSION_COOKIE_NAME)

# Basic Logger
logger = logging.getLogger(__name__)
# Configure logging only if handlers are not already set (e.g., by Uvicorn or root main.py)
if not logger.hasHandlers():
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
        # Use app.url_path_for for consistency and if routes change
        return RedirectResponse(url=app.url_path_for("login_page"), status_code=status.HTTP_302_FOUND)

    # Supabase already returns a list of dicts, so no need for [dict(file) for file in files]
    files_for_template = supabase_utils.get_all_files(search_term=search if search else None)

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

    success = supabase_utils.delete_file_by_id(db_id) # Use supabase_utils
    if not success:
        logger.error(f"Failed to delete file with DB ID: {db_id} from Supabase.")
    return RedirectResponse(url=app.url_path_for("dashboard_page"), status_code=status.HTTP_302_FOUND)

# No if __name__ == "__main__": block needed here anymore.
