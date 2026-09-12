"""Flask configuration for the local, ChromaDB-enabled chatbot."""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration."""
    DEBUG = os.getenv("FLASK_DEBUG", False)
    TESTING = False
    BOT_NAME = os.getenv("BOT_NAME", "Nexus")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    RAG_ADMIN_EMAILS = os.getenv("RAG_ADMIN_EMAILS", "")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True

class DevelopmentConfig(Config):
    """Development configuration."""
    # Flask-SocketIO Configuration
    SOCKETIO_ASYNC_MODE = 'threading'
    
    # Session Configuration
    SESSION_TIMEOUT = 86400  # 24 hours
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=86400)
    MAX_STORED_MESSAGES = 28

    # CORS (React dev server)
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get the appropriate configuration."""
    env = os.getenv("FLASK_ENV", "development")
    return config.get(env, config['default'])
