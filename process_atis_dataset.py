# ============================================================
# process_atis_dataset.py
# Processes the ATIS (Airline Travel Information System)
# dataset from Kaggle and integrates it with existing intents
# ============================================================

import json
import csv
from collections import defaultdict

# Paths
ATIS_DATASET_PATH = r"C:\Users\KRISHNA KARTHIK\.cache\kagglehub\datasets\hassanamin\atis-airlinetravelinformationsystem\versions\1\atis_intents_train.csv"
EXISTING_INTENTS_PATH = "data/intents.json"
OUTPUT_INTENTS_PATH = "data/intents.json"

# Response templates for ATIS intents
ATIS_RESPONSES = {
    "atis_flight": [
        "I found several flight options for you! Here are the available departures.",
        "Let me search for flights matching your criteria.",
        "I can help you find the perfect flight!",
        "Based on your preferences, here are the available flights."
    ],
    "atis_airfare": [
        "I can provide you with airfare information.",
        "Let me check the current fares for your route.",
        "Here are the fares available for your journey.",
        "I found several airfare options within your budget."
    ],
    "atis_aircraft": [
        "The aircraft used on this route is listed in your booking details.",
        "Let me provide information about the aircraft for this flight.",
        "Here's the aircraft information for your flight.",
        "I can tell you more about the aircraft on this route."
    ],
    "atis_ground_service": [
        "Ground transportation options are available at your destination.",
        "I can help you with ground transportation arrangements.",
        "Here are the ground service options available.",
        "Let me provide ground transportation details for you."
    ],
    "atis_airport": [
        "I have airport information available for you.",
        "Let me provide details about this airport.",
        "Here's the airport information you requested.",
        "I can help you with airport details."
    ],
    "atis_flight_time": [
        "Here's the flight time information you requested.",
        "Let me provide the arrival and departure times.",
        "I found the flight timing details for you.",
        "Here are the time details for your flight."
    ],
    "atis_airline": [
        "I have airline information available.",
        "Let me provide details about this airline.",
        "Here's the information about this airline.",
        "I can help with airline-specific details."
    ],
    "atis_restriction": [
        "Here are the restrictions that apply to your booking.",
        "Let me provide information about booking restrictions.",
        "I found the relevant restrictions for your journey.",
        "Here are the important restrictions you should know about."
    ],
    "atis_cheapest": [
        "I found the most affordable options for you.",
        "Here are the cheapest fares available.",
        "Let me show you the best deals available.",
        "I found budget-friendly flight options for you."
    ],
}


def load_atis_dataset(filepath):
    """Load ATIS dataset from CSV and group by intent."""
    intents_data = defaultdict(list)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split(', ', 1)
                if len(parts) == 2:
                    intent_tag = parts[0].strip()
                    utterance = parts[1].strip()
                    intents_data[intent_tag].append(utterance)
        
        print(f"✓ Loaded {len(intents_data)} unique intents from ATIS dataset")
        for tag, utterances in intents_data.items():
            print(f"  - {tag}: {len(utterances)} utterances")
        
        return intents_data
    except FileNotFoundError:
        print(f"ERROR: File not found: {filepath}")
        return {}


def load_existing_intents(filepath):
    """Load existing intents from JSON."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"No existing intents file found. Creating new structure.")
        return {"intents": []}


def merge_intents(existing_intents, atis_intents):
    """Merge ATIS intents with existing intents."""
    merged_intents = existing_intents.get("intents", [])
    existing_tags = {intent.get("tag") for intent in merged_intents}
    
    # Add ATIS intents
    for atis_tag, utterances in atis_intents.items():
        # Skip if already exists
        if atis_tag in existing_tags:
            print(f"⚠ Intent '{atis_tag}' already exists, skipping.")
            continue
        
        # Get responses for this intent
        responses = ATIS_RESPONSES.get(atis_tag, [
            f"I can help with {atis_tag.replace('atis_', '')}.",
            f"Let me assist you with {atis_tag.replace('atis_', '')}.",
        ])
        
        new_intent = {
            "tag": atis_tag,
            "patterns": utterances[:15],  # Limit to 15 patterns per intent
            "responses": responses
        }
        
        merged_intents.append(new_intent)
        print(f"✓ Added '{atis_tag}' with {len(utterances[:15])} patterns")
    
    return {"intents": merged_intents}


def main():
    print("=" * 60)
    print("      Processing ATIS Dataset for Chatbot")
    print("=" * 60)
    
    # Step 1: Load ATIS dataset
    print("\n[1/3] Loading ATIS dataset...")
    atis_intents = load_atis_dataset(ATIS_DATASET_PATH)
    
    if not atis_intents:
        print("ERROR: Could not load ATIS dataset. Exiting.")
        return
    
    # Step 2: Load existing intents
    print("\n[2/3] Loading existing intents...")
    existing_intents = load_existing_intents(EXISTING_INTENTS_PATH)
    print(f"✓ Found {len(existing_intents.get('intents', []))} existing intents")
    
    # Step 3: Merge intents
    print("\n[3/3] Merging intents...")
    merged = merge_intents(existing_intents, atis_intents)
    
    # Save merged intents
    with open(OUTPUT_INTENTS_PATH, 'w') as f:
        json.dump(merged, f, indent=2)
    
    total_intents = len(merged["intents"])
    total_patterns = sum(len(intent.get("patterns", [])) for intent in merged["intents"])
    
    print(f"\n{'=' * 60}")
    print(f"✓ Merged intents saved to {OUTPUT_INTENTS_PATH}")
    print(f"  Total intents: {total_intents}")
    print(f"  Total patterns: {total_patterns}")
    print(f"\nYou can now run: python train_model.py")
    print(f"{'=' * 60}\n")


if __name__ == '__main__':
    main()
