"""Database utilities and connection management."""
import logging
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from backend.models import db, Account, User, Conversation, Intent, ModelMetadata

logger = logging.getLogger(__name__)


def _ensure_user_account_column():
    """Add account_id to users when upgrading an existing database."""
    inspector = inspect(db.engine)
    if 'users' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('users')}
    if 'account_id' in columns:
        return

    with db.engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN account_id INT NULL, "
            "ADD INDEX ix_users_account_id (account_id), "
            "ADD CONSTRAINT fk_users_account_id "
            "FOREIGN KEY (account_id) REFERENCES accounts(id)"
        ))
    logger.info("Added users.account_id column for authentication.")


def init_db(app):
    """Initialize the database with the Flask app."""
    with app.app_context():
        db.create_all()
        _ensure_user_account_column()
        logger.info("Database tables created/verified.")


def create_account(email, password, display_name=None):
    """Create a registered account."""
    try:
        account = Account(email=email, display_name=display_name)
        account.set_password(password)
        db.session.add(account)
        db.session.commit()
        logger.info("Created account: %s", email)
        return account
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Error creating account: %s", e)
        return None


def get_account_by_email(email):
    """Fetch an account by email address."""
    try:
        return Account.query.filter_by(email=email).first()
    except SQLAlchemyError as e:
        logger.error("Error retrieving account: %s", e)
        return None


def create_user_session(session_id, account_id=None):
    """Create a new chat session."""
    try:
        user = User(session_id=session_id, account_id=account_id)
        db.session.add(user)
        db.session.commit()
        logger.info("Created user session: %s", session_id)
        return user
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Error creating user session: %s", e)
        return None


def get_user_by_session_id(session_id):
    """Get user by session ID."""
    try:
        return User.query.filter_by(session_id=session_id).first()
    except SQLAlchemyError as e:
        logger.error(f"Error retrieving user: {e}")
        return None


def save_conversation(user_id, user_message, bot_response, intent, confidence, engine, model):
    """Save a conversation to the database."""
    try:
        conversation = Conversation(
            user_id=user_id,
            user_message=user_message,
            bot_response=bot_response,
            intent=intent,
            confidence=confidence,
            engine=engine,
            model=model
        )
        db.session.add(conversation)
        db.session.commit()
        logger.info(f"Saved conversation for user {user_id}")
        return conversation
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error saving conversation: {e}")
        return None


def get_conversation_history(user_id, limit=28):
    """Get conversation history for a user."""
    try:
        conversations = Conversation.query.filter_by(user_id=user_id).order_by(
            Conversation.timestamp.desc()
        ).limit(limit).all()
        return sorted(conversations, key=lambda x: x.timestamp)
    except SQLAlchemyError as e:
        logger.error(f"Error retrieving conversation history: {e}")
        return []


def save_intent(tag, patterns, responses):
    """Save an intent to the database."""
    try:
        intent = Intent.query.filter_by(tag=tag).first()
        if intent:
            intent.patterns = patterns
            intent.responses = responses
        else:
            intent = Intent(tag=tag, patterns=patterns, responses=responses)
            db.session.add(intent)
        db.session.commit()
        logger.info(f"Saved intent: {tag}")
        return intent
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error saving intent: {e}")
        return None


def get_all_intents():
    """Get all intents from database."""
    try:
        intents = Intent.query.all()
        return [{
            'tag': intent.tag,
            'patterns': intent.patterns,
            'responses': intent.responses
        } for intent in intents]
    except SQLAlchemyError as e:
        logger.error(f"Error retrieving intents: {e}")
        return []


def save_model_metadata(model_name, version, intents_count, training_samples, accuracy):
    """Save model metadata."""
    try:
        metadata = ModelMetadata(
            model_name=model_name,
            version=version,
            intents_count=intents_count,
            training_samples=training_samples,
            accuracy=accuracy
        )
        db.session.add(metadata)
        db.session.commit()
        logger.info(f"Saved model metadata: {model_name}")
        return metadata
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error saving model metadata: {e}")
        return None


def get_model_metadata(model_name):
    """Get model metadata."""
    try:
        return ModelMetadata.query.filter_by(model_name=model_name).order_by(
            ModelMetadata.trained_at.desc()
        ).first()
    except SQLAlchemyError as e:
        logger.error(f"Error retrieving model metadata: {e}")
        return None


def clear_user_session(session_id, account_id=None):
    """Clear a chat session and its conversations."""
    try:
        user = User.query.filter_by(session_id=session_id).first()
        if not user:
            return False
        if account_id is not None and user.account_id != account_id:
            return False

        Conversation.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        logger.info("Cleared session: %s", session_id)
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Error clearing session: %s", e)
        return False


def get_user_for_account(session_id, account_id):
    """Return a chat session if it belongs to the authenticated account."""
    try:
        user = User.query.filter_by(session_id=session_id).first()
        if not user:
            return None
        if user.account_id != account_id:
            return None
        return user
    except SQLAlchemyError as e:
        logger.error("Error retrieving account session: %s", e)
        return None
