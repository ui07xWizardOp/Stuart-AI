"""
Tests for Automation Scheduler
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock
import time
import schedule

# Mock observability module

from automation.scheduler import AutomationScheduler

def test_scheduler_intervals():
    # Make sure schedule is clear natively
    schedule.clear()
    
    mock_push = MagicMock()
    sch = AutomationScheduler(mock_push)
    
    job_id = sch.add_interval_job(5, "Do work")
    
    assert job_id in sch.jobs
    assert "Active" in sch.list_jobs()
    
    # Force run pending to check firing mechanic theoretically 
    # (can't easily mock time inside `schedule` safely without freezing, 
    # but we can call the internal callback directly to ensure wiring)
    sch._fire_job("Do work")
    
    mock_push.assert_called_with("Do work")
    
    assert sch.cancel_job(job_id) is True
    assert job_id not in sch.jobs
