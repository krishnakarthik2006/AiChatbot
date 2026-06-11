"""Enhanced Chatbot with NLTK NLP and database integration."""
from __future__ import annotations

import ast
import operator
import pickle
import os
import random
import re
import logging
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

from local_llm import LocalLLMClient, LocalLLMError

logger = logging.getLogger(__name__)

load_dotenv()

def ensure_nltk_resource(resource_name: str, lookup_paths: tuple[str, ...]) -> None:
    for lookup_path in lookup_paths:
        try:
            nltk.data.find(lookup_path)
            return
        except LookupError:
            continue

    try:
        nltk.download(resource_name, quiet=True, raise_on_error=True)
    except Exception as exc:
        logger.warning("NLTK resource '%s' is unavailable: %s", resource_name, exc)


ensure_nltk_resource('punkt', ('tokenizers/punkt', 'tokenizers/punkt.zip'))
ensure_nltk_resource('stopwords', ('corpora/stopwords', 'corpora/stopwords.zip'))
ensure_nltk_resource('wordnet', ('corpora/wordnet', 'corpora/wordnet.zip'))


MODEL_PATH = "model/chatbot_model.pkl"
VECTORIZER_PATH = "model/vectorizer.pkl"
INTENTS_PATH = "model/intents_data.pkl"

MAX_HISTORY_MESSAGES = 14
CONFIDENCE_THRESHOLD = 0.35

FALLBACK_RESPONSES = [
    "I do not have that in my custom model yet. Try asking in a different way.",
    "That is outside my trained intents for now, but I can help with supported topics.",
    "Teach me that by adding patterns and responses to your intents data, then retrain the model.",
]

BOT_NAME = os.getenv("BOT_NAME", "Nexus")

BASE_SYSTEM_PROMPT = f"""
You are {BOT_NAME}, a private AI assistant running on the user's computer.
You are a local, custom-built assistant — not a third-party cloud service.
Be helpful, direct, and conversational.
When sharing code, put a short explanation in plain text first, then place the code inside a fenced markdown block like ```c ... ``` on its own.
""".strip()

MODE_PROMPTS = {
    'precise': 'Favor concise, careful answers.',
    'balanced': 'Balance depth with speed.',
    'creative': 'Offer richer ideas and alternatives.',
}

MATH_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class NLTKPreprocessor:
    """NLTK-based text preprocessing."""
    
    def __init__(self):
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))
    
    def preprocess(self, text: str) -> str:
        """Preprocess text using NLTK."""
        text = text.lower()
        tokens = word_tokenize(text)
        tokens = [
            self.lemmatizer.lemmatize(token)
            for token in tokens
            if token.isalnum() and token not in self.stop_words
        ]
        return ' '.join(tokens)


class Chatbot:
    """Hybrid assistant: local LLM first, deterministic tools, intent fallback."""

    def __init__(self) -> None:
        self.model = None
        self.vectorizer = None
        self.tag_responses: dict[str, list[str]] = {}
        self.classes: list[str] = []
        self.confidence_threshold = CONFIDENCE_THRESHOLD
        self.intent_model_loaded = False
        self.enable_local_llm = os.getenv("ENABLE_LOCAL_LLM", "0") == "1"
        self.local_llm = LocalLLMClient() if self.enable_local_llm else None
        self.preprocessor = NLTKPreprocessor()
        self._load_intent_model()

    def _load_intent_model(self) -> None:
        """Load trained model and vectorizer from files."""
        try:
            with open(MODEL_PATH, "rb") as file:
                self.model = pickle.load(file)
            with open(VECTORIZER_PATH, "rb") as file:
                self.vectorizer = pickle.load(file)
            with open(INTENTS_PATH, "rb") as file:
                metadata = pickle.load(file)
            self.tag_responses = metadata.get("tag_responses", {})
            self.classes = list(metadata.get("classes", []))
            self.intent_model_loaded = True
        except FileNotFoundError:
            self.intent_model_loaded = False

    def get_status(self) -> dict:
        return {
            "intent_model_loaded": self.intent_model_loaded,
            "intents_count": len(self.classes),
            "confidence_threshold": self.confidence_threshold,
            "custom_model": {
                "available": self.intent_model_loaded,
                "type": "intent_classifier",
                "primary": True,
            },
            "local_llm": self.local_llm.status() if self.local_llm else {
                "available": False,
                "base_url": None,
                "model": None,
                "active_model": None,
                "model_ready": False,
                "installed_models": [],
                "error": "Local LLM is disabled. Enable ENABLE_LOCAL_LLM=1 to use Ollama.",
            },
        }

    def predict_intent(self, user_input: str) -> tuple[str, float]:
        if not self.intent_model_loaded or self.model is None:
            return "unknown", 0.0
        processed = self.preprocessor.preprocess(user_input)
        vector = self.vectorizer.transform([processed])
        probabilities = self.model.predict_proba(vector)[0]
        max_index = np.argmax(probabilities)
        return self.classes[max_index], float(probabilities[max_index])

    def get_response(self, user_input: str, history: list[dict] | None = None, mode: str = "balanced", temperature: float | None = None) -> dict:
        user_input = (user_input or "").strip()
        if not user_input:
            return self._result("Please type something.", "empty", 0.0, False, "system")
        
        intent, confidence = self.predict_intent(user_input)
        
        if confidence >= self.confidence_threshold and intent in self.tag_responses:
            return self._result(random.choice(self.tag_responses[intent]), intent, confidence, True, "custom_model", local_model=self.get_status().get("local_llm"))

        local_status = self.local_llm.status() if self.local_llm else self.get_status().get("local_llm")

        if self.local_llm and local_status.get("available") and local_status.get("model_ready"):
            try:
                messages = self._build_messages(user_input, history or [], mode)
                llm_response = self.local_llm.chat(messages, temperature=self._temperature_for(mode, temperature))
                return self._result(llm_response["content"], intent, confidence, True, "local_llm", model=llm_response["model"], local_model=local_status)
            except LocalLLMError:
                pass
        
        return self._result(random.choice(FALLBACK_RESPONSES), intent or "offline", confidence, False, "custom_model", local_model=local_status)

    def _build_messages(self, user_input: str, history: list[dict], mode: str) -> list[dict]:
        mode_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS["balanced"])
        messages = [{"role": "system", "content": f"{BASE_SYSTEM_PROMPT}\n\n{mode_prompt}"}]
        for item in history[-MAX_HISTORY_MESSAGES:]:
            messages.append(item)
        messages.append({"role": "user", "content": user_input})
        return messages

    def _temperature_for(self, mode: str, temperature: float | None) -> float:
        if temperature is not None:
            return temperature
        return {"precise": 0.2, "balanced": 0.45, "creative": 0.75}.get(mode, 0.45)

    def _result(self, response: str, intent: str, confidence: float, understood: bool, engine: str, model: str | None = None, local_model: dict | None = None) -> dict:
        return {
            "response": response,
            "intent": intent,
            "confidence": round(confidence, 3) if confidence else 0.0,
            "understood": understood,
            "engine": engine,
            "model": model,
            "local_model": local_model or self.local_llm.status(),
        }
