"""
Tests for Plan Library (Task 24)
"""
import sys
import pytest
import json
from unittest.mock import Mock, MagicMock

# Mock observability
mock_logger = MagicMock()
sys.modules['observability'] = MagicMock()
sys.modules['observability'].get_logging_system = Mock(return_value=mock_logger)

from cognitive.plan_library import PlanLibrary

def test_plan_lib_record_and_lookup():
    mock_mem = MagicMock()
    
    # Setup mock so extract_context returns the mocked fact
    def fake_extract(cat, exact_key):
        if exact_key == "plan_f88e6dd178dc926fc3aae63db9820f1f": # hash of "do math"
            return [{"sequence": json.dumps([{"tool": "python", "action": "run"}])}]
        return []
        
    mock_mem.extract_context.side_effect = fake_extract
    
    pl = PlanLibrary(mock_mem)
    
    # Record
    pl.record_successful_plan("Do Math", [{"tool": "python", "action": "run"}])
    mock_mem.remember_fact.assert_called_once()
    
    # Lookup
    res = pl.lookup_plan(" do math ") # testing whitespace cleaning in hash
    
    assert res is not None
    assert "proven plan" in res
    assert "1. python.run" in res

def test_plan_lib_empty():
    mock_mem = MagicMock()
    mock_mem.extract_context.return_value = []
    
    pl = PlanLibrary(mock_mem)
    res = pl.lookup_plan("New problem")
    assert res is None
