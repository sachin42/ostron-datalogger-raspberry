import threading
from flask import Flask
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

from modules.constants import logger
from modules.config import load_env_config
from modules.network import send_error_to_endpoint, get_public_ip
from modules.threads import logger_thread, heartbeat_thread
from modules.routes import register_routes

app = Flask(__name__)
auth = HTTPBasicAuth()

# Default credentials (change on first login)
users = {
    "admin": generate_password_hash("admin123")
}


@auth.verify_password
def verify_password(username: str, password: str) -> bool:
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None


# Register all routes
register_routes(app, auth)


if __name__ == '__main__':
    # Load environment configuration at startup
    logger.info("Loading environment configuration from .env")
    env_config = load_env_config()

    # Start logger thread
    logger_thread_obj = threading.Thread(target=logger_thread, daemon=True)
    logger_thread_obj.start()

    # Start heartbeat thread
    heartbeat_thread_obj = threading.Thread(target=heartbeat_thread, daemon=True)
    heartbeat_thread_obj.start()

    public_ip = get_public_ip()
    heartbeat_msg = f"System Started - IP: {public_ip}"

    logger.info(f"Sending heartbeat: {heartbeat_msg}")
    send_error_to_endpoint("HEARTBEAT", heartbeat_msg)

    logger.info("Datalogger application started")

    # Run web app
    app.run(host='0.0.0.0', port=9999, debug=False)
