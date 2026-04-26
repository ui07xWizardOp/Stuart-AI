"""
Simple standalone test for Event Bus System
Tests basic functionality without database dependencies
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from uuid import uuid4
from events.event_types import Event, EventType


def test_event_creation():
    """Test creating events"""
    print("Testing event creation...")
    
    event = Event.create(
        event_type=EventType.TASK_STARTED,
        source_component="test_component",
        payload={"task_id": "123", "goal": "test goal"},
        trace_id="trace-123",
        correlation_id="corr-123",
        workflow_id="workflow-123"
    )
    
    assert event.event_id is not None
    assert event.event_type == EventType.TASK_STARTED.value
    assert event.source_component == "test_component"
    assert event.trace_id == "trace-123"
    assert event.correlation_id == "corr-123"
    assert event.workflow_id == "workflow-123"
    assert event.payload["task_id"] == "123"
    
    print("✓ Event creation works")


def test_event_validation():
    """Test event validation"""
    print("Testing event validation...")
    
    # Valid event
    valid_event = Event.create(
        event_type=EventType.TASK_COMPLETED,
        source_component="executor",
        payload={"result": "success"},
        trace_id="trace-456",
        correlation_id="corr-456"
    )
    
    assert valid_event.validate() == True
    
    # Invalid event (empty ID)
    invalid_event = Event(
        event_id="",
        event_type=EventType.TASK_FAILED.value,
        event_timestamp=datetime.utcnow(),
        source_component="test",
        trace_id="trace-789",
        correlation_id="corr-789",
        workflow_id=None,
        payload={}
    )
    
    assert invalid_event.validate() == False
    
    print("✓ Event validation works")


def test_event_serialization():
    """Test event serialization"""
    print("Testing event serialization...")
    
    original_event = Event.create(
        event_type=EventType.WORKFLOW_STARTED,
        source_component="workflow_engine",
        payload={"workflow_name": "test_workflow"},
        trace_id="trace-111",
        correlation_id="corr-111"
    )
    
    # Test to_dict
    event_dict = original_event.to_dict()
    assert 'event_id' in event_dict
    assert 'event_timestamp' in event_dict
    assert isinstance(event_dict['event_timestamp'], str)
    assert event_dict['event_timestamp'].endswith('Z')
    
    # Test to_json
    event_json = original_event.to_json()
    assert isinstance(event_json, str)
    assert original_event.event_id in event_json
    
    # Test from_dict
    restored_event = Event.from_dict(event_dict)
    assert restored_event.event_id == original_event.event_id
    assert restored_event.event_type == original_event.event_type
    assert restored_event.source_component == original_event.source_component
    
    print("✓ Event serialization works")


def test_event_types():
    """Test all event types are defined"""
    print("Testing event types...")
    
    expected_types = [
        "task_started", "task_completed", "task_failed",
        "plan_created", "execution_started", "observation_completed", "reflection_triggered",
        "workflow_started", "workflow_completed", "workflow_failed",
        "tool_execution_started", "tool_execution_completed", "tool_execution_failed",
        "document_ingested", "knowledge_updated",
        "approval_requested", "approval_granted", "approval_denied",
        "memory_updated", "memory_pruned",
        "health_check_failed"
    ]
    
    for event_type in expected_types:
        # Verify enum value exists
        enum_value = EventType(event_type)
        assert enum_value.value == event_type
    
    print(f"✓ All {len(expected_types)} event types defined")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Event Bus System - Simple Tests")
    print("=" * 60)
    print()
    
    try:
        test_event_creation()
        test_event_validation()
        test_event_serialization()
        test_event_types()
        
        print()
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
