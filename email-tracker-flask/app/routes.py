from flask import (
    Blueprint, request, jsonify, send_from_directory,
    render_template, abort, current_app, url_for, Response,
    flash, redirect # Added flash and redirect
)
from flask_login import login_user, logout_user, login_required, current_user # Added Flask-Login functions
from sqlalchemy.exc import SQLAlchemyError
from urllib.parse import urlparse, urljoin # For safe redirects

import uuid
import os
import logging
import smtplib # For sending email
from email.message import EmailMessage # For constructing email

from .models import SentEmail, EmailOpen, User # Added User
from .database import db
from .services import get_client_ip, get_location_from_ip # get_client_ip now used less directly
from .forms import LoginForm, ComposeEmailForm # Added forms

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__,
                    template_folder='templates',
                    static_folder='static')

PIXEL_FILENAME = 'pixel.gif'

# --- Helper Functions ---

def is_safe_url(target):
    """Checks if a redirect target URL is safe."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

def send_email_smtp(recipient, subject, html_body):
    """Sends email using configured SMTP settings."""
    sender = current_app.config['SMTP_USERNAME']
    password = current_app.config['SMTP_PASSWORD']
    server_host = current_app.config['SMTP_SERVER']
    port = current_app.config['SMTP_PORT']
    use_tls = current_app.config['SMTP_USE_TLS']
    use_ssl = current_app.config['SMTP_USE_SSL']

    if not all([sender, password, server_host]):
        logger.error("SMTP configuration is missing. Cannot send email.")
        return False, "SMTP configuration missing."

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    msg.set_content("Please enable HTML to view this email.") # Plain text fallback
    msg.add_alternative(html_body, subtype='html') # HTML body

    try:
        if use_ssl:
            logger.debug(f"Connecting via SSL to {server_host}:{port}")
            server = smtplib.SMTP_SSL(server_host, port)
        else:
            logger.debug(f"Connecting via standard SMTP to {server_host}:{port}")
            server = smtplib.SMTP(server_host, port)
            if use_tls:
                logger.debug("Starting TLS...")
                server.starttls()

        logger.debug(f"Logging into SMTP server as {sender}...")
        server.login(sender, password)
        logger.info(f"Sending email via SMTP to {recipient} with subject: {subject}")
        server.send_message(msg)
        server.quit()
        logger.info(f"Email to {recipient} sent successfully.")
        return True, "Email sent successfully."
    except smtplib.SMTPAuthenticationError:
        logger.error(f"SMTP Authentication Failed for user {sender}. Check credentials/App Password.")
        return False, "SMTP Authentication Failed. Check configuration."
    except Exception as e:
        logger.error(f"Failed to send email via SMTP: {e}", exc_info=True)
        return False, f"Failed to send email: {e}"


def log_send_event_internal(subject, recipient_email, sender_ip=None):
    """Internal function to log send event and generate pixel."""
    if sender_ip is None:
         sender_ip = get_client_ip() # Get IP if not passed (e.g., called from compose)
    sender_location = get_location_from_ip(sender_ip)

    new_email = SentEmail(
        sender_ip=sender_ip,
        sender_location=sender_location,
        subject=subject,
        recipient_email=recipient_email,
        sender_user=current_user if current_user.is_authenticated else None # Link to logged-in user
    )
    try:
        db.session.add(new_email)
        db.session.commit()
        logger.info(f"Logged internal send for tracking_id: {new_email.tracking_id} by user {current_user.username if current_user.is_authenticated else 'Anonymous/API'}")
        # Generate URLs (need request context or app context + SERVER_NAME config)
        # It's better to generate these just before sending or in the API response
        # For now, just return the tracking_id
        return new_email.tracking_id
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database error in log_send_event_internal: {e}", exc_info=True)
        return None


# --- Authentication Routes ---

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('.dashboard')) # Redirect if already logged in
    form = LoginForm()
    if form.validate_on_submit(): # Runs on POST request after validation
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger') # Use flash categories
            logger.warning(f"Failed login attempt for username: {form.username.data}")
            return redirect(url_for('.login'))
        # Log the user in
        login_user(user, remember=form.remember_me.data)
        logger.info(f"User '{user.username}' logged in successfully.")
        # Redirect to the page they were trying to access, or dashboard
        next_page = request.args.get('next')
        if not next_page or not is_safe_url(next_page):
            next_page = url_for('.dashboard')
        return redirect(next_page)
    # If GET request or form validation fails, render the login template
    return render_template('login.html', title='Sign In', form=form)

@main_bp.route('/logout')
@login_required # Must be logged in to logout
def logout():
    logger.info(f"User '{current_user.username}' logging out.")
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('.login'))

# --- Core Application Routes ---

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required # Protect the dashboard
def dashboard():
    """Displays list of tracked emails sent by the user."""
    # Fetch emails sent by the current user, ordered most recent first
    # Add pagination for large numbers of emails
    page = request.args.get('page', 1, type=int)
    per_page = 15 # Number of emails per page
    user_emails = SentEmail.query.filter_by(sender_user_id=current_user.id)\
                                 .order_by(SentEmail.send_time.desc())\
                                 .paginate(page=page, per_page=per_page, error_out=False)

    return render_template('dashboard.html', title='Dashboard', emails_pagination=user_emails)


@main_bp.route('/compose', methods=['GET', 'POST'])
@login_required
def compose_email():
    """Page to compose and send a tracked email."""
    form = ComposeEmailForm()
    if form.validate_on_submit():
        recipient = form.recipient.data
        subject = form.subject.data
        body_html_from_form = form.body_html.data 

        # 1. Log the send event internally to get tracking ID
        logger.info(f"User {current_user.username} composing email to {recipient}")
        sender_ip = get_client_ip() # IP of user using the compose form
        tracking_id = log_send_event_internal(subject, recipient, sender_ip)

        if not tracking_id:
            flash('Error logging email send event in database. Email not sent.', 'danger')
            return render_template('compose.html', title='Compose Email', form=form)

        # 2. Generate the pixel URL and HTML
        try:
            pixel_url = url_for('.track_open', tracking_id_str=tracking_id, _external=True)
            report_url = url_for('.view_report', tracking_id_str=tracking_id, _external=True) # Maybe include in email body for testing?
            html_pixel = f'<img src="{pixel_url}" width="1" height="1" alt="" border="0" style="border:0; height:1px; width:1px; padding:0; margin:0; display:block;" loading="eager">'
        except Exception as e:
            logger.error(f"Could not build URLs for tracking_id {tracking_id}: {e}", exc_info=True)
            flash('Error generating tracking URLs. Email not sent.', 'danger')
            return render_template('compose.html', title='Compose Email', form=form)

        # 3. Inject pixel into body (simple append)
        final_html_body = body_html_from_form + "\n" + html_pixel

        # 4. Send the email via SMTP
        success, message = send_email_smtp(recipient, subject, final_html_body)

        if success:
            flash(f'Tracked email sent successfully to {recipient}!', 'success')
            return redirect(url_for('.dashboard'))
        else:
            flash(f'Error sending email: {message}', 'danger')
            # Optionally, you might want to delete the logged SentEmail record if sending fails critically
            # sent_email_to_delete = SentEmail.query.filter_by(tracking_id=tracking_id).first()
            # if sent_email_to_delete:
            #     db.session.delete(sent_email_to_delete)
            #     db.session.commit()


    # Render compose form on GET or if POST validation fails
    return render_template('compose.html', title='Compose Email', form=form)


# --- Report Route (Protected) ---
@main_bp.route('/report/<string:tracking_id_str>')
@login_required # Protect reports
def view_report(tracking_id_str):
    """Displays a simple HTML report for a given tracking ID."""
    try:
        tracking_id = uuid.UUID(tracking_id_str)
        tracking_id_query_str = str(tracking_id)
    except ValueError:
        logger.warning(f"Invalid report tracking ID format: {tracking_id_str}")
        abort(404, description="Invalid Tracking ID format.")

    # Fetch the email, ensuring it belongs to the current user (or allow admin view later)
    sent_email = db.session.query(SentEmail).filter_by(
        tracking_id=tracking_id_query_str,
        sender_user_id=current_user.id # Restrict access
        ).first()

    if not sent_email:
        logger.warning(f"Report tracking ID {tracking_id_str} not found or access denied for user {current_user.username}.")
        abort(404, description="Tracking ID not found or not accessible.")

    email_opens = sent_email.opens.order_by(EmailOpen.open_time.asc()).all()
    total_opens = len(email_opens)

    logger.debug(f"Generating report for tracking_id: {tracking_id_str} with {total_opens} opens for user {current_user.username}.")
    return render_template('report.html', title=f'Report: {sent_email.subject or sent_email.tracking_id}', email=sent_email, opens=email_opens, total_opens=total_opens)


# --- Tracking Pixel Endpoint (Remains Public) ---
@main_bp.route('/track/open/<string:tracking_id_str>.gif')
def track_open(tracking_id_str):
    """
    Endpoint hit by the tracking pixel. Logs the open event. (No login required).
    """
    try:
        tracking_id = uuid.UUID(tracking_id_str)
        tracking_id_query_str = str(tracking_id)
    except ValueError:
        logger.warning(f"Invalid tracking ID format received: {tracking_id_str}")
        return serve_tracking_pixel() # Serve pixel anyway

    # Find the original SentEmail record
    sent_email = db.session.query(SentEmail).filter_by(tracking_id=tracking_id_query_str).first()

    if not sent_email:
        logger.warning(f"Tracking ID not found in database: {tracking_id_str}")
        return serve_tracking_pixel() # Serve pixel anyway

    opener_ip = get_client_ip()
    opener_location = get_location_from_ip(opener_ip)
    user_agent = request.headers.get('User-Agent', 'Unknown')[:255]

    new_open = EmailOpen(
        sent_email_id=sent_email.id,
        opener_ip=opener_ip,
        opener_location=opener_location,
        user_agent=user_agent
    )
    try:
        db.session.add(new_open)
        db.session.commit()
        logger.info(f"Logged open for tracking_id: {tracking_id_str} from IP: {opener_ip}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database error logging open for {tracking_id_str}: {e}", exc_info=True)
    finally:
        return serve_tracking_pixel() # Always serve pixel


def serve_tracking_pixel():
    """Helper function to send the tracking pixel."""
    try:
        response = send_from_directory(
            main_bp.static_folder,
            PIXEL_FILENAME,
            mimetype='image/gif',
            max_age=0 # Deprecated, use Cache-Control
        )
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except FileNotFoundError:
        logger.error(f"Tracking pixel file '{PIXEL_FILENAME}' not found in '{main_bp.static_folder}'")
        return Response(status=204)
    except Exception as e:
        logger.error(f"Error serving tracking pixel: {e}", exc_info=True)
        return Response("Error serving tracking pixel.", status=500)


# --- Optional API Endpoint (Keep or Remove) ---
# If you want external systems to still be able to log sends, keep this.
# Consider adding API Key authentication here if kept.
@main_bp.route('/api/track/send', methods=['POST'])
def track_send_api():
    """ API endpoint (optional). Consider adding authentication. """
    sender_ip = get_client_ip() # IP of the API client
    data = request.get_json(silent=True) or {}
    subject = data.get('subject')
    recipient_email = data.get('recipient_email')

    # Log without associating with a logged-in user
    tracking_id = log_send_event_internal(subject, recipient_email, sender_ip)

    if not tracking_id:
        return jsonify({"error": "Failed to log email send event."}), 500

    try:
        pixel_url = url_for('.track_open', tracking_id_str=tracking_id, _external=True)
        report_url = url_for('.view_report', tracking_id_str=tracking_id, _external=True)
        html_pixel = f'<img src="{pixel_url}" width="1" height="1" alt="" border="0" style="border:0; height:1px; width:1px; padding:0; margin:0; display:block;" loading="eager">'
    except Exception as e:
         logger.error(f"Could not build URLs for tracking_id {tracking_id} in API: {e}", exc_info=True)
         pixel_url = f"/track/open/{tracking_id}.gif" # Fallback
         report_url = f"/report/{tracking_id}"
         html_pixel = f'<img src="{pixel_url}" width="1" height="1" alt="" border="0" style="border:0; height:1px; width:1px; padding:0; margin:0; display:block;" loading="eager">'


    return jsonify({
        "message": "API: Email send event logged successfully.",
        "tracking_id": tracking_id,
        "pixel_url": pixel_url,
        "html_pixel": html_pixel,
        "report_url": report_url 
    }), 201