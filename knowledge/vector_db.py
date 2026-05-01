"""
Vector Database Backend (Task 17.3)

Provides semantic search wrappers around Qdrant local disk DB.
Allows us to ingest dense overlapping vectors and pull them back via Cosine Similarity.
"""

from typing import List, Dict, Any, Optional
import uuid
import os
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from observability import get_logging_system
from .vectorizer import TextChunk

class VectorDatabase:
    _clients: Dict[str, QdrantClient] = {}

    def __init__(self, collection_name: str = "obsidian_vault", storage_path: Optional[str] = None):
        self.logger = get_logging_system()
        self.collection_name = collection_name
        
        # Determine local DB path
        if not storage_path:
            base_dir = Path(__file__).parent.parent / "database" / "qdrant"
            base_dir.mkdir(parents=True, exist_ok=True)
            storage_path = str(base_dir)
            
        if storage_path not in self.__class__._clients:
            self.__class__._clients[storage_path] = QdrantClient(path=storage_path)
            self.logger.info(f"Qdrant Vector DB bound to {storage_path}")
            
        self.client = self.__class__._clients[storage_path]
        
        self._ensure_collection()

    def _ensure_collection(self):
        """Initializes the collection if it does not exist."""
        # text-embedding-3-small has 1536 dimensions, nomic-embed-text has 768
        # We will determine size based on OPENAI_API_KEY presence
        import os
        from knowledge.vectorizer import OpenAIConfig
        config = OpenAIConfig()
        has_openai = bool(config.openai_api_key or os.environ.get("OPENAI_API_KEY", ""))
        self.vector_size = 1536 if has_openai else 768
        
        collections = self.client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
            self.logger.info(f"Created new Qdrant collection: {self.collection_name} (Size: {self.vector_size})")

    def upsert_chunks(self, chunks: List[TextChunk]) -> None:
        """Pushes embedded vectors into Qdrant."""
        if not chunks:
            return
            
        points = []
        for chunk in chunks:
            if not chunk.vector:
                self.logger.warning(f"Skipping chunk {chunk.chunk_index} of {chunk.document_id} as it lacks a vector.")
                continue
                
            # Combine dicts securely
            payload = chunk.metadata.copy()
            payload["text"] = chunk.text
            payload["document_id"] = chunk.document_id
            payload["chunk_index"] = chunk.chunk_index
            
            # Predictable UUID based on doc ID and chunk index so re-ingesting overwrites them purely
            # Just use namespace UUID to prevent duplicating chunks inherently
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk.document_id}_{chunk.chunk_index}"))
            
            points.append(PointStruct(
                id=point_id,
                vector=chunk.vector,
                payload=payload
            ))
            
        # Push points to DB
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            self.logger.debug(f"Upserted {len(points)} vectors to Qdrant.")

    def semantic_search(self, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """Finds closest text chunks via cosine similarity to the query vector."""
        if not query_vector:
            return []
            
        search_result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit
        )
        
        results = []
        for hit in search_result.points:
            results.append({
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "document_id": hit.payload.get("document_id", ""),
                "metadata": hit.payload
            })
            
        return results

    def remove_document(self, document_id: str) -> None:
        """Deletes all chunks associated with a specific markdown file."""
        from qdrant_client.http import models
        
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id)
                    )
                ]
            )
        )
        self.logger.debug(f"Removed document {document_id} from vector store.")
