"""
Tests for Cognitive Maintenance (Task 23)
"""
import sys
import pytest
from unittest.mock import Mock, MagicMock

# Mock observability module
mock_logger = MagicMock()
sys.modules['observability'] = MagicMock()
sys.modules['observability'].get_logging_system = Mock(return_value=mock_logger)

from cognitive.maintenance import CognitiveMaintenanceEngine

def test_distillation_no_records():
    mock_mem = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [] # No records
    mock_mem.long_term.conn.cursor.return_value = mock_cursor
    
    mock_router = MagicMock()
    
    engine = CognitiveMaintenanceEngine(mock_mem, mock_router)
    res = engine.run_distillation()
    
    assert "skipped" in res
    assert not mock_router.execute_with_failover.called

def test_distillation_with_records():
    mock_mem = MagicMock()
    mock_cursor = MagicMock()
    # Mocking rows returned from SQLite. 
    # Tuple format: (id, context_key, extracted_facts)
    mock_cursor.fetchall.return_value = [
        (1, "context_a", "I like apples"),
        (2, "context_b", "I hate oranges")
    ]
    mock_mem.long_term.conn.cursor.return_value = mock_cursor
    
    mock_router = MagicMock()
    mock_router.execute_with_failover.return_value = "User likes apples but not oranges."
    
    engine = CognitiveMaintenanceEngine(mock_mem, mock_router)
    res = engine.run_distillation()
    
    assert "processed" in res.lower()
    
    # Ensures LLM was asked to summarize
    assert mock_router.execute_with_failover.called
    
    # Ensures it saved the result back to memory
    mock_mem.remember_fact.assert_called_once()
    
    # Ensures DELETE FROM was executed
    assert mock_cursor.execute.call_count == 2 # 1 for SELECT, 1 for DELETE
