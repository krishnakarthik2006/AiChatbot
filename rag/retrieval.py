"""BM25 lexical scorer for hybrid retrieval.

Kept dependency-free so the hybrid pipeline works without extra installs.
Score formula: Okapi BM25 with k1=1.5, b=0.75.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

_TOKEN_RE = re.compile(r"[\w'-]{2,}")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens; hyphens and apostrophes stay inside words."""
    return [token.lower() for token in _TOKEN_RE.findall(text or "")]


class BM25:
    """In-memory Okapi BM25 index over a fixed corpus."""

    def __init__(self, corpus: Iterable[str]) -> None:
        self._docs = [tokenize(doc) for doc in corpus]
        self.doc_count = len(self._docs)
        self.doc_len = [len(doc) for doc in self._docs]
        self.avgdl = sum(self.doc_len) / self.doc_count if self.doc_count else 0.0
        doc_freq: Counter[str] = Counter()
        for doc in self._docs:
            doc_freq.update(set(doc))
        self.doc_freq = doc_freq
        n = self.doc_count
        self.idf = {
            term: math.log(1 + (n - freq + 0.5) / (freq + 0.5))
            for term, freq in doc_freq.items()
        }

    def score(self, query: str) -> list[float]:
        """BM25 relevance for each corpus document, in corpus order."""
        if self.doc_count == 0:
            return []
        k1, b = 1.5, 0.75
        terms = set(tokenize(query))
        scores = [0.0] * self.doc_count
        for term in terms:
            idf = self.idf.get(term, 0.0)
            if idf <= 0:
                continue
            for index, doc in enumerate(self._docs):
                freq = doc.count(term)
                if not freq:
                    continue
                denom = freq + k1 * (1 - b + b * self.doc_len[index] / self.avgdl) if self.avgdl else freq + k1
                scores[index] += idf * (freq * (k1 + 1)) / denom
        return scores