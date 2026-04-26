"""
Unit tests for Event Bus System

Tests:
- Event creation and validation
- Event serialization/deserialization
- EventBus publish/subscribe
- Event filtering
- Event ordering with Lamport clocks
- Dead letter queue
- Idempotency validation
- Event replay
"""

import unittest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from .event_types import Event, EventType
from .event_bus import EventBus, Subscription, LamportClock


class TestEvent(unittest.TestCase):
    """Test Event dataclass"""
    
    def test_create_event(self):
        """Test event creation with auto-generated fields"""
        event = Event.create(
            event_type=EventType.TASK_STARTED,
            source_component="test_component",
            payload={"task_id": "123"},
            trace_id="trace-123",
            correlation_id="corr-123",
            workflow_id="workflow-123"
        )
        
        self.assertIsNotNone(event.event_id)
        self.assertEqual(event.event_type, EventType.TASK_STARTED.value)
        self.assertEqual(event.source_component, "test_component")
        self.assertEqual(event.trace_id, "trace-123")
        self.assertEqual(event.correlation_id, "corr-123")
        self.assertEqual(event.workflow_id, "workflow-123")
        self.assertEqual(event.payload, {"task_id": "123"})
        self.assertIsInstance(event.event_timestamp, datetime)
    
    def test_event_validation_success(self):
        """Test event validation with valid event"""
        event = Event.create(
            event_type=EventType.TASK_COMPLETED,
            source_component="executor",
            payload={"result": "success"},
            trace_id="trace-456",
            correlation_id="corr-456"
        )
        
        self.assertTrue(event.validate())
    
    def test_event_validation_missing_fields(self):
        """Test event validation with missing fields"""
        event = Event(
            event_id="",
            event_type=EventType.TASK_FAILED.value,
            event_timestamp=datetime.utcnow(),
            source_component="",
            trace_id="trace-789",
            correlation_id="corr-789",
            workflow_id=None,
            payload={}
        )
        
        self.assertFalse(event.validate())
    
    def test_event_validation_invalid_type(self):
        """Test event validation with invalid event type"""
        event = Event(
            event_id=str(uuid4()),
            event_type="invalid_type",
            event_timestamp=datetime.utcnow(),
            source_component="test",
            trace_id="trace-999",
            correlation_id="corr-999",
            workflow_id=None,
            payload={}
        )
        
        self.assertFalse(event.validate())
    
    def test_event_serialization(self):
        """Test event to_dict and to_json"""
        event = Event.create(
            event_type=EventType.WORKFLOW_STARTED,
            source_component="workflow_engine",
            payload={"workflow_name": "test_workflow"},
            trace_id="trace-111",
            correlation_id="corr-111"
        )
        
        # Test to_dict
        event_dict = event.to_dict()
        self.assertIn('event_id', event_dict)
        self.assertIn('event_timestamp', event_dict)
        self.assertIsInstance(event_dict['event_timestamp'], str)
        self.assertTrue(event_dict['event_timestamp'].endswith('Z'))
        
        # Test to_json
        event_json = event.to_json()
        self.assertIsInstance(event_json, str)
        self.assertIn(event.event_id, event_json)
    
    def test_event_deserialization(self):
        """Test event from_dict"""
        original_event = Event.create(
            event_type=EventType.TOOL_EXECUTION_COMPLETED,
            source_component="tool_executor",
            payload={"tool": "file_manager", "result": "success"},
            trace_id="trace-222",
            correlation_id="corr-222"
        )
        
        # Serialize and deserialize
        event_dict = original_event.to_dict()
        restored_event = Event.from_dict(event_dict)
        
        self.assertEqual(restored_event.event_id, original_event.event_id)
        self.assertEqual(restored_event.event_type, original_event.event_type)
        self.assertEqual(restored_event.source_component, original_event.source_component)
        self.assertEqual(restored_event.payload, original_event.payload)


class TestLamportClock(unittest.TestCase):
    """Test Lamport clock for event ordering"""
    
    def test_tick(self):
        """Test clock tick increments value"""
        clock = LamportClock()
        workflow_id = "workflow-1"
        
        time1 = clock.tick(workflow_id)
        time2 = clock.tick(workflow_id)
        time3 = clock.tick(workflow_id)
        
        self.assertEqual(time1, 1)
        self.assertEqual(time2, 2)
        self.assertEqual(time3, 3)
    
    def test_get(self):
        """Test getting current clock value"""
        clock = LamportClock()
        workflow_id = "workflow-2"
        
        self.assertEqual(clock.get(workflow_id), 0)
        clock.tick(workflow_id)
        self.assertEqual(clock.get(workflow_id), 1)
    
    def test_update(self):
        """Test updating clock with received time"""
        clock = LamportClock()
        workflow_id = "workflow-3"
        
        # Local clock is at 0, receive event with time 5
        new_time = clock.update(workflow_id, 5)
        self.assertEqual(new_time, 6)  # max(0, 5) + 1
        
        # Local clock is at 6, receive event with time 3
        new_time = clock.update(workflow_id, 3)
        self.assertEqual(new_time, 7)  # max(6, 3) + 1
    
    def test_multiple_workflows(self):
        """Test independent clocks for different workflows"""
        clock = LamportClock()
        
        workflow1 = "workflow-a"
        workflow2 = "workflow-b"
        
        clock.tick(workflow1)
        clock.tick(workflow1)
        clock.tick(workflow2)
        
        self.assertEqual(clock.get(workflow1), 2)
        self.assertEqual(clock.get(workflow2), 1)


class TestEventBus(unittest.TestCase):
    """Test EventBus publish/subscribe functionality"""
    
    def setUp(self):
        """Set up test event bus"""
        self.event_bus = EventBus(
            enable_persistence=False,  # Disable for unit tests
            enable_ordering=True,
            max_retry_attempts=3
        )
    
    def test_publish_and_subscribe(self):
        """Test basic publish/subscribe"""
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        # Subscribe to event type
        sub_id = self.event_bus.subscribe(EventType.TASK_STARTED.value, handler)
        
        # Publish event
        event = Event.create(
            event_type=EventType.TASK_STARTED,
            source_component="test",
            payload={"test": "data"},
            trace_id="trace-1",
            correlation_id="corr-1"
        )
        
        self.event_bus.publish(event)
        
        # Verify delivery
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].event_id, event.event_id)
    
    def test_wildcard_subscription(self):
        """Test wildcard subscription receives all events"""
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        # Subscribe to all events
        self.event_bus.subscribe("*", handler)
        
        # Publish different event types
        event1 = Event.create(
            event_type=EventType.TASK_STARTED,
            source_component="test",
            payload={},
            trace_id="trace-1",
            correlation_id="corr-1"
        )
        event2 = Event.create(
            event_type=EventType.WORKFLOW_COMPLETED,
            source_component="test",
            payload={},
            trace_id="trace-2",
            correlation_id="corr-2"
        )
        
        self.event_bus.publish(event1)
        self.event_bus.publish(event2)
        
        # Verify both received
        self.assertEqual(len(received_events), 2)
    
    def test_event_filtering(self):
        """Test event filtering with filter function"""
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        def filter_func(event: Event) -> bool:
            return event.payload.get("priority") == "high"
        
        # Subscribe with filter
        self.event_bus.subscribe(
            EventType.TASK_STARTED.value,
            handler,
            filter_func=filter_func
        )
        
        # Publish events with different priorities
        event1 = Event.create(
            event_type=EventType.TASK_STARTED,
            source_component="test",
            payload={"priority": "high"},
            trace_id="trace-1",
            correlation_id="corr-1"
        )
        event2 = Event.create(
            event_type=EventType.TASK_STARTED,
            source_component="test",
            payload={"priority": "low"},
            trace_id="trace-2",
            correlation_id="corr-2"
        )
        
        self.event_bus.publish(event1)
        self.event_bus.publish(event2)
        
        # Only high priority event should be received
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].payload["priority"], "high")
    
    def test_unsubscribe(self):
        """Test unsubscribing from events"""
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        # Subscribe and then unsubscribe
        sub_id = self.event_bus.subscribe(EventType.TASK_COMPLETED.value, handler)
        self.event_bus.unsubscribe(sub_id)
        
        # Publish event
        event = Event.create(
            event_type=EventType.TASK_COMPLETED,
            source_component="test",
            payload={},
            trace_id="trace-1",
            correlation_id="corr-1"
        )
        
        self.event_bus.publish(event)
        
        # Should not receive event
        self.assertEqual(len(received_events), 0)
    
    def test_lamport_clock_ordering(self):
        """Test Lamport clock adds ordering to events"""
        workflow_id = "workflow-test"
        
        event1 = Event.create(
            event_type=EventType.TASK_STARTED,
            source_component="test",
            payload={},
            trace_id="trace-1",
            correlation_id="corr-1",
            workflow_id=workflow_id
        )
        event2 = Event.create(
            event_type=EventType.TASK_COMPLETED,
            source_component="test",
            payload={},
            trace_id="trace-2",
            correlation_id="corr-2",
            workflow_id=workflow_id
        )
        
        self.event_bus.publish(event1)
        self.event_bus.publish(event2)
        
        # Check Lamport timestamps were added
        self.assertIn('_lamport_time', event1.payload)
        self.assertIn('_lamport_time', event2.payload)
        self.assertEqual(event1.payload['_lamport_time'], 1)
        self.assertEqual(event2.payload['_lamport_time'], 2)
    
    def test_idempotency(self):
        """Test duplicate events are ignored"""
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        self.event_bus.subscribe(EventType.TASK_STARTED.value, handler)
        
        # Create event with specific ID
        event = Event(
            event_id="duplicate-test",
            event_type=EventType.TASK_STARTED.value,
            event_timestamp=datetime.utcnow(),
            source_component="test",
            trace_id="trace-1",
            correlation_id="corr-1",
            workflow_id=None,
            payload={}
        )
        
        # Publish same event twice
        self.event_bus.publish(event)
        self.event_bus.publish(event)
        
        # Should only receive once
        self.assertEqual(len(received_events), 1)
    
    def test_dead_letter_queue(self):
        """Test failed deliveries go to dead letter queue"""
        def failing_handler(event: Event):
            raise Exception("Handler failed")
        
        self.event_bus.subscribe(EventType.TASK_FAILED.value, failing_handler)
        
        event = Event.create(
            event_type=EventType.TASK_FAILED,
            source_component="test",
            payload={},
            trace_id="trace-1",
            correlation_id="corr-1"
        )
        
        self.event_bus.publish(event)
        
        # Check dead letter queue
        dlq = self.event_bus.get_dead_letter_queue()
        self.assertEqual(len(dlq), 1)
        self.assertEqual(dlq[0].event.event_id, event.event_id)
        self.assertIn("Handler failed", dlq[0].error_message)
    
    def test_invalid_event_rejected(self):
        """Test invalid events are rejected"""
        invalid_event = Event(
            event_id="",  # Invalid: empty ID
            event_type=EventType.TASK_STARTED.value,
            event_timestamp=datetime.utcnow(),
            source_component="test",
            trace_id="trace-1",
            correlation_id="corr-1",
            workflow_id=None,
            payload={}
        )
        
        with self.assertRaises(ValueError):
            self.event_bus.publish(invalid_event)
    
    @patch('Personal Agent.Stuart-AI.events.event_bus.get_db_connection')
    def test_event_replay(self, mock_get_db):
        """Test event replay from database"""
        # Create event bus with persistence enabled
        event_bus = EventBus(enable_persistence=True, enable_ordering=True)
        
        # Mock database cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'event_id': 'event-1',
                'event_type': EventType.TASK_STARTED.value,
                'event_timestamp': '2024-01-01T10:00:00Z',
                'source_component': 'test',
                'trace_id': 'trace-1',
                'correlation_id': 'corr-1',
                'workflow_id': 'workflow-1',
                'payload': {'test': 'data'}
            }
        ]
        
        mock_db = MagicMock()
        mock_db.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_db.return_value = mock_db
        
        # Replay events
        events = event_bus.replay_events('workflow-1')
        
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_id, 'event-1')


if __name__ == '__main__':
    unittest.main()
