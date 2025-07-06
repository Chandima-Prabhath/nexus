import os
import sys
import subprocess
import signal
import logging
import uvicorn
from typing import Optional

# --- Logger setup ---
logger = logging.getLogger(__name__)
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
    try:
        from admin_dashboard.app import app as fastapi_app
        logger.info("FastAPI app imported successfully.")

        # Note: Uvicorn's --reload feature is best handled by running uvicorn directly from CLI.
        # When running programmatically like this, --reload can behave unexpectedly with multiprocessing/subprocess.
        # We are using reload=False here for more predictable behavior of this main script.
        # For development with reload, it's often better to run uvicorn and the bot as separate commands.
        uvicorn_config = uvicorn.Config(
            app=fastapi_app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            # reload=True, # Enabling reload here can make managing the bot subprocess harder.
            # app_dir="admin_dashboard" # This is not needed if 'app' is an app instance.
                                    # app_dir is for when app is a string like "app:app"
        )
        server = uvicorn.Server(config=uvicorn_config)
        logger.info("Starting Uvicorn server for FastAPI dashboard...")
        server.run() # This is a blocking call

    except ImportError:
        logger.error("Could not import FastAPI app from admin_dashboard.app. Ensure paths are correct.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        # This finally block will be executed after uvicorn.server.run() completes (e.g. on Ctrl+C if not handled by signal)
        # or if server.run() raises an exception.
        logger.info("Main script is exiting. Ensuring bot process is stopped.")
        stop_bot_process()
        logger.info("Exited.")
