import re

import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer


stemmer = PorterStemmer()


def _ensure_nltk_package(resource: str, package: str) -> bool:
    try:
        nltk.data.find(resource)
        return True
    except LookupError:
        try:
            return bool(nltk.download(package, quiet=True))
        except Exception:
            return False


HAS_TOKENIZER = _ensure_nltk_package("tokenizers/punkt", "punkt")
_ensure_nltk_package("tokenizers/punkt_tab", "punkt_tab")

try:
    _ensure_nltk_package("corpora/stopwords", "stopwords")
    STOPWORDS = set(stopwords.words("english"))
except LookupError:
    STOPWORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }


def tokenize(sentence: str) -> list[str]:
    if HAS_TOKENIZER:
        try:
            return nltk.word_tokenize(sentence)
        except LookupError:
            pass
    return re.findall(r"[a-zA-Z]+", sentence)


def stem(word: str) -> str:
    return stemmer.stem(word.lower())


def clean_and_stem(sentence: str, remove_stopwords: bool = True) -> str:
    sentence = sentence.lower()
    sentence = re.sub(r"[^a-z\s]", "", sentence)
    tokens = tokenize(sentence)

    if remove_stopwords:
        tokens = [token for token in tokens if token not in STOPWORDS]

    return " ".join(stem(token) for token in tokens if token.strip())


def preprocess_patterns(patterns: list[str]) -> list[str]:
    return [clean_and_stem(pattern) for pattern in patterns]


if __name__ == "__main__":
    examples = [
        "Hello, how are you doing today?",
        "Tell me a funny joke please!",
        "What is machine learning?",
        "I need some help with coding.",
    ]
    for example in examples:
        print(f"{example} -> {clean_and_stem(example)}")
