"""
Short-Term Memory System (Task 16.1)

Provides a First-In-First-Out (FIFO) sliding window context buffer
to maintain operational awareness without exceeding LLM context windows.
"""

import time
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from observability import get_logging_system


class MemoryRole(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    OBSERVATION = "observation"
    THOUGHT = "thought"


@dataclass
class MemoryEntry:
    """A discrete unit of information within the short-term window."""
    role: MemoryRole
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        return cls(
            role=MemoryRole(data["role"]),
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {})
        )


class ShortTermMemory:
    """
    Sliding window session memory. Evicts oldest entries once capacity is exceeded.
    """

    def __init__(self, capacity: int = 20):
        self.logger = get_logging_system()
        self.capacity = capacity
        self._buffer: List[MemoryEntry] = []
        self.logger.info(f"Short term memory initialized with capacity {capacity}")

    def add_entry(self, role: MemoryRole, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Appends a new interaction to the active conversation sliding window."""
        entry = MemoryEntry(role=role, content=content, metadata=metadata or {})
        self._buffer.append(entry)
        
        # Enforce FIFO bound
        if len(self._buffer) > self.capacity:
            evicted = self._buffer.pop(0)
            self.logger.debug(f"Short-Term Memory capacity maxed. Evicted oldest entry: {evicted.role.value}")

    def get_context_window(self, max_entries: Optional[int] = None) -> List[MemoryEntry]:
        """
        Retrieves the active context, potentially capped at `max_entries`.
        Entries are returned in chronological order (oldest -> newest).
        """
        if max_entries is not None and max_entries > 0:
            return self._buffer[-max_entries:]
        return self._buffer.copy()

    def format_as_prompt_context(self) -> str:
        """Converts the buffer directly into a fast text blob for LLMs."""
        lines = []
        for entry in self._buffer:
            role_header = entry.role.value.upper()
            lines.append(f"<{role_header}>\n{entry.content}\n</{role_header}>")
        return "\n\n".join(lines)

    def clear(self) -> None:
        """Flushes the working memory."""
        self._buffer.clear()
        self.logger.info("Short term memory explicitly flushed.")

    def export_state(self) -> List[Dict[str, Any]]:
        """Serializes current state for persisting session dumps."""
        return [entry.to_dict() for entry in self._buffer]

    def load_state(self, state_list: List[Dict[str, Any]]) -> None:
        """Restores memory from a session dump."""
        self._buffer = [MemoryEntry.from_dict(d) for d in state_list]
        
        # Prevent oversized loads
        if len(self._buffer) > self.capacity:
            self.logger.warning("Loaded state exceeded current capacity constraints. Trimming.")
            self._buffer = self._buffer[-self.capacity:]
