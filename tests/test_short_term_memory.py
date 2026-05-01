"""
Tests for Short Term Memory System (Task 16.1)
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock

# Mock observability module

from memory.short_term import ShortTermMemory, MemoryRole

def test_short_term_fifo_eviction():
    mem = ShortTermMemory(capacity=3)
    
    mem.add_entry(MemoryRole.USER, "1")
    mem.add_entry(MemoryRole.AGENT, "2")
    mem.add_entry(MemoryRole.OBSERVATION, "3")
    
    assert len(mem._buffer) == 3
    assert mem._buffer[0].content == "1"
    
    # Exceed capacity
    mem.add_entry(MemoryRole.THOUGHT, "4")
    
    assert len(mem._buffer) == 3
    # 1 should be gone
    assert mem._buffer[0].content == "2"
    assert mem._buffer[-1].content == "4"

def test_short_term_context_formatting():
    mem = ShortTermMemory(capacity=20)
    
    mem.add_entry(MemoryRole.USER, "What time is it?")
    mem.add_entry(MemoryRole.AGENT, "It is noon.")
    
    text = mem.format_as_prompt_context()
    
    assert "<USER>" in text
    assert "What time is it?" in text
    assert "</USER>" in text
    
    assert "<AGENT>" in text
    assert "It is noon." in text
    
def test_short_term_state_serialization():
    mem = ShortTermMemory(capacity=5)
    mem.add_entry(MemoryRole.SYSTEM, "Booting up", {"os": "windows"})
    
    state = mem.export_state()
    assert isinstance(state, list)
    assert state[0]["role"] == "system"
    assert state[0]["content"] == "Booting up"
    assert state[0]["metadata"]["os"] == "windows"
    
    # Restore into fresh memory
    mem2 = ShortTermMemory(capacity=5)
    mem2.load_state(state)
    
    assert len(mem2._buffer) == 1
    assert mem2._buffer[0].content == "Booting up"
