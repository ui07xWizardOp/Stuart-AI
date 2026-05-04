"""
Tests for Task Queue
"""
import sys
import pytest
from unittest.mock import Mock, MagicMock
import time

# Mock observability module

from automation.task_queue import TaskQueue

def test_task_queue_execution():
    mock_orchestrator = MagicMock()
    mock_orchestrator.process_user_message.return_value = "Done"
    
    # Factory just returns the mocked class
    tq = TaskQueue(lambda: mock_orchestrator, max_workers=1)
    
    job_id = tq.push_background_task("Test command")
    assert getattr(tq, 'jobs')[job_id] in ["QUEUED", "RUNNING", "COMPLETED"]
    
    # Let thread run for 100ms
    time.sleep(0.1)
    
    assert tq.check_status(job_id) == "COMPLETED"
    assert mock_orchestrator.process_user_message.called
    
    tq.shutdown()
