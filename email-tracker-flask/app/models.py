from .database import db
from datetime import datetime
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin # Import UserMixin

# Association with LoginManager will happen in __init__.py
# from . import login_manager # Avoid circular import, setup in __init__

class User(UserMixin, db.Model): # Inherit from UserMixin
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128)) # Store hash, not password

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# SentEmail and EmailOpen models remain the same as before
class SentEmail(db.Model):
    __tablename__ = 'sent_emails'

    id = db.Column(db.Integer, primary_key=True)
    tracking_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    send_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sender_ip = db.Column(db.String(45), nullable=True) # IP of the *system* sending via the app
    sender_location = db.Column(db.String(100), nullable=True)
    # Add user who sent it
    sender_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Optional link to user
    sender_user = db.relationship('User', backref='sent_emails') # Relationship

    subject = db.Column(db.String(255), nullable=True)
    recipient_email = db.Column(db.String(255), nullable=True)

    opens = db.relationship('EmailOpen', backref='sent_email', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<SentEmail {self.tracking_id}>'

class EmailOpen(db.Model):
    __tablename__ = 'email_opens'

    id = db.Column(db.Integer, primary_key=True)
    sent_email_id = db.Column(db.Integer, db.ForeignKey('sent_emails.id', ondelete='CASCADE'), nullable=False, index=True)
    open_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    opener_ip = db.Column(db.String(45), nullable=True)
    opener_location = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<EmailOpen ID: {self.id} for SentEmail ID: {self.sent_email_id}>'