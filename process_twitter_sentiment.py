# ============================================================
# process_twitter_sentiment.py
# Processes Twitter Entity Sentiment Analysis dataset from Kaggle
# and integrates sentiment-based intents into the chatbot
# ============================================================

import json
import kagglehub
from kagglehub import KaggleDatasetAdapter
from collections import defaultdict

# Load the Twitter sentiment dataset
print("Loading Twitter Entity Sentiment Analysis dataset...")
try:
    df = kagglehub.load_dataset(
        KaggleDatasetAdapter.PANDAS,
        "jp797498e/twitter-entity-sentiment-analysis"
    )
except Exception as e:
    print(f"Error loading dataset: {e}")
    print("Attempting alternative approach...")
    import os
    import pandas as pd
    
    # Alternative: Download and load manually
    dataset_path = kagglehub.dataset_download("jp797498e/twitter-entity-sentiment-analysis")
    csv_files = [f for f in os.listdir(dataset_path) if f.endswith('.csv')]
    
    if csv_files:
        df = pd.read_csv(os.path.join(dataset_path, csv_files[0]), header=None, names=["ID", "Entity", "Sentiment", "Tweet"])
    else:
        raise FileNotFoundError("No CSV files found in dataset")

print(f"✓ Loaded {len(df)} tweets")
print(f"Sentiment distribution: {df['Sentiment'].value_counts().to_dict()}\n")

# Paths
EXISTING_INTENTS_PATH = "data/intents.json"
OUTPUT_INTENTS_PATH = "data/intents.json"

# Sentiment response templates
SENTIMENT_RESPONSES = {
    "positive_sentiment": [
        "That's wonderful to hear! I'm glad you're feeling positive!",
        "Awesome! It sounds like things are going great for you!",
        "That's fantastic! Your enthusiasm is contagious!",
        "I love the positive energy! Keep it up!"
    ],
    "negative_sentiment": [
        "I understand you're feeling frustrated. Let me help if I can.",
        "I'm sorry to hear that. What can I do to assist?",
        "That sounds challenging. I'm here to support you.",
        "Don't worry, things often look better with a fresh perspective."
    ],
    "neutral_sentiment": [
        "I appreciate you sharing that perspective.",
        "That's an interesting point. Tell me more.",
        "I see your point. What would you like to know?",
        "That's a fair observation. How can I assist further?"
    ],
    "emotion_happy": [
        "Your happiness is contagious! That's wonderful!",
        "Great to see you in such good spirits!",
        "I love the positive vibes!",
        "Your joy is inspiring!"
    ],
    "emotion_angry": [
        "I sense some frustration. Take a deep breath.",
        "I understand your anger. Let's work through this together.",
        "It's okay to feel upset. How can I help calm things down?",
        "I hear the intensity in your words. What's bothering you?"
    ],
    "emotion_sad": [
        "I'm here for you during tough times.",
        "It's okay to feel sad sometimes. How can I support you?",
        "I hear the sadness in your words. Let's talk about it.",
        "You're not alone. I'm here to help."
    ],
    "emotion_confused": [
        "That's a confusing situation. Let me help clarify.",
        "I understand the confusion. Let's break this down together.",
        "Sometimes things are unclear. What specifically confuses you?",
        "It's okay to be unsure. I'm here to help explain."
    ],
    "emotion_excited": [
        "Your excitement is amazing! Tell me more!",
        "I can feel your enthusiasm! What's got you so energized?",
        "That excitement is wonderful! What's the good news?",
        "Your energy is inspiring! Keep that momentum going!"
    ],
    "feedback_positive": [
        "Thank you for the positive feedback! I appreciate it.",
        "I'm glad I could help! That makes me happy.",
        "Your kind words mean a lot. How else can I assist?",
        "I'm thrilled you're satisfied with my help!"
    ],
    "feedback_negative": [
        "Thank you for the honest feedback. I'll improve.",
        "I appreciate you pointing that out. Let me do better.",
        "I hear your criticism. How can I improve?",
        "Your feedback helps me grow. What can I do differently?"
    ]
}

# Extract sentiment patterns from tweets
def extract_sentiment_patterns():
    """Extract positive, negative, and neutral patterns from the dataset."""
    patterns = {
        "positive_sentiment": [],
        "negative_sentiment": [],
        "neutral_sentiment": [],
        "emotion_happy": [],
        "emotion_angry": [],
        "emotion_sad": [],
        "emotion_confused": [],
        "emotion_excited": [],
        "feedback_positive": [],
        "feedback_negative": []
    }
    
    for idx, row in df.iterrows():
        sentiment = row['Sentiment'].lower()
        tweet = row['Tweet']
        
        # Skip rows with missing data
        if not isinstance(tweet, str) or not tweet.strip():
            continue
        
        tweet = tweet.strip()
        
        # Map sentiments to intent tags
        if sentiment == 'positive':
            if len(patterns["positive_sentiment"]) < 20:
                patterns["positive_sentiment"].append(tweet)
            if 'great' in tweet.lower() or 'amazing' in tweet.lower() or 'awesome' in tweet.lower():
                if len(patterns["emotion_excited"]) < 15:
                    patterns["emotion_excited"].append(tweet)
            elif 'love' in tweet.lower() or 'happy' in tweet.lower():
                if len(patterns["emotion_happy"]) < 15:
                    patterns["emotion_happy"].append(tweet)
            elif 'good' in tweet.lower() or 'nice' in tweet.lower() or 'thanks' in tweet.lower():
                if len(patterns["feedback_positive"]) < 15:
                    patterns["feedback_positive"].append(tweet)
                    
        elif sentiment == 'negative':
            if len(patterns["negative_sentiment"]) < 20:
                patterns["negative_sentiment"].append(tweet)
            if 'angry' in tweet.lower() or 'hate' in tweet.lower() or '!' in tweet:
                if len(patterns["emotion_angry"]) < 15:
                    patterns["emotion_angry"].append(tweet)
            elif 'sad' in tweet.lower() or 'hurt' in tweet.lower() or 'upset' in tweet.lower():
                if len(patterns["emotion_sad"]) < 15:
                    patterns["emotion_sad"].append(tweet)
            elif 'bad' in tweet.lower() or 'worse' in tweet.lower() or 'poor' in tweet.lower():
                if len(patterns["feedback_negative"]) < 15:
                    patterns["feedback_negative"].append(tweet)
                    
        elif sentiment == 'neutral':
            if len(patterns["neutral_sentiment"]) < 15:
                patterns["neutral_sentiment"].append(tweet)
                if '?' in tweet:
                    if len(patterns["emotion_confused"]) < 10:
                        patterns["emotion_confused"].append(tweet)
    
    return patterns


def load_existing_intents(filepath):
    """Load existing intents from JSON."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"intents": []}


def merge_sentiment_intents(existing_intents, sentiment_patterns):
    """Add sentiment-based intents to existing intents."""
    merged_intents = existing_intents.get("intents", [])
    existing_tags = {intent.get("tag") for intent in merged_intents}
    
    for intent_tag, patterns in sentiment_patterns.items():
        if not patterns:
            continue
            
        if intent_tag in existing_tags:
            print(f"⚠ Intent '{intent_tag}' already exists, skipping.")
            continue
        
        responses = SENTIMENT_RESPONSES.get(intent_tag, [
            f"Thank you for sharing that about {intent_tag}.",
            f"I understand your {intent_tag}."
        ])
        
        new_intent = {
            "tag": intent_tag,
            "patterns": patterns[:15],  # Limit to 15 patterns
            "responses": responses
        }
        
        merged_intents.append(new_intent)
        print(f"✓ Added '{intent_tag}' with {len(patterns[:15])} patterns")
    
    return {"intents": merged_intents}


def main():
    print("\n" + "=" * 60)
    print("  Processing Twitter Sentiment Dataset for Chatbot")
    print("=" * 60)
    
    # Step 1: Extract patterns from tweets
    print("\n[1/3] Extracting sentiment patterns from tweets...")
    sentiment_patterns = extract_sentiment_patterns()
    total_patterns = sum(len(p) for p in sentiment_patterns.values())
    print(f"✓ Extracted {total_patterns} sentiment patterns")
    for tag, patterns in sentiment_patterns.items():
        if patterns:
            print(f"  - {tag}: {len(patterns)} patterns")
    
    # Step 2: Load existing intents
    print("\n[2/3] Loading existing intents...")
    existing_intents = load_existing_intents(EXISTING_INTENTS_PATH)
    print(f"✓ Found {len(existing_intents.get('intents', []))} existing intents")
    
    # Step 3: Merge sentiment intents
    print("\n[3/3] Merging sentiment intents...")
    merged = merge_sentiment_intents(existing_intents, sentiment_patterns)
    
    # Save merged intents
    with open(OUTPUT_INTENTS_PATH, 'w') as f:
        json.dump(merged, f, indent=2)
    
    total_intents = len(merged["intents"])
    total_patterns_all = sum(len(intent.get("patterns", [])) for intent in merged["intents"])
    
    print(f"\n{'=' * 60}")
    print(f"✓ Merged intents saved to {OUTPUT_INTENTS_PATH}")
    print(f"  Total intents: {total_intents}")
    print(f"  Total patterns: {total_patterns_all}")
    print(f"\nNext steps:")
    print(f"  1. Run: python train_model.py")
    print(f"  2. Run: python app.py")
    print(f"{'=' * 60}\n")


if __name__ == '__main__':
    main()
