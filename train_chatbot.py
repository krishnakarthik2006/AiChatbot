"""Training script to train the chatbot model and save to database."""
import json
import os
import pickle
import logging
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Download NLTK resources
for resource in ['punkt', 'stopwords', 'wordnet']:
    try:
        nltk.data.find(f'tokenizers/{resource}')
    except LookupError:
        nltk.download(resource, quiet=True)


class NLTKPreprocessor:
    """NLTK-based text preprocessing."""
    
    def __init__(self):
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))
    
    def preprocess(self, text):
        """Preprocess text using NLTK."""
        text = text.lower()
        tokens = word_tokenize(text)
        tokens = [
            self.lemmatizer.lemmatize(token)
            for token in tokens
            if token.isalnum() and token not in self.stop_words
        ]
        return ' '.join(tokens)


def load_intents(filepath):
    """Load intents from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def prepare_training_data(intents_data):
    """Prepare training data from intents."""
    patterns = []
    labels = []
    tag_responses = {}
    
    for intent in intents_data.get('intents', []):
        tag = intent['tag']
        tag_responses[tag] = intent.get('responses', [])
        
        for pattern in intent.get('patterns', []):
            patterns.append(pattern)
            labels.append(tag)
    
    return patterns, labels, tag_responses


def train_model(patterns, labels, preprocessor, model_path, vectorizer_path, intents_path):
    """Train TF-IDF + Logistic Regression model."""
    logger.info(f"Training model with {len(set(labels))} intents and {len(patterns)} samples...")
    
    # Preprocess patterns
    processed_patterns = [preprocessor.preprocess(pattern) for pattern in patterns]
    
    # TF-IDF Vectorizer
    vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
    X = vectorizer.fit_transform(processed_patterns)
    
    # Logistic Regression Classifier
    classifier = LogisticRegression(max_iter=200, random_state=42, multi_class='multinomial')
    classifier.fit(X, labels)
    
    # Get classes
    classes = list(classifier.classes_)
    
    # Save model
    os.makedirs(os.path.dirname(model_path) or '.', exist_ok=True)
    
    with open(model_path, 'wb') as f:
        pickle.dump(classifier, f)
    logger.info(f"Model saved to {model_path}")
    
    with open(vectorizer_path, 'wb') as f:
        pickle.dump(vectorizer, f)
    logger.info(f"Vectorizer saved to {vectorizer_path}")
    
    # Calculate accuracy on training data
    accuracy = classifier.score(X, labels)
    
    # Save metadata
    metadata = {
        'classes': classes,
        'tag_responses': {},
        'confidence_threshold': 0.35,
        'accuracy': float(accuracy),
        'intents_count': len(set(labels)),
        'training_samples': len(patterns),
    }
    
    with open(intents_path, 'wb') as f:
        pickle.dump(metadata, f)
    logger.info(f"Metadata saved to {intents_path}")
    
    logger.info(f"Training complete! Accuracy: {accuracy:.2%}")
    return classifier, vectorizer, metadata


def save_intents_to_db(intents_data):
    """Save intents to MySQL database."""
    try:
        from flask import Flask
        from backend.database import save_intent, init_db
        from backend.config import get_config
        from backend.models import db
        
        app = Flask(__name__)
        config = get_config()
        app.config.from_object(config)
        db.init_app(app)
        
        with app.app_context():
            init_db(app)
            for intent in intents_data.get('intents', []):
                save_intent(
                    tag=intent['tag'],
                    patterns=intent.get('patterns', []),
                    responses=intent.get('responses', [])
                )
            logger.info("Intents saved to database")
    except Exception as e:
        logger.warning(f"Could not save intents to database: {e}")


def main():
    """Main training function."""
    intents_file = 'backend/intents.json'
    model_path = 'model/chatbot_model.pkl'
    vectorizer_path = 'model/vectorizer.pkl'
    intents_path = 'model/intents_data.pkl'
    
    # Ensure model directory exists
    Path('model').mkdir(exist_ok=True)
    
    # Load intents
    logger.info(f"Loading intents from {intents_file}")
    intents_data = load_intents(intents_file)
    
    # Prepare data
    patterns, labels, tag_responses = prepare_training_data(intents_data)
    logger.info(f"Prepared {len(patterns)} patterns for {len(set(labels))} intents")
    
    # Initialize preprocessor
    preprocessor = NLTKPreprocessor()
    
    # Train model
    classifier, vectorizer, metadata = train_model(
        patterns, labels, preprocessor, model_path, vectorizer_path, intents_path
    )
    
    # Update metadata with tag_responses
    metadata['tag_responses'] = tag_responses
    with open(intents_path, 'wb') as f:
        pickle.dump(metadata, f)
    
    # Try to save to database
    save_intents_to_db(intents_data)
    
    logger.info("Training completed successfully!")


if __name__ == '__main__':
    main()
