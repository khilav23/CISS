import os
from dotenv import load_dotenv
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

basedir = Path(__file__).resolve().parent
dotenv_path = basedir / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path)
    logger.info(f".env file loaded from {dotenv_path}")
else:
    logger.warning(f".env file not found at {dotenv_path}, using defaults or existing environment variables.")

class Config:
    """Base configuration settings."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default_secret_key_if_not_set')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database configuration
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT_STR = os.getenv("DB_PORT", "3306")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")

    try:
        DB_PORT = int(DB_PORT_STR)
    except (ValueError, TypeError):
        logger.error(f"Invalid DB_PORT value '{DB_PORT_STR}'. Using default 3306.")
        DB_PORT = 3306

    if not all([DB_USER, DB_PASSWORD is not None, DB_HOST, DB_NAME]):
         logger.error("One or more essential Database environment variables (DB_USER, DB_PASSWORD, DB_HOST, DB_NAME) are missing. Database connection will likely fail.")
         SQLALCHEMY_DATABASE_URI = None
    else:
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
        )
        logger.info(f"Database URI configured for user '{DB_USER}' on host '{DB_HOST}:{DB_PORT}', database '{DB_NAME}'.")

    # SMTP Configuration for sending email
    SMTP_SERVER = os.getenv('SMTP_SERVER')
    SMTP_PORT_STR = os.getenv('SMTP_PORT', '587')
    try:
        SMTP_PORT = int(SMTP_PORT_STR)
    except (ValueError, TypeError):
        logger.error(f"Invalid SMTP_PORT value '{SMTP_PORT_STR}'. Using default 587.")
        SMTP_PORT = 587
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True').lower() in ('true', '1', 't')
    SMTP_USE_SSL = os.getenv('SMTP_USE_SSL', 'False').lower() in ('true', '1', 't')
    SMTP_USERNAME = os.getenv('SMTP_USERNAME')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD') # Password or App Password

    if not all([SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD]):
        logger.warning("SMTP server configuration is incomplete. Email sending will likely fail.")


    # GeoIP configuration
    GEOIP_DATABASE_PATH = os.environ.get('GEOIP_DATABASE_PATH', str(basedir / 'geoip_data' / 'GeoLite2-City.mmdb'))
    if not os.path.exists(GEOIP_DATABASE_PATH):
        logger.warning(f"GeoIP database file not found at configured path: {GEOIP_DATABASE_PATH}")

# Select the active configuration
ActiveConfig = Config()

# Basic validation feedback
if ActiveConfig.SECRET_KEY == 'default_secret_key_if_not_set' or ActiveConfig.SECRET_KEY == 'flask_secret_key_needs_changing_here!':
     logger.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
     logger.warning("WARNING: Default SECRET_KEY is used. Set a proper SECRET_KEY in your .env file.")
     logger.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")