"""Runtime configuration for the RAG API."""
from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = Path(os.getenv("RAG_DOCUMENTS_DIR", BASE_DIR / "documents"))
USER_DOCUMENTS_DIR = Path(os.getenv("RAG_USER_DOCUMENTS_DIR", BASE_DIR / "user_documents"))
CHROMA_DIR = Path(os.getenv("CHROMA_PERSIST_DIRECTORY", BASE_DIR / "chroma_db"))
KNOWLEDGE_GRAPH_DIR = Path(os.getenv("RAG_KNOWLEDGE_GRAPH_DIR", BASE_DIR / "knowledge_graph"))
WORKSPACES_DIR = Path(os.getenv("RAG_WORKSPACES_DIR", BASE_DIR / "workspaces"))
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "ai_chatbot_knowledge_base")
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "2000"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "500"))
TOP_K = int(os.getenv("RAG_TOP_K", "4"))
RETRIEVAL_CONFIDENCE_THRESHOLD = float(os.getenv("RAG_CONFIDENCE_THRESHOLD", "0.18"))
MAX_UPLOAD_BYTES = int(os.getenv("RAG_MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
MEMORY_MAX_ITEMS = int(os.getenv("RAG_MEMORY_MAX_ITEMS", "40"))
EMBEDDING_MODEL = os.getenv("FASTEMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
