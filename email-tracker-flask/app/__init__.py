from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager # Import LoginManager
from flask_migrate import Migrate # Import Migrate
from config import ActiveConfig
from .database import db # Import db instance from database.py
from .services import close_geoip
import logging
import atexit
import sqlalchemy.exc
import time
import os

# Configure logging early
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)


login_manager = LoginManager()
migrate = Migrate() 


login_manager.login_view = 'main.login'
login_manager.login_message_category = 'info' 


def create_app(config_object=ActiveConfig):
    """Application Factory Function"""
    app = Flask(__name__)
    app.config.from_object(config_object)

    log_level = logging.DEBUG if app.config.get('DEBUG') else logging.INFO
    app.logger.setLevel(log_level)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING if not app.debug else logging.INFO)

    app.logger.info(f"Flask app '{__name__}' created with config: {type(config_object).__name__}")
    # Log DB URI prefix cautiously
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'Not Set')
    if db_uri:
        app.logger.debug(f"Database URI starts with: {db_uri[:db_uri.find('@') if '@' in db_uri else 30]}...")
    else:
         app.logger.error("SQLALCHEMY_DATABASE_URI is not set in the configuration!")

    app.logger.debug(f"Debug mode is {'ON' if app.debug else 'OFF'}")
    geoip_path = app.config.get('GEOIP_DATABASE_PATH', 'Not Set')
    app.logger.info(f"GeoIP Path configured: {geoip_path}")
    if not os.path.exists(geoip_path):
         app.logger.warning(f"GeoIP database file may be missing at: {geoip_path}")


    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db) # Initialize Migrate with app and db
    app.logger.info("SQLAlchemy, LoginManager, Migrate initialized with app.")

    # Define user loader function for Flask-Login
    # Must be done after User model is defined and db is initialized
    from .models import User # Import here to avoid circular dependency
    @login_manager.user_loader
    def load_user(user_id):
        # Return the user object or None if ID not found
        return User.query.get(int(user_id))
    app.logger.info("Flask-Login user_loader configured.")


    # Create database tables - Now primarily handled by Flask-Migrate
    # db.create_all() within app context can still be useful for initial dev or simple cases
    # but migrations are better for managing changes.
    # Consider removing the db.create_all() block if using migrations exclusively.
    with app.app_context():
        app.logger.info("Ensuring database schema exists (via create_all as fallback/initial)...")
        try:
            db.create_all()
            app.logger.info("db.create_all() executed (useful for initial setup without migrations).")
        except Exception as e:
            app.logger.error(f"Error during db.create_all(): {e}", exc_info=True)


    # Register Blueprints
    try:
        from .routes import main_bp
        app.register_blueprint(main_bp)
        app.logger.info("Main blueprint registered.")
    except Exception as e:
        app.logger.error(f"Failed to register main blueprint: {e}", exc_info=True)

    # Register atexit cleanup
    atexit.register(close_geoip)
    app.logger.info("Registered GeoIP reader cleanup function via atexit.")


    # Shell context for Flask CLI
    @app.shell_context_processor
    def make_shell_context():
        from .models import User, SentEmail, EmailOpen # Import models here
        return {'db': db, 'User': User,'SentEmail': SentEmail, 'EmailOpen': EmailOpen}

    @app.cli.command('create-user')
    def create_user_command():
        """Creates the initial admin user."""
        import getpass
        username = input("Enter username: ")
        password = getpass.getpass("Enter password: ")
        confirm_password = getpass.getpass("Confirm password: ")

        if password != confirm_password:
            print("Passwords do not match.")
            return

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"User '{username}' already exists.")
            return

        new_user = User(username=username)
        new_user.set_password(password)
        try:
            db.session.add(new_user)
            db.session.commit()
            print(f"User '{username}' created successfully.")
        except Exception as e:
             db.session.rollback()
             print(f"Error creating user: {e}")

    return app