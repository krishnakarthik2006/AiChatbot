"""Database configuration for the chatbot."""
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
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True

class DevelopmentConfig(Config):
    """Development configuration."""
    # MySQL Configuration via XAMPP
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "ai_chatbot")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    
    # SQLAlchemy Configuration
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    
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
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get the appropriate configuration."""
    env = os.getenv("FLASK_ENV", "development")
    return config.get(env, config['default'])
