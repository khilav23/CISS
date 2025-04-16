import geoip2.database
import logging
import os
from flask import current_app, request # Import request to use it here
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# --- GeoIP Handling ---
_geoip_reader = None
_geoip_db_path = None

def _initialize_geoip_reader():
    """Initializes or re-initializes the GeoIP reader using Flask app config."""
    global _geoip_reader, _geoip_db_path

    # Ensure we have an app context
    if not current_app:
        logger.error("Attempted to initialize GeoIP reader outside of Flask app context.")
        return False

    try:
        current_path = current_app.config.get('GEOIP_DATABASE_PATH')
    except KeyError:
         logger.error("GEOIP_DATABASE_PATH not found in Flask config.")
         return False

    if not current_path:
        logger.error("GEOIP_DATABASE_PATH is configured but empty in Flask config.")
        if _geoip_reader: _geoip_reader.close()
        _geoip_reader = None
        _geoip_db_path = None
        return False

    # Check if path exists
    db_path_str = str(current_path) # Ensure it's a string
    if not os.path.exists(db_path_str):
        # This warning now comes from config.py, log error here if needed during use
        # logger.error(f"GeoIP database not found at configured path: {db_path_str}")
        if _geoip_reader: _geoip_reader.close()
        _geoip_reader = None
        _geoip_db_path = None
        return False

    # Load only if not loaded or if path has changed
    if _geoip_reader is None or _geoip_db_path != db_path_str:
        try:
            if _geoip_reader: # Close previous reader if path changed
                logger.info("GeoIP path changed, closing existing reader.")
                _geoip_reader.close()
            logger.info(f"Attempting to load GeoIP database from: {db_path_str}")
            _geoip_reader = geoip2.database.Reader(db_path_str)
            _geoip_db_path = db_path_str
            logger.info(f"GeoIP database loaded successfully.")
            return True
        except Exception as e:
            logger.error(f"Error loading GeoIP database from {db_path_str}: {e}", exc_info=True)
            if _geoip_reader: _geoip_reader.close()
            _geoip_reader = None
            _geoip_db_path = None
            return False
    return True # Already loaded and path is the same

@contextmanager
def geoip_reader_manager():
    """Context manager for safe access to the GeoIP reader."""
    if _initialize_geoip_reader() and _geoip_reader:
        yield _geoip_reader
    else:
        yield None # Indicate reader is unavailable

def get_location_from_ip(ip_address):
    """Looks up location for an IP address."""
    if not ip_address:
        return "N/A (No IP)"

    location = "Location Unknown"
    try:
        with geoip_reader_manager() as reader:
            if reader:
                try:
                    response = reader.city(ip_address)
                    city = response.city.name or "N/A"
                    country = response.country.name or "N/A"
                    if city != "N/A" or country != "N/A":
                        location = f"{city}, {country}"
                    else:
                        location = "Location Data Unavailable"
                except geoip2.errors.AddressNotFoundError:
                    logger.debug(f"IP address not found in GeoIP DB: {ip_address}")
                    location = "IP Address Not Found in DB"
                except ValueError:
                    logger.warning(f"Invalid IP Address Format for GeoIP Lookup: {ip_address}")
                    location = "Invalid IP Address Format for Lookup"
            else:
                location = "GeoIP DB Not Available"
                logger.warning(f"GeoIP lookup skipped for {ip_address}: reader unavailable.")
    except Exception as e:
        logger.error(f"GeoIP lookup failed unexpectedly for IP {ip_address}: {e}", exc_info=True)
        location = "GeoIP Lookup Error"
    return location

def close_geoip():
    """Function to explicitly close the GeoIP reader, usually called via atexit."""
    global _geoip_reader, _geoip_db_path
    if _geoip_reader:
        try:
             _geoip_reader.close()
             _geoip_reader = None
             _geoip_db_path = None
             logger.info("GeoIP reader closed via atexit.")
        except Exception as e:
             logger.error(f"Error closing GeoIP reader via atexit: {e}")

# --- IP Address Handling ---
def get_client_ip():
    """
    Gets the client's real IP address from the current request context.
    Considers X-Forwarded-For headers. Needs proxy configuration for production.
    """
    # Check standard header used by proxies first
    if request.headers.getlist("X-Forwarded-For"):
        # Take the first IP in the list (client's original IP)
        ip = request.headers.getlist("X-Forwarded-For")[0].strip()
        logger.debug(f"IP found in X-Forwarded-For: {ip}")
    else:
        # Fallback to remote_addr if header not present
        ip = request.remote_addr
        logger.debug(f"IP found in remote_addr: {ip}")
    return ip