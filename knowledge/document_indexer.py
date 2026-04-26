"""
Phase 10: RAG & Second Brain
Document Ingestion Pipeline

Parses local files (.md, .txt, .csv, .json, .pdf) into text,
chunks them, embeds them, and stores them in Qdrant.
"""

import os
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Generator

from observability import get_logging_system
from knowledge.vectorizer import Vectorizer, TextChunk
from knowledge.vector_db import VectorDatabase


class DocumentIndexer:
    """
    Crawls a directory, parses files, embeds chunks, and saves to the vector DB.
    """
    
    SUPPORTED_EXTENSIONS = {'.txt', '.md', '.csv', '.json', '.pdf'}
    IGNORE_DIRS = {'.git', '.obsidian', 'node_modules', 'venv', '__pycache__', '.venv'}
    
    def __init__(self):
        self.logger = get_logging_system()
        self.vectorizer = Vectorizer()
        self.db = VectorDatabase()
        
    def index_directory(self, root_path: str) -> Dict[str, Any]:
        """
        Indexes all supported files in a directory recursively.
        Returns a summary dictionary of what was indexed.
        """
        path = Path(root_path).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Directory not found: {path}")
            
        self.logger.info(f"Starting document indexing for directory: {path}")
        
        stats = {
            "files_processed": 0,
            "files_skipped": 0,
            "chunks_created": 0,
            "errors": 0
        }
        
        for file_path in self._walk_directory(path):
            try:
                self.logger.debug(f"Processing file: {file_path}")
                text = self._extract_text(file_path)
                
                if not text.strip():
                    self.logger.info(f"Empty text parsed from {file_path}, skipping.")
                    stats["files_skipped"] += 1
                    continue
                
                # Delete existing chunks for this document to avoid duplicates
                doc_id = str(file_path)
                self.db.remove_document(doc_id)
                
                # Chunk the text
                metadata = {"filename": file_path.name, "extension": file_path.suffix}
                chunks = self.vectorizer.process_document(doc_id, text, metadata)
                
                if not chunks:
                    stats["files_skipped"] += 1
                    continue
                    
                # Calculate embeddings (Note: This mutates chunks in-place)
                self.vectorizer.calculate_embeddings(chunks)
                
                # Filter out chunks that failed to get an embedding
                valid_chunks = [c for c in chunks if c.vector]
                
                if valid_chunks:
                    self.db.upsert_chunks(valid_chunks)
                    stats["files_processed"] += 1
                    stats["chunks_created"] += len(valid_chunks)
                else:
                    self.logger.warning(f"No valid embeddings returned for {file_path}.")
                    stats["errors"] += 1
                    
            except Exception as e:
                self.logger.error(f"Failed to process file {file_path}: {e}")
                stats["errors"] += 1
                
        self.logger.info(f"Indexing complete. Stats: {stats}")
        return stats
        
    def _walk_directory(self, root_path: Path) -> Generator[Path, None, None]:
        """Yields file paths safely, ignoring specified directories."""
        for root, dirs, files in os.walk(root_path):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS and not d.startswith('.')]
            
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    yield file_path

    def _extract_text(self, file_path: Path) -> str:
        """
        Extracts raw text based on file extension.
        """
        ext = file_path.suffix.lower()
        
        if ext in {'.txt', '.md'}:
            return file_path.read_text(encoding='utf-8', errors='ignore')
            
        elif ext == '.json':
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                return json.dumps(data, indent=2)
            except Exception:
                # Fallback to raw parsing
                return file_path.read_text(encoding='utf-8', errors='ignore')
                
        elif ext == '.csv':
            text = []
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    text.append(" | ".join(row))
            return "\n".join(text)
            
        elif ext == '.pdf':
            return self._extract_pdf(file_path)
            
        return ""

    def _extract_pdf(self, file_path: Path) -> str:
        """Extracts text from PDF using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
            text = []
            with fitz.open(file_path) as doc:
                for page in doc:
                    text.append(page.get_text("text"))
            return "\n".join(text)
        except ImportError:
            self.logger.warning("PyMuPDF (fitz) is not installed. PDF indexing skipped.")
            return f"[PDF Parsing Failed - Missing PyMuPDF]: {file_path.name}"
        except Exception as e:
            self.logger.error(f"Error parsing PDF {file_path}: {e}")
            return f"[PDF Parse Error]: {e}"
