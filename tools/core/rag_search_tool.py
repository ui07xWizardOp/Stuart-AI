"""
RAG Search Tool (Phase 10)

Provides explicit commands to the Agent Orchestrator to search the personal
document index (Vector DB) or read full matched documents.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from tools.base import BaseTool, CapabilityDescriptor, ToolRiskLevel, ToolResult
from observability import get_logging_system


class RagSearchTool(BaseTool):
    """
    Semantic search over the personal document index (Qdrant Vector DB).
    """
    
    name = "rag_search"
    description = "Searches the user's indexed local personal documents (PDFs, Markdown, text files) using vector similarity."
    version = "1.0.0"
    category = "knowledge"
    risk_level = ToolRiskLevel.LOW
    
    parameter_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The question or topic to search for in user documents."},
            "document_id": {"type": "string", "description": "Used ONLY with read_document to fetch full text. Typically a file path."}
        }
    }
    
    capabilities = [
        CapabilityDescriptor("search_my_documents", "Searches the local indexed knowledge base via semantic vector similarity.", ["query"]),
        CapabilityDescriptor("read_document", "Reads the complete raw text of an indexed document given its exact document_id.", ["document_id"])
    ]

    def __init__(self):
        self.logger = get_logging_system()
        # Initialize lazily to prevent blocking startup if DB is down or missing
        self._db = None
        self._vectorizer = None

    @property
    def db(self):
        if not self._db:
            from knowledge.vector_db import VectorDatabase
            self._db = VectorDatabase()
        return self._db

    @property
    def vectorizer(self):
        if not self._vectorizer:
            from knowledge.vectorizer import Vectorizer
            self._vectorizer = Vectorizer()
        return self._vectorizer

    def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> ToolResult:
        if action == "search_my_documents":
            query = parameters.get("query")
            if not query:
                return ToolResult(success=False, error="search_my_documents requires a 'query' parameter.", output=None)
                
            try:
                # 1. Embed query
                from knowledge.vectorizer import TextChunk
                dummy = [TextChunk("query", query, 0, {})]
                self.vectorizer.calculate_embeddings(dummy)
                query_vec = dummy[0].vector
                
                if not query_vec:
                    return ToolResult(success=False, error="Embedding failed. Check API key.", output=None)
                
                # 2. Search DB
                hits = self.db.semantic_search(query_vec, limit=5)
                
                if not hits:
                    return ToolResult(success=True, output="No relevant documents found in the personal index.")
                
                # 3. Format output
                output_str = f"Found {len(hits)} semantic matches in your documents:\n"
                for i, hit in enumerate(hits):
                    score = round(hit['score'], 3)
                    doc_id = hit.get('document_id', 'Unknown')
                    metadata = hit.get('metadata', {})
                    filename = metadata.get('filename', doc_id)
                    
                    output_str += f"\n--- Match {i+1} (Score: {score}) | Source: {filename} (ID: `{doc_id}`) ---\n"
                    output_str += f"{hit['text']}\n"
                    
                output_str += "\n\nTip: You can use `read_document` with the document_id to read the full file."
                return ToolResult(success=True, output=output_str)
                
            except Exception as e:
                self.logger.error(f"RAG search failed: {e}")
                return ToolResult(success=False, error=f"Vector search failed: {str(e)}", output=None)

        elif action == "read_document":
            document_id = parameters.get("document_id")
            if not document_id:
                return ToolResult(success=False, error="read_document requires 'document_id'", output=None)
                
            filepath = Path(document_id)
            if not filepath.exists():
                return ToolResult(success=False, error=f"File does not exist: {document_id}", output=None)
                
            try:
                # Extract text based on file type
                ext = filepath.suffix.lower()
                text = ""
                if ext in {'.txt', '.md', '.json', '.csv'}:
                    text = filepath.read_text(encoding='utf-8', errors='ignore')
                elif ext == '.pdf':
                    import fitz
                    text_parts = []
                    with fitz.open(filepath) as doc:
                        for page in doc:
                            text_parts.append(page.get_text("text"))
                    text = "\n".join(text_parts)
                else:
                    return ToolResult(success=False, error=f"Unsupported file type to read directly: {ext}")
                
                # Truncate if insanely large (e.g., > 10,000 words)
                words = text.split()
                if len(words) > 5000:
                    text = " ".join(words[:5000]) + "\n\n... [TRUNCATED DUE TO LENGTH] ..."
                    
                return ToolResult(success=True, output=f"DOCUMENT: {filepath.name}\n\n{text}")
                
            except Exception as e:
                self.logger.error(f"Read document failed: {e}")
                return ToolResult(success=False, error=f"Failed to read file: {e}")

        return ToolResult(success=False, error=f"Unknown capability action: {action}", output=None)
