# Event Bus System

The Event Bus System provides publish-subscribe event communication for the Personal Cognitive Agent (PCA) with ordering guarantees, persistence, and reliability features.

## Features

- **Publish-Subscribe Pattern**: Decoupled event communication between components
- **Event Persistence**: All events stored in PostgreSQL database for audit and replay
- **Event Ordering**: Per-workflow event ordering using Lamport clocks
- **Dead Letter Queue**: Failed event deliveries tracked and retryable
- **Event Filtering**: Subscribe with custom filter functions
- **Idempotency**: Duplicate events automatically ignored
- **Event Replay**: Replay events for a workflow from any timestamp

## Architecture

### Event Structure

All events include standardized metadata:

```python
@dataclass
class Event:
    event_id: str              # UUID
    event_type: str            # Event type (from EventType enum)
    event_timestamp: datetime  # ISO 8601 timestamp
    source_component: str      # Component that generated the event
    trace_id: str             # Distributed trace ID
    correlation_id: str       # Request correlation ID
    workflow_id: Optional[str] # For ordering guarantees
    payload: Dict[str, Any]   # Event-specific data
```

### Supported Event Types

- **Task Lifecycle**: `task_started`, `task_completed`, `task_failed`, `plan_created`, `execution_started`, `observation_completed`, `reflection_triggered`
- **Workflow Lifecycle**: `workflow_started`, `workflow_completed`, `workflow_failed`
- **Tool Execution**: `tool_execution_started`, `tool_execution_completed`, `tool_execution_failed`
- **Knowledge Management**: `document_ingested`, `knowledge_updated`
- **Approval System**: `approval_requested`, `approval_granted`, `approval_denied`
- **Memory System**: `memory_updated`, `memory_pruned`
- **Health Monitoring**: `health_check_failed`

## Usage

### Initialization

```python
from events import initialize_event_bus

# Initialize event bus (typically done at system startup)
event_bus = initialize_event_bus(
    enable_persistence=True,  # Store events in database
    enable_ordering=True,     # Use Lamport clocks for ordering
    max_retry_attempts=3      # Retry failed deliveries
)
```

### Publishing Events

```python
from events import Event, EventType, get_event_bus

# Create and publish an event
event = Event.create(
    event_type=EventType.TASK_STARTED,
    source_component="agent_orchestrator",
    payload={
        "task_id": "task-123",
        "goal": "Process user request"
    },
    trace_id="trace-abc-123",
    correlation_id="corr-xyz-456",
    workflow_id="workflow-789"  # Optional, for ordering
)

event_bus = get_event_bus()
event_bus.publish(event)
```

### Subscribing to Events

```python
from events import get_event_bus, Event, EventType

def handle_task_completion(event: Event):
    """Handle task completion events"""
    task_id = event.payload.get("task_id")
    result = event.payload.get("result")
    print(f"Task {task_id} completed with result: {result}")

# Subscribe to specific event type
event_bus = get_event_bus()
subscription_id = event_bus.subscribe(
    event_type=EventType.TASK_COMPLETED.value,
    handler=handle_task_completion
)

# Later, unsubscribe if needed
event_bus.unsubscribe(subscription_id)
```

### Wildcard Subscriptions

```python
def handle_all_events(event: Event):
    """Handle all events"""
    print(f"Received event: {event.event_type} from {event.source_component}")

# Subscribe to all event types
subscription_id = event_bus.subscribe(
    event_type="*",
    handler=handle_all_events
)
```

### Event Filtering

```python
def handle_high_priority_tasks(event: Event):
    """Handle only high priority task events"""
    print(f"High priority task: {event.payload['task_id']}")

def priority_filter(event: Event) -> bool:
    """Filter for high priority events"""
    return event.payload.get("priority") == "high"

# Subscribe with filter
subscription_id = event_bus.subscribe(
    event_type=EventType.TASK_STARTED.value,
    handler=handle_high_priority_tasks,
    filter_func=priority_filter
)
```

### Event Replay

```python
from datetime import datetime, timedelta

# Replay all events for a workflow
events = event_bus.replay_events(workflow_id="workflow-789")

# Replay events from a specific timestamp
start_time = datetime.utcnow() - timedelta(hours=1)
recent_events = event_bus.replay_events(
    workflow_id="workflow-789",
    from_timestamp=start_time
)

# Process replayed events
for event in events:
    print(f"Event: {event.event_type} at {event.event_timestamp}")
```

### Dead Letter Queue

```python
# Get failed deliveries
dead_letters = event_bus.get_dead_letter_queue()

for entry in dead_letters:
    print(f"Failed delivery: {entry.event.event_id}")
    print(f"Error: {entry.error_message}")
    print(f"Retry count: {entry.retry_count}")

# Retry a specific failed delivery
success = event_bus.retry_dead_letter(entry_id="dlq-entry-123")
if success:
    print("Retry succeeded")
else:
    print("Retry failed")
```

## Event Ordering Guarantees

The Event Bus uses Lamport clocks to guarantee per-workflow event ordering:

1. Each workflow has an independent logical clock
2. When an event is published with a `workflow_id`, the clock is incremented
3. The Lamport timestamp is added to the event payload as `_lamport_time`
4. Events can be ordered by their Lamport timestamps within a workflow

This ensures that events are delivered in the order they were published, even in distributed systems.

## Idempotency

The Event Bus automatically tracks processed events by `event_id`:

- If an event with the same `event_id` is published twice, the second publish is ignored
- This prevents duplicate event processing
- Useful for retry scenarios and distributed systems

## Integration with Logging

Events are automatically logged when published:

```python
# Event publication is logged with:
# - Event type
# - Event ID
# - Workflow ID (if present)
# - Lamport timestamp (if ordering enabled)
```

## Integration with Database

Events are persisted to the `events` table:

```sql
CREATE TABLE events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    source_component VARCHAR(100) NOT NULL,
    trace_id VARCHAR(100) NOT NULL,
    correlation_id VARCHAR(100) NOT NULL,
    workflow_id UUID,
    payload JSONB NOT NULL
);
```

Indexes are created for efficient querying:
- `event_type` - Query by event type
- `event_timestamp` - Query by time range
- `workflow_id` - Query by workflow
- `trace_id` - Query by trace

## Best Practices

### 1. Use Appropriate Event Types

Choose the correct event type from the `EventType` enum. This enables type-safe event handling and filtering.

### 2. Include Trace and Correlation IDs

Always include `trace_id` and `correlation_id` for distributed tracing and request correlation:

```python
event = Event.create(
    event_type=EventType.TOOL_EXECUTION_STARTED,
    source_component="tool_executor",
    payload={"tool": "file_manager"},
    trace_id=current_trace_id,      # From tracing system
    correlation_id=current_corr_id  # From request context
)
```

### 3. Use Workflow IDs for Ordering

If events need to be ordered within a workflow, always include `workflow_id`:

```python
event = Event.create(
    event_type=EventType.WORKFLOW_STARTED,
    source_component="workflow_engine",
    payload={"workflow_name": "data_processing"},
    trace_id=trace_id,
    correlation_id=correlation_id,
    workflow_id=workflow_id  # Enables ordering
)
```

### 4. Keep Payloads Focused

Event payloads should contain only relevant data for the event:

```python
# Good: Focused payload
payload = {
    "task_id": "task-123",
    "status": "completed",
    "duration_ms": 1500
}

# Avoid: Overly large payloads
# Don't include entire objects or large data structures
```

### 5. Handle Failures Gracefully

Event handlers should handle exceptions gracefully:

```python
def safe_handler(event: Event):
    try:
        # Process event
        process_event(event)
    except Exception as e:
        logger.error(f"Event handling failed: {e}")
        # Don't re-raise - let event bus handle via DLQ
```

### 6. Monitor Dead Letter Queue

Regularly check the dead letter queue for failed deliveries:

```python
# Periodic check (e.g., in a background job)
dlq = event_bus.get_dead_letter_queue()
if len(dlq) > 0:
    logger.warning(f"Dead letter queue has {len(dlq)} entries")
    # Alert administrators or attempt retries
```

## Testing

### Unit Tests

The event bus includes comprehensive unit tests:

```bash
python -m unittest events.test_event_bus -v
```

### Integration Tests

For integration testing with database:

```python
from events import initialize_event_bus, Event, EventType

# Initialize with test database
event_bus = initialize_event_bus(enable_persistence=True)

# Publish test event
event = Event.create(
    event_type=EventType.TASK_STARTED,
    source_component="test",
    payload={"test": "data"},
    trace_id="test-trace",
    correlation_id="test-corr"
)

event_bus.publish(event)

# Verify persistence
events = event_bus.replay_events(workflow_id=None)
assert len(events) > 0
```

## Performance Considerations

### Event Delivery

- Event delivery is synchronous within the publish call
- Handlers are called sequentially for each subscription
- Long-running handlers will block event delivery
- Consider using async handlers or background processing for heavy operations

### Database Persistence

- Event persistence is synchronous but doesn't block delivery on failure
- Failed persistence is logged but doesn't prevent event delivery
- Consider batching for high-volume event scenarios

### Memory Usage

- Idempotency tracking uses in-memory set of event IDs
- Dead letter queue is stored in memory
- Consider periodic cleanup for long-running systems

## Troubleshooting

### Events Not Being Delivered

1. Check that subscription is active: `event_bus._subscriptions`
2. Verify event type matches subscription
3. Check filter function if used
4. Look for exceptions in handler

### Events Not Persisted

1. Verify database connection is initialized
2. Check `enable_persistence=True` in initialization
3. Review database logs for errors
4. Verify `events` table exists

### Ordering Issues

1. Verify `enable_ordering=True` in initialization
2. Check that `workflow_id` is set on events
3. Verify Lamport timestamps in event payloads
4. Review event timestamps in database

## Future Enhancements

Potential improvements for future versions:

- Async event delivery with thread pool
- Event batching for high-volume scenarios
- Event retention policies and automatic cleanup
- Event schema validation
- Event versioning support
- Distributed event bus with message queue backend (RabbitMQ, Kafka)
- Event sourcing patterns for state reconstruction
