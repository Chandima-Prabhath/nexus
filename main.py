import os
import sys
import subprocess
import signal
import logging
import uvicorn
from typing import Optional
from dotenv import load_dotenv # Import dotenv

# --- Load .env variables at the very start ---
load_dotenv()

# --- Logger setup ---
logger = logging.getLogger(__name__)
# Configure logging only if handlers are not already set (e.g. by Uvicorn)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# --- Global for bot process ---
bot_process: Optional[subprocess.Popen] = None

# --- Bot Process Management ---
def start_bot_process():
    global bot_process
    project_root = os.path.dirname(os.path.abspath(__file__))
    bot_script_path = os.path.join(project_root, "nexus_bot.py")

    logger.info(f"Attempting to start bot from: {bot_script_path} with cwd: {project_root}")

    current_env = os.environ.copy()
    current_env["PYTHONUNBUFFERED"] = "1" # Ensures bot's print/logging output is seen immediately

    creation_flags = 0
    if sys.platform == "win32":
        if hasattr(subprocess, 'CREATE_NO_WINDOW'): # subprocess.CREATE_NO_WINDOW is Windows specific
            creation_flags = subprocess.CREATE_NO_WINDOW

    try:
        bot_process = subprocess.Popen([sys.executable, bot_script_path], cwd=project_root, env=current_env, creationflags=creation_flags)
        # Check if process started successfully and is running
        if bot_process and bot_process.poll() is None:
            logger.info(f"Nexus bot process started successfully with PID: {bot_process.pid}")
        elif bot_process:
            logger.error(f"Nexus bot process started but exited immediately with code: {bot_process.returncode}. Check bot logs.")
            bot_process = None # Clear if it exited
        else: # Popen itself might have failed if bot_process is None
            logger.error("Failed to start Nexus bot process (subprocess.Popen call failed).")
            bot_process = None
    except Exception as e:
        logger.error(f"Exception during bot process startup: {e}")
        bot_process = None


def stop_bot_process():
    global bot_process
    if bot_process and bot_process.poll() is None: # Check if process exists and is running
        logger.info(f"Attempting to terminate Nexus bot process (PID: {bot_process.pid})...")
        bot_process.terminate() # Send SIGTERM
        try:
            bot_process.wait(timeout=10) # Wait for graceful shutdown
            logger.info("Nexus bot process terminated successfully.")
        except subprocess.TimeoutExpired:
            logger.warning("Nexus bot process did not terminate in time, killing.")
            bot_process.kill() # Force kill
            logger.info("Nexus bot process killed.")
        except Exception as e:
            logger.error(f"Exception during bot process shutdown: {e}")
    elif bot_process : # Process existed but was already terminated
        logger.info(f"Nexus bot process (PID: {bot_process.pid}) was already terminated.")
    else: # Process was never started successfully
        logger.info("No active Nexus bot process to terminate (or it failed to start).")
    bot_process = None


# --- Signal Handling for graceful shutdown ---
def signal_handler(signum, frame):
    logger.info(f"Received signal {signal.Signals(signum).name}. Shutting down...")
    stop_bot_process()
    # Uvicorn should handle its own shutdown upon receiving the signal if it's running in the main thread.
    # If Uvicorn is run in a separate thread by this script (not the case here), it would need explicit shutdown.
    sys.exit(0) # Exit main script

# --- Main Application Execution ---
if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the bot process
    start_bot_process()

    # Start Uvicorn for the FastAPI app
    # Import the app object from admin_dashboard.app
    # Also ensure supabase_utils (and thus Supabase client) is initialized before bot/app try to use it.
    try:
        # Ensure supabase_utils (which loads Supabase client) is imported and initialized first
        import supabase_utils
        if not supabase_utils.supabase:
            logger.critical("Supabase client in supabase_utils failed to initialize. Cannot proceed.")
            sys.exit(1)
        else:
            logger.info("Supabase client appears initialized via supabase_utils.")

        from admin_dashboard.app import app as fastapi_app
        logger.info("FastAPI app imported successfully.")

        uvicorn_config = uvicorn.Config(
            app=fastapi_app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
            # reload=False is generally better for programmatic run to avoid issues with subprocesses.
            # For development with reload, `uvicorn admin_dashboard.app:app --reload` is preferred for the web part.
        )
        server = uvicorn.Server(config=uvicorn_config)
        logger.info("Starting Uvicorn server for FastAPI dashboard...")
        server.run()

    except ImportError as e:
        logger.error(f"Could not import required modules. Ensure paths and dependencies are correct: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
    finally:
        logger.info("Main script is exiting. Ensuring bot process is stopped.")
        stop_bot_process() # This will run when server.run() exits (e.g., Ctrl+C)
        logger.info("Exited.")
