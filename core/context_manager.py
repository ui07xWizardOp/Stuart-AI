"""
Context Manager (Task 18 MVP)

Responsbible for token-budget enforcement. It trims and deduplicates semantic arrays
and dialogue windows to ensure we do not hit HTTP 400 limitations on the LLM API.
"""

from typing import List, Dict, Any, Tuple
import math

from observability import get_logging_system
from memory.short_term import MemoryEntry

class ContextManager:
    def __init__(self, max_tokens: int = 16000):
        self.logger = get_logging_system()
        # Reserve buffer space for system prompts and tool schemas.
        self.max_tokens = max_tokens
        self.reserved_overhead = 2000 
        self.available_tokens = self.max_tokens - self.reserved_overhead
    
    def _approximate_tokens(self, text: str) -> int:
        """
        Crude fallback token approximation logic (roughly 4 chars per token).
        In production, a proper tokenizer like tiktoken is required.
        """
        return math.ceil(len(text) / 4.0)

    def trim_working_memory(self, entries: List[MemoryEntry]) -> List[MemoryEntry]:
        """
        Takes a chronological array of memory entries (oldest to newest)
        and crops from the beginning (oldest) until it fits the token budget.
        """
        current_tokens = sum(self._approximate_tokens(e.content) for e in entries)
        
        trimmed_entries = entries.copy()
        
        while current_tokens > self.available_tokens and len(trimmed_entries) > 1:
            # Pop the oldest entry
            removed = trimmed_entries.pop(0)
            removed_tokens = self._approximate_tokens(removed.content)
            current_tokens -= removed_tokens
            self.logger.warning(f"ContextManager: Popped oldest entry '{removed.role.value}' to save {removed_tokens} tokens.")
            
        return trimmed_entries
        
    def trim_semantic_search_results(self, text_blob: str, max_allowed_tokens: int = 2000) -> str:
        """
        Strictly truncates massive RAG blobs (from Obsidian) to a fixed token geometry
        so it doesn't crush the immediate reasoning step limits.
        """
        tokens = self._approximate_tokens(text_blob)
        if tokens <= max_allowed_tokens:
            return text_blob
            
        self.logger.warning(f"ContextManager: Trimming RAG blob from {tokens} down to {max_allowed_tokens} tokens.")
        
        # Invert the character logic (1 token ~= 4 chars)
        cutoff_length = max_allowed_tokens * 4
        return text_blob[:cutoff_length] + "\n...[TRUNCATED BY CONTEXT MANAGER]..."
