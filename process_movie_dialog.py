# ============================================================
# process_movie_dialog.py
# Processes Cornell Movie Dialog Corpus and integrates
# conversational patterns into the chatbot
# ============================================================

import json
import os
from collections import defaultdict

DATASET_PATH = r"C:\Users\KRISHNA KARTHIK\.cache\kagglehub\datasets\rajathmc\cornell-moviedialog-corpus\versions\1"
MOVIE_LINES_FILE = os.path.join(DATASET_PATH, "movie_lines.txt")
EXISTING_INTENTS_PATH = "data/intents.json"
OUTPUT_INTENTS_PATH = "data/intents.json"

# Response templates for conversational intents
CONVERSATION_RESPONSES = {
    "conversation_greeting": [
        "Hey! How are you doing today?",
        "Hi there! What's up?",
        "Hello! Great to see you!",
        "Hey! How can I help?",
        "Hi! What brings you here?"
    ],
    "conversation_question": [
        "That's a great question! Let me think about it.",
        "Good question. I can help with that.",
        "That's interesting. Tell me more.",
        "I see what you're asking. Let me explain.",
        "That's a valid point. Here's my take."
    ],
    "conversation_agreement": [
        "I totally agree with you on that!",
        "You're absolutely right about that.",
        "That's exactly how I feel!",
        "I couldn't have said it better myself.",
        "You've got a point there!"
    ],
    "conversation_disagreement": [
        "I see your point, but I have a different perspective.",
        "I understand, but let me offer another view.",
        "That's interesting, though I'd argue...",
        "I hear you, but consider this...",
        "That's one way to look at it, but..."
    ],
    "conversation_advice": [
        "Here's what I'd suggest...",
        "If I were in your position, I'd...",
        "My advice would be to...",
        "You might want to consider...",
        "Here's a tip that might help..."
    ],
    "conversation_concern": [
        "I understand your concern. Here's how we can address it.",
        "That's a valid worry. Let me help ease that.",
        "I get why you're concerned. Let me explain.",
        "That's something to think about. Here's my suggestion.",
        "Your concern is valid. Let's work through it."
    ],
    "conversation_casual": [
        "That's cool! Tell me more about that.",
        "Really? That sounds interesting!",
        "No way! I didn't know that.",
        "That's awesome! What happened next?",
        "Haha, that's funny! I love it!"
    ],
    "conversation_knowledge": [
        "Did you know that...?",
        "Here's something interesting...",
        "Fun fact: ...",
        "You might find this useful...",
        "Let me share some insights..."
    ]
}


def parse_movie_lines(filepath):
    """
    Parse movie_lines.txt and extract conversational utterances.
    Format: LineID +++$+++ CharacterID +++$+++ MovieID +++$+++ CharacterName +++$+++ Line
    """
    lines = []
    skipped = 0
    
    print(f"Reading {filepath}...")
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f):
            if line_num % 50000 == 0 and line_num > 0:
                print(f"  Processed {line_num:,} lines...")
            
            try:
                parts = line.strip().split(" +++$+++ ")
                if len(parts) == 5:
                    line_id, char_id, movie_id, char_name, utterance = parts
                    
                    # Filter: keep utterances that are reasonable length
                    utterance = utterance.strip()
                    if len(utterance) > 5 and len(utterance) < 500:
                        lines.append({
                            'id': line_id,
                            'character': char_name,
                            'text': utterance
                        })
            except Exception as e:
                skipped += 1
    
    print(f"✓ Extracted {len(lines):,} valid utterances (skipped {skipped})")
    return lines


def categorize_lines(lines):
    """Categorize lines into conversational intent groups."""
    patterns = {
        "conversation_greeting": [],
        "conversation_question": [],
        "conversation_agreement": [],
        "conversation_disagreement": [],
        "conversation_advice": [],
        "conversation_concern": [],
        "conversation_casual": [],
        "conversation_knowledge": []
    }
    
    keywords = {
        "conversation_greeting": ["hello", "hi", "hey", "howdy", "greetings", "welcome"],
        "conversation_question": ["what", "when", "where", "why", "how", "who", "?"],
        "conversation_agreement": ["yes", "agree", "right", "correct", "absolutely", "definitely", "exactly"],
        "conversation_disagreement": ["no", "disagree", "wrong", "but", "however", "instead", "rather"],
        "conversation_advice": ["should", "would", "could", "try", "suggest", "recommend", "recommend"],
        "conversation_concern": ["worry", "concern", "afraid", "scared", "nervous", "anxious", "problem"],
        "conversation_casual": ["cool", "awesome", "great", "nice", "fun", "haha", "lol", "funny"],
        "conversation_knowledge": ["know", "learned", "fact", "interesting", "research", "study", "found"]
    }
    
    print("\nCategorizing lines into conversational intents...")
    
    for i, line_data in enumerate(lines):
        if i % 50000 == 0 and i > 0:
            print(f"  Categorized {i:,} lines...")
        
        text_lower = line_data['text'].lower()
        
        # Classify based on keywords
        classified = False
        for intent, keywords_list in keywords.items():
            if any(keyword in text_lower for keyword in keywords_list):
                if len(patterns[intent]) < 30:  # Limit per category
                    patterns[intent].append(line_data['text'])
                    classified = True
                    break
        
        # If not classified, add to casual
        if not classified and len(patterns["conversation_casual"]) < 30:
            patterns["conversation_casual"].append(line_data['text'])
    
    # Print statistics
    for intent, items in patterns.items():
        if items:
            print(f"  - {intent}: {len(items)} patterns")
    
    return patterns


def load_existing_intents(filepath):
    """Load existing intents from JSON."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"intents": []}


def merge_movie_intents(existing_intents, conversation_patterns):
    """Add movie conversation intents to existing intents."""
    merged_intents = existing_intents.get("intents", [])
    existing_tags = {intent.get("tag") for intent in merged_intents}
    
    added_count = 0
    for intent_tag, patterns in conversation_patterns.items():
        if not patterns:
            continue
        
        if intent_tag in existing_tags:
            print(f"⚠ Intent '{intent_tag}' already exists, skipping.")
            continue
        
        responses = CONVERSATION_RESPONSES.get(intent_tag, [
            f"That's interesting about {intent_tag}.",
            f"I understand your point about {intent_tag}."
        ])
        
        new_intent = {
            "tag": intent_tag,
            "patterns": patterns[:20],  # Limit to 20 patterns
            "responses": responses
        }
        
        merged_intents.append(new_intent)
        print(f"✓ Added '{intent_tag}' with {len(patterns[:20])} patterns")
        added_count += 1
    
    return {"intents": merged_intents}, added_count


def main():
    print("=" * 70)
    print("  Processing Cornell Movie Dialog Corpus for Chatbot")
    print("=" * 70)
    
    # Step 1: Parse movie lines
    print("\n[1/4] Parsing movie lines...")
    lines = parse_movie_lines(MOVIE_LINES_FILE)
    
    if not lines:
        print("ERROR: No lines extracted. Exiting.")
        return
    
    # Step 2: Categorize lines
    print("\n[2/4] Categorizing lines into conversational intents...")
    conversation_patterns = categorize_lines(lines)
    
    total_patterns = sum(len(p) for p in conversation_patterns.values())
    print(f"Total patterns extracted: {total_patterns}")
    
    # Step 3: Load existing intents
    print("\n[3/4] Loading existing intents...")
    existing_intents = load_existing_intents(EXISTING_INTENTS_PATH)
    existing_count = len(existing_intents.get('intents', []))
    print(f"✓ Found {existing_count} existing intents")
    
    # Step 4: Merge intents
    print("\n[4/4] Merging movie dialog intents...")
    merged, added = merge_movie_intents(existing_intents, conversation_patterns)
    
    # Save merged intents
    with open(OUTPUT_INTENTS_PATH, 'w') as f:
        json.dump(merged, f, indent=2)
    
    total_intents = len(merged["intents"])
    total_patterns_all = sum(len(intent.get("patterns", [])) for intent in merged["intents"])
    
    print(f"\n{'=' * 70}")
    print(f"✓ Merged intents saved to {OUTPUT_INTENTS_PATH}")
    print(f"  Intents added: {added}")
    print(f"  Total intents: {total_intents}")
    print(f"  Total patterns: {total_patterns_all}")
    print(f"\nNext step: python train_model.py")
    print(f"{'=' * 70}\n")


if __name__ == '__main__':
    main()
