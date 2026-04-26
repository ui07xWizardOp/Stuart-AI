"""
Example usage of Event Bus System

Demonstrates:
- Event bus initialization
- Publishing events
- Subscribing to events
- Event filtering
- Event replay
- Dead letter queue handling
"""

from datetime import datetime
from event_types import Event, EventType
from event_bus import EventBus


def example_basic_publish_subscribe():
    """Example: Basic publish and subscribe"""
    print("\n=== Basic Publish/Subscribe ===")
    
    # Initialize event bus (without database for example)
    event_bus = EventBus(enable_persistence=False, enable_ordering=True)
    
    # Define event handler
    def handle_task_started(event: Event):
        print(f"Task started: {event.payload.get('task_id')}")
        print(f"  Trace ID: {event.trace_id}")
        print(f"  Timestamp: {event.event_timestamp}")
    
    # Subscribe to task_started events
    subscription_id = event_bus.subscribe(
        event_type=EventType.TASK_STARTED.value,
        handler=handle_task_started
    )
    
    # Publish an event
    event = Event.create(
        event_type=EventType.TASK_STARTED,
        source_component="agent_orchestrator",
        payload={
            "task_id": "task-123",
            "goal": "Process user request"
        },
        trace_id="trace-abc-123",
        correlation_id="corr-xyz-456"
    )
    
    event_bus.publish(event)
    
    # Cleanup
    event_bus.unsubscribe(subscription_id)


def example_event_filtering():
    """Example: Event filtering with custom filter function"""
    print("\n=== Event Filtering ===")
    
    event_bus = EventBus(enable_persistence=False, enable_ordering=True)
    
    # Handler for high priority tasks only
    def handle_high_priority(event: Event):
        print(f"High priority task: {event.payload.get('task_id')}")
    
    # Filter function
    def priority_filter(event: Event) -> bool:
        return event.payload.get("priority") == "high"
    
    # Subscribe with filter
    subscription_id = event_bus.subscribe(
        event_type=EventType.TASK_STARTED.value,
        handler=handle_high_priority,
        filter_func=priority_filter
    )
    
    # Publish high priority event (will be delivered)
    event1 = Event.create(
        event_type=EventType.TASK_STARTED,
        source_component="test",
        payload={"task_id": "task-1", "priority": "high"},
        trace_id="trace-1",
        correlation_id="corr-1"
    )
    event_bus.publish(event1)
    
    # Publish low priority event (will be filtered out)
    event2 = Event.create(
        event_type=EventType.TASK_STARTED,
        source_component="test",
        payload={"task_id": "task-2", "priority": "low"},
        trace_id="trace-2",
        correlation_id="corr-2"
    )
    event_bus.publish(event2)
    
    event_bus.unsubscribe(subscription_id)


def example_wildcard_subscription():
    """Example: Wildcard subscription for all events"""
    print("\n=== Wildcard Subscription ===")
    
    event_bus = EventBus(enable_persistence=False, enable_ordering=True)
    
    # Handler for all events
    def handle_all_events(event: Event):
        print(f"Event: {event.event_type} from {event.source_component}")
    
    # Subscribe to all events with wildcard
    subscription_id = event_bus.subscribe(
        event_type="*",
        handler=handle_all_events
    )
    
    # Publish different event types
    events = [
        Event.create(
            event_type=EventType.TASK_STARTED,
            source_component="orchestrator",
            payload={},
            trace_id="trace-1",
            correlation_id="corr-1"
        ),
        Event.create(
            event_type=EventType.WORKFLOW_COMPLETED,
            source_component="workflow_engine",
            payload={},
            trace_id="trace-2",
            correlation_id="corr-2"
        ),
        Event.create(
            event_type=EventType.TOOL_EXECUTION_STARTED,
            source_component="tool_executor",
            payload={},
            trace_id="trace-3",
            correlation_id="corr-3"
        )
    ]
    
    for event in events:
        event_bus.publish(event)
    
    event_bus.unsubscribe(subscription_id)


def example_event_ordering():
    """Example: Event ordering with Lamport clocks"""
    print("\n=== Event Ordering ===")
    
    event_bus = EventBus(enable_persistence=False, enable_ordering=True)
    
    workflow_id = "workflow-123"
    
    # Publish multiple events for same workflow
    events = []
    for i in range(5):
        event = Event.create(
            event_type=EventType.TASK_STARTED,
            source_component="test",
            payload={"step": i},
            trace_id=f"trace-{i}",
            correlation_id=f"corr-{i}",
            workflow_id=workflow_id
        )
        event_bus.publish(event)
        events.append(event)
    
    # Check Lamport timestamps
    print(f"Workflow: {workflow_id}")
    for event in events:
        lamport_time = event.payload.get('_lamport_time')
        print(f"  Step {event.payload['step']}: Lamport time = {lamport_time}")


def example_dead_letter_queue():
    """Example: Dead letter queue for failed deliveries"""
    print("\n=== Dead Letter Queue ===")
    
    event_bus = EventBus(enable_persistence=False, enable_ordering=True)
    
    # Handler that always fails
    def failing_handler(event: Event):
        raise Exception("Simulated handler failure")
    
    # Subscribe with failing handler
    subscription_id = event_bus.subscribe(
        event_type=EventType.TASK_FAILED.value,
        handler=failing_handler
    )
    
    # Publish event (will fail and go to DLQ)
    event = Event.create(
        event_type=EventType.TASK_FAILED,
        source_component="test",
        payload={"error": "test error"},
        trace_id="trace-1",
        correlation_id="corr-1"
    )
    
    event_bus.publish(event)
    
    # Check dead letter queue
    dlq = event_bus.get_dead_letter_queue()
    print(f"Dead letter queue size: {len(dlq)}")
    
    if dlq:
        entry = dlq[0]
        print(f"  Event ID: {entry.event.event_id}")
        print(f"  Error: {entry.error_message}")
        print(f"  Retry count: {entry.retry_count}")
    
    event_bus.unsubscribe(subscription_id)


def example_idempotency():
    """Example: Idempotency prevents duplicate processing"""
    print("\n=== Idempotency ===")
    
    event_bus = EventBus(enable_persistence=False, enable_ordering=True)
    
    received_count = [0]  # Use list to modify in closure
    
    def handler(event: Event):
        received_count[0] += 1
        print(f"Event received (count: {received_count[0]})")
    
    subscription_id = event_bus.subscribe(
        event_type=EventType.TASK_COMPLETED.value,
        handler=handler
    )
    
    # Create event with specific ID
    event = Event(
        event_id="duplicate-test-123",
        event_type=EventType.TASK_COMPLETED.value,
        event_timestamp=datetime.utcnow(),
        source_component="test",
        trace_id="trace-1",
        correlation_id="corr-1",
        workflow_id=None,
        payload={"result": "success"}
    )
    
    # Publish same event multiple times
    print("Publishing event 3 times with same ID...")
    event_bus.publish(event)
    event_bus.publish(event)
    event_bus.publish(event)
    
    print(f"Total deliveries: {received_count[0]} (should be 1)")
    
    event_bus.unsubscribe(subscription_id)


def example_multiple_subscribers():
    """Example: Multiple subscribers to same event"""
    print("\n=== Multiple Subscribers ===")
    
    event_bus = EventBus(enable_persistence=False, enable_ordering=True)
    
    # Multiple handlers
    def handler1(event: Event):
        print(f"Handler 1: Processing {event.event_type}")
    
    def handler2(event: Event):
        print(f"Handler 2: Logging {event.event_type}")
    
    def handler3(event: Event):
        print(f"Handler 3: Monitoring {event.event_type}")
    
    # Subscribe all handlers to same event type
    sub1 = event_bus.subscribe(EventType.WORKFLOW_STARTED.value, handler1)
    sub2 = event_bus.subscribe(EventType.WORKFLOW_STARTED.value, handler2)
    sub3 = event_bus.subscribe(EventType.WORKFLOW_STARTED.value, handler3)
    
    # Publish event (all handlers will be called)
    event = Event.create(
        event_type=EventType.WORKFLOW_STARTED,
        source_component="workflow_engine",
        payload={"workflow_name": "data_processing"},
        trace_id="trace-1",
        correlation_id="corr-1"
    )
    
    event_bus.publish(event)
    
    # Cleanup
    event_bus.unsubscribe(sub1)
    event_bus.unsubscribe(sub2)
    event_bus.unsubscribe(sub3)


def main():
    """Run all examples"""
    print("Event Bus System - Usage Examples")
    print("=" * 50)
    
    example_basic_publish_subscribe()
    example_event_filtering()
    example_wildcard_subscription()
    example_event_ordering()
    example_dead_letter_queue()
    example_idempotency()
    example_multiple_subscribers()
    
    print("\n" + "=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    main()
