"""Source-quality controls for freshness, duplicate versions, and possible conflicts."""
from __future__ import annotations

import re
from collections import defaultdict

from .storage import list_documents


DATE_PATTERN = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")


def source_quality(owner_id: str) -> dict:
    documents = list_documents(owner_id)
    versions = defaultdict(list)
    for document in documents:
        versions[document["name"].lower()].append(document)
    duplicate_names = [name for name, items in versions.items() if len(items) > 1]
    return {
        "documents": documents,
        "freshness": [{"source": item["name"], "updated_at": item["updated_at"], "version": item["version"]} for item in documents],
        "duplicate_sources": duplicate_names,
        "guidance": "Review documents with overlapping topics or conflicting dates before relying on them for decisions.",
    }


def conflict_signals(chunks: list) -> list[dict]:
    """Flag sources that present different date-like values around the same lexical topic."""
    by_topic = defaultdict(set)
    for chunk in chunks:
        topic = " ".join(re.findall(r"[A-Za-z]{5,}", chunk.content.lower())[:3])
        dates = DATE_PATTERN.findall(chunk.content)
        if topic and dates:
            by_topic[topic].update(dates)
    return [{"topic": topic, "values": sorted(values)} for topic, values in by_topic.items() if len(values) > 1]
