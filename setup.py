"""Setup script for initializing MySQL database and training the model."""
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_mysql():
    """Create MySQL database and tables."""
    logger.info("Setting up MySQL database...")
    
    import mysql.connector
    from mysql.connector import Error
    
    try:
        # Connect to MySQL server
        connection = mysql.connector.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            port=int(os.getenv('MYSQL_PORT', 3306))
        )
        
        cursor = connection.cursor()
        
        # Create database
        db_name = os.getenv('MYSQL_DATABASE', 'ai_chatbot')
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        logger.info(f"Database '{db_name}' created/verified")
        
        # Use database
        cursor.execute(f"USE {db_name}")
        
        connection.close()
        logger.info("MySQL setup completed successfully!")
        return True
        
    except Error as e:
        logger.error(f"MySQL Error: {e}")
        return False


def setup_flask_db():
    """Setup Flask-SQLAlchemy database."""
    logger.info("Setting up Flask database...")
    
    try:
        from flask import Flask
        from backend.models import db
        from backend.config import get_config
        
        app = Flask(__name__)
        config = get_config()
        app.config.from_object(config)
        db.init_app(app)
        
        with app.app_context():
            db.create_all()
            logger.info("SQLAlchemy tables created successfully!")
            return True
    except Exception as e:
        logger.error(f"Flask DB Error: {e}")
        return False


def train_model():
    """Train the chatbot model."""
    logger.info("Training chatbot model...")
    
    try:
        import train_chatbot
        train_chatbot.main()
        logger.info("Model training completed!")
        return True
    except Exception as e:
        logger.error(f"Training Error: {e}")
        return False


def main():
    """Run complete setup."""
    logger.info("=" * 50)
    logger.info("Nexus AI Chatbot - Setup")
    logger.info("=" * 50)
    
    steps = [
        ("MySQL Database Setup", setup_mysql),
        ("Flask Database Setup", setup_flask_db),
        ("Model Training", train_model),
    ]
    
    for step_name, step_func in steps:
        logger.info(f"\n>>> {step_name}...")
        if not step_func():
            logger.error(f"Setup failed at: {step_name}")
            return False
    
    logger.info("\n" + "=" * 50)
    logger.info("✓ Setup completed successfully!")
    logger.info("Run: python app.py")
    logger.info("=" * 50)
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
