"""
Core Memory System Controller (Task 16.3)

Provides a unified interface combining both Short-Term sliding windows
and Long-Term SQLite databases, acting as the Single Point of Truth for the Orchestrator.
"""

from typing import Dict, Any, List, Optional
from observability import get_logging_system

from .short_term import ShortTermMemory, MemoryRole, MemoryEntry
from .long_term import LongTermMemory


class MemorySystem:
    """
    Master controller for all agent memory.
    Coordinates between short-term conversational context and long-term fact storage.
    """

    def __init__(self, stm_capacity: int = 20, ltm_db_path: Optional[str] = None):
        self.logger = get_logging_system()
        self.short_term = ShortTermMemory(capacity=stm_capacity)
        self.long_term = LongTermMemory(db_path=ltm_db_path)
        self.logger.info("Master Memory System initialized.")

    # --- Short-Term API Routines ---

    def commit_interaction(self, role: MemoryRole, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Saves a conversational turn or thought to the short-term working buffer."""
        self.short_term.add_entry(role, content, metadata)

    def extract_context(self) -> str:
        """Returns the fully formatted text block for LLM prompt ingestion."""
        return self.short_term.format_as_prompt_context()
        
    def get_recent_entries(self, count: int = 5) -> List[MemoryEntry]:
        """Provides the last N distinct observations/thoughts for logic routing."""
        return self.short_term.get_context_window(max_entries=count)

    def wipe_session(self) -> None:
        """Clears the short term cache entirely."""
        self.short_term.clear()

    # --- Long-Term API Routines ---

    def remember_fact(self, category: str, key: str, value: Any) -> None:
        """Explicitly stores logic into persistent storage."""
        self.long_term.store_fact(category, key, value)

    def recall_fact(self, category: str, key: str) -> Optional[Any]:
        """Retrieves an explicit value from persistent storage."""
        return self.long_term.retrieve_fact(category, key)
        
    def recall_category(self, category: str) -> Dict[str, Any]:
        """Loads an entire category dict (e.g. settings) into memory."""
        return self.long_term.retrieve_category(category)

    def search_memory(self, query: str) -> List[Dict[str, Any]]:
        """
        Executes a baseline text search over SQLite.
        Note: True Semantic vectoring is slated for Task 17 integration.
        """
        return self.long_term.search_facts(query)

    def forget_fact(self, category: str, key: str) -> bool:
        """Deletes a fact from persistent storage."""
        return self.long_term.delete_fact(category, key)
