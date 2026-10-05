import configparser
import jwt
import os
import time
import secrets
# import shlex
import re
import logging
import signal
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from flask import Flask, request
from synochat.webhooks import SlashCommand
from synochat.exceptions import ParameterParseError

# load environment variables from a .env file if present
load_dotenv()

# Load configuration
config = configparser.ConfigParser()
config.read('app.conf')
log_level = config.get('DEFAULT', 'level', fallback='INFO')
log_filename = config.get('DEFAULT', 'filename', fallback='app.log')
log_filemode = config.get('DEFAULT', 'filemode', fallback='a')
log_max_bytes = config.getint('DEFAULT', 'maxBytes', fallback=10485760)  # 10MB
log_backup_count = config.getint('DEFAULT', 'backupCount', fallback=5)

# Setup logging
numeric_level = getattr(logging, log_level.upper(), None)
if not isinstance(numeric_level, int):
    numeric_level = logging.INFO

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(numeric_level)

# Create handlers
file_handler = RotatingFileHandler(
    log_filename,
    mode=log_filemode,
    maxBytes=log_max_bytes,
    backupCount=log_backup_count
)
console_handler = logging.StreamHandler()

# Create formatters and add to handlers
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("Logging system initialized")

# Function to update log level dynamically
def update_log_level(level_name):
    """
    Update the logging level dynamically

    Args:
        level_name (str): The name of the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        level = getattr(logging, level_name.upper(), None)
        if isinstance(level, int):
            logger.setLevel(level)
            logger.info(f"Log level changed to {level_name.upper()}")
            return True
        else:
            logger.error(f"Invalid log level: {level_name}")
            return False
    except Exception as e:
        logger.error(f"Error updating log level: {str(e)}", exc_info=True)
        return False

# Register signal handlers for log rotation
def handle_sigusr1(signum, frame):
    """Reload configuration and update logging when SIGUSR1 is received"""
    logger.info("Received SIGUSR1, reloading configuration")
    try:
        config.read('app.conf')
        log_level = config.get('DEFAULT', 'level', fallback='INFO')
        update_log_level(log_level)
        logger.info("Configuration reloaded successfully")
    except Exception as e:
        logger.error(f"Error reloading configuration: {str(e)}", exc_info=True)

# Register the signal handler
signal.signal(signal.SIGUSR1, handle_sigusr1)

# create the Flask app
app = Flask(__name__)
logger.info("Flask app initialized")

# config via environment variables
SYNO_TOKEN = os.getenv("SYNO_SLASH_TOKEN")
JITSI_DOMAIN = os.getenv("JITSI_DOMAIN", "lsnchat.lifesitenews.com")
JITSI_APP_ID = os.getenv("JITSI_APP_ID")
JITSI_APP_SECRET = os.getenv("JITSI_APP_SECRET")
logger.info(f"Configuration loaded. Using Jitsi domain: {JITSI_DOMAIN}")

def sanitize_room(name: str) -> str:
    """Sanitize room name to be URL-safe and within length limits"""
    sanitized = re.sub(r"[^A-Za-z0-9_\-]", "-", name)[:128]
    logger.debug(f"Sanitized room name: '{name}' -> '{sanitized}'")
    return sanitized

def gen_room(username: str) -> str:
    """Generate a unique room name based on username and random token"""
    room = sanitize_room(f"{username}-{int(time.time())}-{secrets.token_hex(3)}")
    logger.debug(f"Generated room name for user '{username}': '{room}'")
    return room

@app.route("/", methods=["GET"])
def home():
    """Home page"""
    logger.debug("Home page accessed")
    return "Welcome to the webhook for integrate Synology Chat and Jitsi Meet! 📅\n"

@app.route("/log/level", methods=["GET", "POST"])
def log_level_endpoint():
    """Get or set the current log level"""
    if request.method == "GET":
        return {"current_level": logging.getLevelName(logger.level)}
    elif request.method == "POST":
        try:
            data = request.get_json()
            if "level" in data:
                success = update_log_level(data["level"])
                if success:
                    return {"status": "success", "level": logging.getLevelName(logger.level)}
                else:
                    return {"status": "error", "message": f"Invalid log level: {data['level']}"}, 400
            else:
                return {"status": "error", "message": "No log level provided"}, 400
        except Exception as e:
            logger.error(f"Error setting log level: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}, 500

@app.route("/slash/meeting", methods=["POST"])
def slash_meeting():
    """Handle the /meeting slash command from Synology Chat"""
    logger.info("Received /meeting slash command")
    try:
        # parse the incoming slash command
        cmd = SlashCommand(request.form)
        # we compare with the saved token
        if not cmd.authenticate(SYNO_TOKEN):
            logger.warning(f"Authentication failed for user: {cmd.username}")
            return cmd.createResponse("❌ Invalid token."), 401
        logger.debug(f"Authentication successful for user: {cmd.username}")
    except Exception as e:
        logger.error(f"Error processing slash command: {str(e)}", exc_info=True)
        return "Internal Server Error\n", 500

    # Check if the command parameters are valid
    try:
        action  = cmd.addParameter('action')
        name   = cmd.addParameter('name', optional=True)
    except ParameterParseError:
        return cmd.createResponse('Slash command failed because one or more parameters are missing.')

    # Handle the first (positional) parameter
    if action.isPresent():
        print(action)
    else:
        print("Parameter 'action' not detected in the command.")

    # Handle the second (positional) parameter
    if name.isPresent():
        print(name)
    else:
        print("Parameter 'name' not detected in the command.")

    # # text entered after /meeting ... (could contain name, pass=..., duration=...)
    # text = (cmd.text or "").strip()
    # tokens = shlex.split(text) if text else []

    # params, positional = {}, []
    # for t in tokens:
    #     if "=" in t:
    #         k, v = t.split("=", 1)
    #         params[k.lower()] = v
    #     else:
    #         positional.append(t)

    # room = params.get("name") or (positional[0] if positional else None) or gen_room(cmd.username)
    room = name or gen_room(cmd.username)
    room = sanitize_room(room)

    # mount the base url addressing the room
    meeting_url = f"https://{JITSI_DOMAIN}/{room}"

    # If you have JWT set: generate token (optional)
    if JITSI_APP_ID and JITSI_APP_SECRET:
        logger.debug(f"Generating JWT token for room: {room}")
        payload = {
            "aud": JITSI_APP_ID,
            "iss": JITSI_APP_ID,
            "sub": JITSI_DOMAIN,
            "room": room,
            "exp": int(time.time()) + 3600,
            "context": {"user": {"name": cmd.username}},
        }
        token = jwt.encode(payload, JITSI_APP_SECRET, algorithm="HS256")
        # recommended way: we recommend using an intermediate page/iframe that passes the JWT to the iframe,
        # but as a shortcut you can return the link including ?jwt=... (try it first).
        meeting_url = meeting_url + f"?jwt={token}"
        logger.debug("JWT token generated successfully")
    else:
        logger.debug("JWT token generation skipped - app ID or secret missing")

    # Reply to Synology (visible only to the one who executed the /command)
    text_response = f"{cmd.username} created a 📅 video conference: {meeting_url}\n🗂 Room: `{room}`"
    logger.info(f"Meeting created by {cmd.username} in room: {room}")
    return cmd.createResponse(text_response)
