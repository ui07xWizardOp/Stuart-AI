"""
Tests for Vector Database Binding (Task 17.3)
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock

# Mock observability module

from knowledge.vector_db import VectorDatabase
from knowledge.vectorizer import TextChunk

@pytest.fixture
def mock_qdrant_db():
    # Use memory mode for fast isolated DB tests
    from observability import initialize_logging
    initialize_logging()
    return VectorDatabase(storage_path=":memory:")

def test_qdrant_upsert_and_search(mock_qdrant_db):
    # text-embedding-3-small uses 768 dims. We'll populate just a bit and pad the rest
    vec1 = [0.0] * 768
    vec1[0] = 1.0 # purely on axis 1
    
    vec2 = [0.0] * 768
    vec2[1] = 1.0 # purely on axis 2
    
    c1 = TextChunk("notes_1.md", "I love apples", 0, {"author": "Me"})
    c1.vector = vec1
    
    c2 = TextChunk("notes_2.md", "I love oranges", 0, {"author": "Me"})
    c2.vector = vec2
    
    mock_qdrant_db.upsert_chunks([c1, c2])
    
    # query right along axis 1
    query_vec = [0.0] * 768
    query_vec[0] = 0.9
    
    results = mock_qdrant_db.semantic_search(query_vec, limit=1)
    assert len(results) == 1
    
    assert len(results) == 1
    assert "apples" in results[0]["text"]
    assert results[0]["document_id"] == "notes_1.md"

def test_qdrant_document_removal(mock_qdrant_db):
    vec = [0.5] * 768
    c = TextChunk("del_me.md", "Delete this info", 0, {})
    c.vector = vec
    
    mock_qdrant_db.upsert_chunks([c])
    assert len(mock_qdrant_db.semantic_search(vec, 10)) > 0
    
    mock_qdrant_db.remove_document("del_me.md")
    results = mock_qdrant_db.semantic_search(vec, 10)
    assert not any(r["document_id"] == "del_me.md" for r in results)
