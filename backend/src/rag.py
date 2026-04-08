"""
SQLite-backed RAG module for medical guidelines.
Replaces the Supabase-dependent version with a local SQLite + numpy cosine similarity approach.
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Database path
DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "guidelines.db"

# Lazy-loaded embedding model
_embeddings_model = None


def _get_embeddings_model():
    """Lazy-load the HuggingFace embeddings model."""
    global _embeddings_model
    if _embeddings_model is None:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            logger.info("Loading AI Embedding model (first time may take a few seconds)...")
            _embeddings_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("langchain_huggingface not installed — RAG disabled")
            return None
        except Exception as e:
            logger.warning("Failed to load embedding model: %s", str(e))
            return None
    return _embeddings_model


def _init_db():
    """Create the SQLite table if it doesn't exist."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS medical_guidelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            metadata TEXT,
            embedding TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _cosine_similarity(vec_a: list, vec_b: list) -> float:
    """Compute cosine similarity between two vectors without numpy."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def ingest_guidelines(text_chunks: List[str], source_name: str):
    """Ingest medical guideline text chunks into SQLite with embeddings."""
    model = _get_embeddings_model()
    if model is None:
        logger.warning("Cannot ingest guidelines — embedding model not available")
        return

    _init_db()
    logger.info("Ingesting %d medical guidelines into SQLite...", len(text_chunks))
    
    embeddings = model.embed_documents(text_chunks)
    
    conn = sqlite3.connect(str(DB_PATH))
    for i, (chunk, embedding) in enumerate(zip(text_chunks, embeddings)):
        metadata = json.dumps({"source": source_name, "chunk_index": i})
        conn.execute(
            "INSERT INTO medical_guidelines (content, metadata, embedding) VALUES (?, ?, ?)",
            (chunk, metadata, json.dumps(embedding))
        )
    conn.commit()
    conn.close()
    logger.info("SUCCESS: Ingestion complete — %d chunks stored in SQLite.", len(text_chunks))


def retrieve_guidelines(query_text: str, top_k: int = 3) -> List[str]:
    """Retrieve the most relevant guideline chunks for a query using cosine similarity."""
    model = _get_embeddings_model()
    if model is None:
        logger.warning("Cannot retrieve guidelines — embedding model not available")
        return []

    if not DB_PATH.exists():
        logger.warning("No guidelines database found at %s", DB_PATH)
        return []
    
    logger.info("Searching AI Librarian for: '%s'", query_text)
    query_vector = model.embed_query(query_text)
    
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute("SELECT content, embedding FROM medical_guidelines").fetchall()
    conn.close()
    
    if not rows:
        logger.info("No guidelines stored in database.")
        return []
    
    # Compute similarities
    scored = []
    for content, embedding_json in rows:
        stored_embedding = json.loads(embedding_json)
        similarity = _cosine_similarity(query_vector, stored_embedding)
        if similarity > 0.1:  # minimum relevance threshold
            scored.append((similarity, content))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    results = scored[:top_k]
    
    for idx, (score, content) in enumerate(results):
        logger.info("--- Rule Found (Match Score: %d%%) ---", round(score * 100))
    
    return [content for _, content in results]


def search_medical_guidelines(query_text: str) -> List[str]:
    """Tool-ready retrieval function for the Chief Agent."""
    return retrieve_guidelines(query_text=query_text, top_k=3)


def ingest_file(file_path: str):
    """Load a document file and ingest its chunks into the SQLite vector store."""
    try:
        from langchain_community.document_loaders import PyPDFLoader, TextLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        logger.warning("langchain document loaders not installed — cannot ingest file")
        return

    logger.info("Loading document: %s", file_path)
    
    if file_path.endswith('.pdf'):
        loader = PyPDFLoader(file_path)
    elif file_path.endswith('.txt'):
        loader = TextLoader(file_path)
    else:
        logger.warning("Unsupported file type. Please use .pdf or .txt")
        return
        
    documents = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, 
        chunk_overlap=50
    )
    chunks = text_splitter.split_documents(documents)
    logger.info("Document split into %d chunks.", len(chunks))
    
    text_chunks = [chunk.page_content for chunk in chunks]
    source_name = os.path.basename(file_path)
    
    ingest_guidelines(text_chunks, source_name)


if __name__ == "__main__":
    test_file_path = str(Path(__file__).resolve().parent.parent / "data" / "guidelines.txt")
    ingest_file(test_file_path)
