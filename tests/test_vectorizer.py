"""
Tests for Vectorizer Pipeline (Task 17.2)
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock, patch

# Mock observability module
mock_logger = MagicMock()
sys.modules['observability'] = MagicMock()
sys.modules['observability'].get_logging_system = Mock(return_value=mock_logger)

from vectorizer import Vectorizer, TextChunk

def test_vectorizer_chunking():
    # Force tiny chunks for test (5 words, overlap 2)
    vec = Vectorizer(chunk_size=5, chunk_overlap=2)
    # 8 words total
    text = "The quick brown fox jumps over the lazy dog."
    
    chunks = vec.process_document("doc1", text, {"author": "Alice"})
    
    # 1. "The quick brown fox jumps" (5)
    # 2. "fox jumps over the lazy" (5) (overlap 2: fox jumps)
    # 3. "the lazy dog." (3) (overlap 2: the lazy)
    assert len(chunks) == 3
    assert chunks[0].text == "The quick brown fox jumps"
    assert chunks[1].text == "fox jumps over the lazy"
    assert chunks[2].text == "the lazy dog."
    
    assert chunks[0].document_id == "doc1"
    assert chunks[0].metadata["author"] == "Alice"

@patch('vectorizer.openai.Client')
def test_vectorizer_embeddings(mock_openai_client):
    # Setup mock response
    mock_instance = MagicMock()
    mock_response = MagicMock()
    mock_data_obj = MagicMock()
    mock_data_obj.embedding = [0.1, 0.2, 0.3]
    mock_response.data = [mock_data_obj]
    
    mock_instance.embeddings.create.return_value = mock_response
    mock_openai_client.return_value = mock_instance
    
    vec = Vectorizer(chunk_size=10, chunk_overlap=0)
    vec.api_key = "test_key"
    vec.client = mock_instance
    
    chunks = [TextChunk("doc1", "Hello World", 0, {})]
    
    # Process
    vec.calculate_embeddings(chunks)
    
    # Verify mutations
    assert chunks[0].vector == [0.1, 0.2, 0.3]
    mock_instance.embeddings.create.assert_called_once()
