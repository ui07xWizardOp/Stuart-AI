"""
Tests for Context Manager (Task 18 MVP)
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock

# Mock observability module

from core.context_manager import ContextManager
from memory.short_term import MemoryRole, MemoryEntry

def test_context_manager_trim_working_memory():
    # Force max tokens to 4 = around 16 chars bounds (remember overhead is subbed, so we mock math)
    cm = ContextManager(max_tokens=2010) # 2000 reserved, leaves 10 tokens = 40 chars
    
    e1 = MemoryEntry(MemoryRole.USER, "AAAABBBBCCCCDDDD") # 16 chars -> 4 tokens
    e2 = MemoryEntry(MemoryRole.AGENT, "EEEEFFFFGGGGHHHH") # 16 chars -> 4 tokens
    e3 = MemoryEntry(MemoryRole.OBSERVATION, "1234567890123456") # 16 chars -> 4 tokens
    
    # Total tokens = 12 tokens. Our limit is 10 tokens. It must drop the first one.
    res = cm.trim_working_memory([e1, e2, e3])
    
    assert len(res) == 2
    assert res[0].content == "EEEEFFFFGGGGHHHH" # e2 is now first
    
def test_context_manager_trim_semantic():
    cm = ContextManager()
    
    # Generate 100 character string (~25 tokens)
    blob = "A" * 100
    
    # Cap to exactly 10 tokens = ~40 chars
    trimmed = cm.trim_semantic_search_results(blob, max_allowed_tokens=10)
    
    assert "TRUNCATED" in trimmed
    # Output should basically be the first 40 chars plus the truncate warning
    assert trimmed.startswith("A" * 40)
