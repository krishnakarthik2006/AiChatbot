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


PLACEHOLDER_VALUES = {
    "change-me-to-a-long-random-string",
    "dev-secret-change-in-production",
    "your-key-here",
    "your-secret-key",
    "changeme",
    "change-me",
    "placeholder",
    "secret",
    "password",
}


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered or lowered in PLACEHOLDER_VALUES:
        return True
    return any(token in lowered for token in ("your-", "change-me", "placeholder", "replace-with"))


def check_env_placeholders() -> list[dict]:
    """Report environment values that are still set to their .env.example placeholders."""
    problems: list[dict] = []
    secret = os.getenv("SECRET_KEY", "")
    if _looks_like_placeholder(secret):
        problems.append({
            "key": "SECRET_KEY",
            "value": secret or "(empty)",
            "hint": "Set a long, random SECRET_KEY in .env. It signs all login tokens.",
        })
    groq = os.getenv("GROQ_API_KEY", "")
    if _looks_like_placeholder(groq):
        problems.append({
            "key": "GROQ_API_KEY",
            "value": groq or "(empty)",
            "hint": "Optional unless query rewriting uses Groq. Leave blank to fall back to a local model.",
        })
    return problems


def warn_placeholders(logger) -> None:
    """Log a warning for every environment value still set to a template placeholder."""
    for problem in check_env_placeholders():
        logger.warning(
            "Configuration placeholder %s=%r — %s",
            problem["key"], problem["value"], problem["hint"],
        )
