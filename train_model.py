# ============================================================
# train_model.py
# Trains an intent classification model using:
#   - TF-IDF for feature extraction
#   - Logistic Regression for classification
#   - Confidence threshold for fallback responses
# Run this script once before starting the Flask app.
# ============================================================

import json
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from preprocessing import preprocess_patterns

# ── Configuration ───────────────────────────────────────────
DATA_PATH    = 'data/intents.json'
MODEL_PATH   = 'model/chatbot_model.pkl'
VECTORIZER_PATH = 'model/vectorizer.pkl'
INTENTS_PATH = 'model/intents_data.pkl'

# Minimum confidence to return a result (below this = fallback)
CONFIDENCE_THRESHOLD = 0.35


def load_intents(filepath: str) -> dict:
    """Load and return the intents JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def build_training_data(intents: dict):
    """
    Convert intents.json into (X, y) training data.

    Returns:
        X_text : list of preprocessed sentences
        y_labels: list of corresponding intent tags
        tag_responses: dict mapping tag → list of responses
    """
    X_text    = []
    y_labels  = []
    tag_responses = {}

    for intent in intents['intents']:
        tag = intent['tag']
        tag_responses[tag] = intent['responses']

        # Preprocess each training pattern and assign its label
        for pattern in intent['patterns']:
            processed = preprocess_patterns([pattern])[0]
            X_text.append(processed)
            y_labels.append(tag)

    return X_text, y_labels, tag_responses


def train(data_path: str = DATA_PATH):
    """
    Full training pipeline:
    1. Load intents
    2. Build training data
    3. Vectorize with TF-IDF
    4. Train Logistic Regression
    5. Evaluate on test split
    6. Save model, vectorizer, and metadata
    """
    print("=" * 50)
    print("       AI Chatbot — Model Training")
    print("=" * 50)

    # ── Step 1: Load data ────────────────────────────────────
    print("\n[1/5] Loading intents dataset...")
    intents = load_intents(data_path)
    print(f"      Found {len(intents['intents'])} intents.")

    # ── Step 2: Build training corpus ────────────────────────
    print("[2/5] Building training corpus...")
    X_text, y_labels, tag_responses = build_training_data(intents)
    print(f"      Total training samples: {len(X_text)}")

    # ── Step 3: TF-IDF Vectorization ─────────────────────────
    # TF-IDF converts text to numerical feature vectors.
    # n-grams (1,2) captures single words AND two-word phrases.
    print("[3/5] Applying TF-IDF vectorization...")
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),   # Use unigrams and bigrams
        min_df=1,             # Include terms that appear at least once
        max_features=5000     # Cap vocabulary size
    )
    X = vectorizer.fit_transform(X_text)
    print(f"      Vocabulary size: {len(vectorizer.vocabulary_)}")

    # ── Step 4: Train/Test split + Logistic Regression ───────
    print("[4/5] Training Logistic Regression model...")

    # Split: 80% train, 20% test (stratified to balance classes)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_labels, test_size=0.2, random_state=42, stratify=y_labels
    )

    model = LogisticRegression(
        max_iter=500,        # Allow enough iterations to converge
        C=5.0,               # Regularization strength (higher = less reg)
        solver='liblinear',  # More stable on Windows than lbfgs
        random_state=42      # For reproducibility
    )
    model.fit(X_train, y_train)

    # ── Step 5: Evaluation ───────────────────────────────────
    print("[5/5] Evaluating model performance...")
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n      Test Accuracy: {acc * 100:.2f}%")
    print("\n--- Classification Report ---")
    print(classification_report(y_test, y_pred, zero_division=0))

    # ── Save artifacts ───────────────────────────────────────
    print("Saving model artifacts...")

    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)

    with open(VECTORIZER_PATH, 'wb') as f:
        pickle.dump(vectorizer, f)

    # Save tag→responses map + classes list for inference
    intents_metadata = {
        'tag_responses': tag_responses,
        'classes': list(model.classes_),
        'confidence_threshold': CONFIDENCE_THRESHOLD
    }
    with open(INTENTS_PATH, 'wb') as f:
        pickle.dump(intents_metadata, f)

    print(f"\n✓ Model saved     → {MODEL_PATH}")
    print(f"✓ Vectorizer saved → {VECTORIZER_PATH}")
    print(f"✓ Metadata saved   → {INTENTS_PATH}")
    print("\nTraining complete! You can now run app.py.\n")

    return model, vectorizer, intents_metadata


# ── Entry point ──────────────────────────────────────────────
if __name__ == '__main__':
    train()
