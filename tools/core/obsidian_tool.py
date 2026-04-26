"""
Obsidian Controller Tool (Task 17.4)

Provides explicit commands to the Agent Orchestrator to search the Vault
or directly write beautifully formatted new memories into the knowledge base.
"""

from typing import Dict, Any, Optional
import time
from pathlib import Path

from tools.base import BaseTool, CapabilityDescriptor, ToolRiskLevel, ToolResult
from knowledge.vector_db import VectorDatabase
from knowledge.vectorizer import Vectorizer


class ObsidianTool(BaseTool):
    
    name = "obsidian_manager"
    description = "Searches the human-readable Markdown Vault and writes structured knowledge notes."
    version = "1.0.0"
    category = "knowledge"
    risk_level = ToolRiskLevel.MEDIUM
    
    parameter_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Used for semantic_search."},
            "filename": {"type": "string", "description": "Target markdown filename to read or write (e.g. 'project_x.md')."},
            "content": {"type": "string", "description": "Markdown body content to write."},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "YAML Tags to insert in new notes."}
        }
    }
    
    capabilities = [
        CapabilityDescriptor("semantic_search", "Uses vector math to find conceptually relevant vault notes.", ["query"]),
        CapabilityDescriptor("read_note", "Reads the exact contents of an Obsidian markdown file.", ["filename"]),
        CapabilityDescriptor("write_note", "Creates a fully formatted Obsidian note with Frontmatter.", ["filename", "content"])
    ]

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.vault_path.mkdir(parents=True, exist_ok=True)
        
        self.vectorizer = Vectorizer()
        self.db = VectorDatabase()

    def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> ToolResult:
        if action == "semantic_search":
            query = parameters.get("query")
            if not query:
                return ToolResult(success=False, error="semantic_search requires a 'query' parameter.", output=None)
                
            try:
                # 1. Convert search phrase to vector
                # We use a dummy document wrapper just to call the calculate_embeddings mutator safely
                from knowledge.vectorizer import TextChunk
                dummy = [TextChunk("query", query, 0, {})]
                self.vectorizer.calculate_embeddings(dummy)
                
                query_vec = dummy[0].vector
                
                # 2. Score against local DB
                hits = self.db.semantic_search(query_vec, limit=5)
                
                # 3. Format response elegantly for LLM
                output_str = f"Found {len(hits)} semantic matches:\n"
                for i, hit in enumerate(hits):
                    score = round(hit['score'], 3)
                    output_str += f"\n--- Match {i+1} (Score: {score}) in {hit['document_id']} ---\n"
                    output_str += f"{hit['text']}\n"
                    
                return ToolResult(success=True, output=output_str)
                
            except Exception as e:
                return ToolResult(success=False, error=f"Vector search failed: {str(e)}", output=None)

        elif action == "read_note":
            filename = parameters.get("filename")
            if not filename:
                return ToolResult(success=False, error="read_note requires 'filename'", output=None)
                
            filepath = self.vault_path / filename.lstrip("/")
            if not filepath.exists():
                return ToolResult(success=False, error="File does not exist.", output=None)
                
            return ToolResult(success=True, output=filepath.read_text(encoding='utf-8'))

        elif action == "write_note":
            filename = parameters.get("filename")
            content = parameters.get("content")
            tags = parameters.get("tags", [])
            
            if not filename or not content:
                return ToolResult(success=False, error="write_note requires 'filename' and 'content'.", output=None)
                
            if not filename.endswith(".md"):
                filename += ".md"
                
            filepath = self.vault_path / filename.lstrip("/")
            
            # Format YAML Frontmatter
            from datetime import datetime
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            yaml_header = "---\n"
            yaml_header += "author: Stuart-AI\n"
            yaml_header += f"created: {now}\n"
            if tags:
                yaml_header += f"tags: [{', '.join(tags)}]\n"
            yaml_header += "---\n\n"
            
            full_content = yaml_header + content
            
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(full_content, encoding='utf-8')
            
            return ToolResult(success=True, output=f"Successfully built note at {filename}")

        return ToolResult(success=False, error=f"Unknown capability action: {action}", output=None)
