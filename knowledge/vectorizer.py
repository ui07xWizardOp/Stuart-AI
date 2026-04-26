"""
Chunking & Embedding Pipeline (Task 17.2)

Converts strings into lists of overlapping text chunks and passes
them to OpenAI's native API to calculate High-Dimensional Dense Vectors.
"""

from typing import List, Dict, Any, Tuple
import os
import openai
from pydantic_settings import BaseSettings

from observability import get_logging_system


class TextChunk:
    def __init__(self, document_id: str, text: str, chunk_index: int, metadata: Dict[str, Any]):
        self.document_id = document_id
        self.text = text
        self.chunk_index = chunk_index
        self.metadata = metadata
        self.vector: List[float] = []

class OpenAIConfig(BaseSettings):
    openai_api_key: str = ""
    
    class Config:
        env_file = ".env"
        extra = "ignore"


class Vectorizer:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.logger = get_logging_system()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Determine API Key from environment or defaults
        config = OpenAIConfig()
        self.api_key = config.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            self.logger.warning("No OpenAI API key found. Defaulting to local Ollama embeddings.")
            
        self.client = openai.Client(api_key=self.api_key) if self.api_key else None
        
        # Local Ollama fallback settings
        self.ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_embed_model = "nomic-embed-text"

    def _split_text(self, text: str) -> List[str]:
        """
        Splits text into chunks by raw word count. 
        In production, a proper tokenizer (tiktoken) is preferred, but splitting by words is faster.
        """
        words = text.split()
        chunks = []
        
        i = 0
        while i < len(words):
            chunk_words = words[i:i + self.chunk_size]
            chunks.append(" ".join(chunk_words))
            i += (self.chunk_size - self.chunk_overlap)
            
        return chunks

    def process_document(self, document_id: str, text: str, metadata: Dict[str, Any] = None) -> List[TextChunk]:
        """Chunks a document strictly into objects."""
        if metadata is None:
            metadata = {}
            
        raw_chunks = self._split_text(text)
        result_chunks = []
        
        for idx, chunk_text in enumerate(raw_chunks):
            result_chunks.append(TextChunk(
                document_id=document_id,
                text=chunk_text,
                chunk_index=idx,
                metadata=metadata.copy()
            ))
            
        return result_chunks

    def calculate_embeddings(self, chunks: List[TextChunk], model: str = "text-embedding-3-small") -> None:
        """
        Mutates the passed chunks by injecting the fetched OpenAI vectors into their `.vector` properties.
        Processes in batches to avoid API limits.
        """
        if not chunks:
            return
            
        if not self.api_key:
            # Local Ollama Fallback
            import requests
            for chunk in chunks:
                try:
                    payload = {
                        "model": self.ollama_embed_model,
                        "prompt": chunk.text
                    }
                    res = requests.post(f"{self.ollama_host}/api/embeddings", json=payload, timeout=30)
                    res.raise_for_status()
                    chunk.vector = res.json().get("embedding", [])
                except Exception as e:
                    self.logger.error(f"Ollama local embedding failed: {e}")
            return
            
        # Extract text list
        texts = [c.text for c in chunks]
        
        # Batch max limit for OpenAI embeddings is 2048, we'll do 500 to be safe
        batch_size = 500
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            
            try:
                response = self.client.embeddings.create(
                    input=batch_texts,
                    model=model
                )
                
                for j, data_obj in enumerate(response.data):
                    # Align response batch index to overall chunk array index
                    chunks[i + j].vector = data_obj.embedding
                    
            except Exception as e:
                self.logger.error(f"Failed to fetch embeddings batch: {e}")
                raise
