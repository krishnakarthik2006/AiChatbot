"""SQLAlchemy models for the chatbot application."""
from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class Account(db.Model, UserMixin):
    """Registered user account."""
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    chat_sessions = db.relationship('User', backref='account', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'display_name': self.display_name or self.email.split('@')[0],
            'created_at': self.created_at.isoformat(),
        }


class User(db.Model):
    """Chat session model (linked to an authenticated account)."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    conversations = db.relationship('Conversation', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'account_id': self.account_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class Conversation(db.Model):
    """Conversation history model."""
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(100))
    confidence = db.Column(db.Float)
    engine = db.Column(db.String(50), default='hybrid')
    model = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_message': self.user_message,
            'bot_response': self.bot_response,
            'intent': self.intent,
            'confidence': self.confidence,
            'engine': self.engine,
            'model': self.model,
            'timestamp': self.timestamp.isoformat()
        }


class Intent(db.Model):
    """Intent model for storing training data."""
    __tablename__ = 'intents'
    
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(100), unique=True, nullable=False, index=True)
    patterns = db.Column(db.JSON, nullable=False)  # JSON array of patterns
    responses = db.Column(db.JSON, nullable=False)  # JSON array of responses
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'tag': self.tag,
            'patterns': self.patterns,
            'responses': self.responses,
            'created_at': self.created_at.isoformat()
        }


class ModelMetadata(db.Model):
    """Model metadata for tracking trained models."""
    __tablename__ = 'model_metadata'
    
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), unique=True, nullable=False)
    version = db.Column(db.String(50), default='1.0.0')
    intents_count = db.Column(db.Integer)
    training_samples = db.Column(db.Integer)
    accuracy = db.Column(db.Float)
    trained_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'model_name': self.model_name,
            'version': self.version,
            'intents_count': self.intents_count,
            'training_samples': self.training_samples,
            'accuracy': self.accuracy,
            'trained_at': self.trained_at.isoformat()
        }
