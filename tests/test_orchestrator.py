"""
Tests for Core Orchestrator (Task 20 MVP)
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock, patch

# Mock observability module
mock_logger = MagicMock()
sys.modules['observability'] = MagicMock()
sys.modules['observability'].get_logging_system = Mock(return_value=mock_logger)

from orchestrator import Orchestrator
from memory.short_term import MemoryRole

def test_orchestrator_final_answer_breakout():
    # Setup mocks
    mock_bus = MagicMock()
    mock_memory = MagicMock()
    mock_memory.short_term.get_context_window.return_value = []
    
    mock_router = MagicMock()
    mock_router.execute_with_failover.return_value = "THOUGHT: I know this.\nFINAL_ANSWER: It is 42."
    
    mock_pm = MagicMock()
    mock_pm.render_prompt.return_value = "System text"
    
    mock_exec = MagicMock()
    mock_context = MagicMock()
    mock_context.trim_working_memory.return_value = []
    
    orch = Orchestrator(mock_bus, mock_memory, mock_router, mock_pm, mock_exec, mock_context)
    
    res = orch.process_user_message("What is the meaning of life?")
    
    assert res == "It is 42."
    # Make sure commit interaction was called at least for USER and THOUGHT and AGENT
    assert mock_memory.commit_interaction.called

def test_orchestrator_max_steps_circuit_breaker():
    mock_bus = MagicMock()
    mock_memory = MagicMock()
    mock_memory.short_term.get_context_window.return_value = []
    
    mock_router = MagicMock()
    # It just talks randomly without outputting the exit tokens
    mock_router.execute_with_failover.return_value = "I am thinking about it..."
    
    mock_pm = MagicMock()
    mock_pm.render_prompt.return_value = "System text"
    
    mock_exec = MagicMock()
    mock_context = MagicMock()
    mock_context.trim_working_memory.return_value = []
    
    orch = Orchestrator(mock_bus, mock_memory, mock_router, mock_pm, mock_exec, mock_context, max_reasoning_steps=2)
    
    res = orch.process_user_message("Do a loop.")
    
    assert "exhausted the max reasoning budget" in res
    assert mock_router.execute_with_failover.call_count == 2
