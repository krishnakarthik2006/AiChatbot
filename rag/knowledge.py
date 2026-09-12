"""Small local knowledge graph extracted from indexed chunks."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from . import config

ENTITY_PATTERN = re.compile(r"\b(?:[A-Z][A-Za-z0-9-]+(?:\s+[A-Z][A-Za-z0-9-]+){0,2}|\d{4}-\d{2}-\d{2})\b")


def _path(namespace: str) -> Path:
    config.KNOWLEDGE_GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", namespace)
    return config.KNOWLEDGE_GRAPH_DIR / f"{safe}.json"


def build_graph(namespace: str, chunks: list[dict]) -> dict:
    nodes, edges = Counter(), Counter()
    for chunk in chunks:
        entities = list(dict.fromkeys(ENTITY_PATTERN.findall(chunk.get("content", ""))))[:12]
        for entity in entities:
            nodes[entity] += 1
        for index, left in enumerate(entities):
            for right in entities[index + 1:]:
                edges[tuple(sorted((left, right)))] += 1
    graph = {
        "nodes": [{"id": name, "mentions": count} for name, count in nodes.most_common(80)],
        "edges": [{"source": left, "target": right, "weight": weight} for (left, right), weight in edges.most_common(160)],
    }
    _path(namespace).write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    return graph


def get_graph(namespace: str) -> dict:
    try:
        return json.loads(_path(namespace).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"nodes": [], "edges": []}
