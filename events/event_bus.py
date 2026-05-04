"""
EventBus: Publish-subscribe event bus with ordering guarantees

Implements:
- Publish-subscribe pattern for decoupled communication
- Event persistence to database
- Per-workflow event ordering using Lamport clocks
- Dead letter queue for failed event deliveries
- Event replay functionality
- Event filtering and subscription management
- Idempotency key validation
"""

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set
from uuid import uuid4

from .event_types import Event, EventType

# Try to import database connection, but make it optional for testing
try:
    from ..database.connection import get_db_connection
    DB_AVAILABLE = True
except (ImportError, ValueError):
    DB_AVAILABLE = False
    def get_db_connection():
        raise RuntimeError("Database connection not available")


logger = logging.getLogger(__name__)


@dataclass
class Subscription:
    """Event subscription"""
    subscription_id: str
    event_type: str
    handler: Callable[[Event], None]
    filter_func: Optional[Callable[[Event], bool]] = None


@dataclass
class DeadLetterEntry:
    """Dead letter queue entry for failed event delivery"""
    entry_id: str
    event: Event
    subscription_id: str
    error_message: str
    retry_count: int
    created_at: datetime
    last_retry_at: Optional[datetime] = None


class LamportClock:
    """
    Lamport clock for per-workflow event ordering
    
    Ensures events are delivered in the order they were published
    within the same workflow.
    """
    
    def __init__(self):
        self._clocks: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
    
    def tick(self, workflow_id: str) -> int:
        """
        Increment clock for workflow and return new value
        
        Args:
            workflow_id: Workflow identifier
        
        Returns:
            New clock value
        """
        with self._lock:
            self._clocks[workflow_id] += 1
            return self._clocks[workflow_id]
    
    def get(self, workflow_id: str) -> int:
        """
        Get current clock value for workflow
        
        Args:
            workflow_id: Workflow identifier
        
        Returns:
            Current clock value
        """
        with self._lock:
            return self._clocks[workflow_id]
    
    def update(self, workflow_id: str, received_time: int) -> int:
        """
        Update clock based on received event time
        
        Args:
            workflow_id: Workflow identifier
            received_time: Received Lamport timestamp
        
        Returns:
            New clock value
        """
        with self._lock:
            self._clocks[workflow_id] = max(self._clocks[workflow_id], received_time) + 1
            return self._clocks[workflow_id]


class EventBus:
    """
    Event bus for publish-subscribe communication
    
    Features:
    - Asynchronous event delivery to subscribers
    - Event persistence to database
    - Per-workflow event ordering guarantees
    - Dead letter queue for failed deliveries
    - Event replay from database
    - Event filtering by type and properties
    - Idempotency key validation
    """
    
    def __init__(
        self,
        enable_persistence: bool = True,
        enable_ordering: bool = True,
        max_retry_attempts: int = 3
    ):
        """
        Initialize event bus
        
        Args:
            enable_persistence: Enable event persistence to database
            enable_persistence: Enable per-workflow event ordering
            max_retry_attempts: Maximum retry attempts for failed deliveries
        """
        self.enable_persistence = enable_persistence
        self.enable_ordering = enable_ordering
        self.max_retry_attempts = max_retry_attempts
        
        # Subscriptions by event type
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        
        # Lock for thread-safe subscription management
        self._subscription_lock = threading.Lock()
        
        # Lamport clock for event ordering
        self._lamport_clock = LamportClock()
        
        # Dead letter queue
        self._dead_letter_queue: List[DeadLetterEntry] = []
        self._dlq_lock = threading.Lock()
        
        # Idempotency tracking (bounded to prevent memory leaks in long sessions)
        self._processed_events: Set[str] = set()
        self._processed_events_order: List[str] = []  # Track insertion order for eviction
        self._max_tracked_events = 10_000
        self._idempotency_lock = threading.Lock()
        
        logger.info(
            f"EventBus initialized: persistence={enable_persistence}, "
            f"ordering={enable_ordering}, max_retries={max_retry_attempts}"
        )
    
    def publish(self, event: Event) -> None:
        """
        Publish event to all subscribers
        
        Args:
            event: Event to publish
        """
        # Validate event has required metadata
        if not event.validate():
            logger.error(f"Event validation failed: {event.event_id}")
            raise ValueError("Event missing required metadata fields")
        
        # Check idempotency
        if not self._check_idempotency(event.event_id):
            logger.debug(f"Duplicate event ignored: {event.event_id}")
            return
        
        # Add Lamport timestamp for ordering if workflow_id present
        lamport_time = None
        if self.enable_ordering and event.workflow_id:
            lamport_time = self._lamport_clock.tick(event.workflow_id)
            event.payload['_lamport_time'] = lamport_time
        
        # Persist event to database
        if self.enable_persistence:
            self._persist_event(event)
        
        # Deliver to subscribers
        self._deliver_event(event)
        
        logger.debug(
            f"Event published: {event.event_type} (id={event.event_id}, "
            f"workflow={event.workflow_id}, lamport={lamport_time})"
        )
    
    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Event], None],
        filter_func: Optional[Callable[[Event], bool]] = None
    ) -> str:
        """
        Subscribe to event type
        
        Args:
            event_type: Event type to subscribe to (or "*" for all events)
            handler: Callback function to handle events
            filter_func: Optional filter function to apply before delivery
        
        Returns:
            Subscription ID
        """
        subscription_id = str(uuid4())
        
        subscription = Subscription(
            subscription_id=subscription_id,
            event_type=event_type,
            handler=handler,
            filter_func=filter_func
        )
        
        with self._subscription_lock:
            self._subscriptions[event_type].append(subscription)
        
        logger.info(f"Subscription created: {subscription_id} for {event_type}")
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> None:
        """
        Remove subscription
        
        Args:
            subscription_id: Subscription ID to remove
        """
        with self._subscription_lock:
            for event_type, subscriptions in self._subscriptions.items():
                self._subscriptions[event_type] = [
                    sub for sub in subscriptions
                    if sub.subscription_id != subscription_id
                ]
        
        logger.info(f"Subscription removed: {subscription_id}")
    
    def replay_events(
        self,
        workflow_id: str,
        from_timestamp: Optional[datetime] = None
    ) -> List[Event]:
        """
        Replay events for workflow from timestamp
        
        Args:
            workflow_id: Workflow identifier
            from_timestamp: Optional start timestamp (replays all if None)
        
        Returns:
            List of events in order
        """
        if not self.enable_persistence:
            logger.warning("Event replay requested but persistence is disabled")
            return []
        
        if not DB_AVAILABLE:
            logger.warning("Event replay requested but database is not available")
            return []
        
        try:
            db = get_db_connection()
            
            with db.get_cursor() as cursor:
                if from_timestamp:
                    cursor.execute(
                        """
                        SELECT event_id, event_type, event_timestamp, source_component,
                               trace_id, correlation_id, workflow_id, payload
                        FROM events
                        WHERE workflow_id = %s AND event_timestamp >= %s
                        ORDER BY event_timestamp ASC
                        """,
                        (workflow_id, from_timestamp)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT event_id, event_type, event_timestamp, source_component,
                               trace_id, correlation_id, workflow_id, payload
                        FROM events
                        WHERE workflow_id = %s
                        ORDER BY event_timestamp ASC
                        """,
                        (workflow_id,)
                    )
                
                rows = cursor.fetchall()
                events = [Event.from_dict(dict(row)) for row in rows]
                
                logger.info(
                    f"Replayed {len(events)} events for workflow {workflow_id}"
                )
                return events
        
        except Exception as e:
            logger.error(f"Event replay failed: {e}")
            raise
    
    def get_dead_letter_queue(self) -> List[DeadLetterEntry]:
        """
        Get all entries in dead letter queue
        
        Returns:
            List of dead letter entries
        """
        with self._dlq_lock:
            return list(self._dead_letter_queue)
    
    def retry_dead_letter(self, entry_id: str) -> bool:
        """
        Retry delivery of dead letter entry
        
        Args:
            entry_id: Dead letter entry ID
        
        Returns:
            True if retry succeeded, False otherwise
        """
        with self._dlq_lock:
            entry = next(
                (e for e in self._dead_letter_queue if e.entry_id == entry_id),
                None
            )
            
            if not entry:
                logger.warning(f"Dead letter entry not found: {entry_id}")
                return False
            
            # Find subscription
            subscription = None
            with self._subscription_lock:
                for subs in self._subscriptions.values():
                    subscription = next(
                        (s for s in subs if s.subscription_id == entry.subscription_id),
                        None
                    )
                    if subscription:
                        break
            
            if not subscription:
                logger.warning(
                    f"Subscription not found for dead letter: {entry.subscription_id}"
                )
                return False
            
            # Attempt delivery
            try:
                subscription.handler(entry.event)
                # Remove from DLQ on success
                self._dead_letter_queue.remove(entry)
                logger.info(f"Dead letter retry succeeded: {entry_id}")
                return True
            
            except Exception as e:
                entry.retry_count += 1
                entry.last_retry_at = datetime.utcnow()
                entry.error_message = str(e)
                logger.error(f"Dead letter retry failed: {entry_id} - {e}")
                return False
    
    def _check_idempotency(self, event_id: str) -> bool:
        """
        Check if event has already been processed.
        Uses a bounded cache to prevent unbounded memory growth.
        
        Args:
            event_id: Event identifier
        
        Returns:
            True if event is new, False if already processed
        """
        with self._idempotency_lock:
            if event_id in self._processed_events:
                return False
            self._processed_events.add(event_id)
            self._processed_events_order.append(event_id)
            # Evict oldest entries when cache exceeds max size
            while len(self._processed_events_order) > self._max_tracked_events:
                oldest = self._processed_events_order.pop(0)
                self._processed_events.discard(oldest)
            return True
    
    def _persist_event(self, event: Event) -> None:
        """
        Persist event to database
        
        Args:
            event: Event to persist
        """
        if not DB_AVAILABLE:
            logger.debug("Database not available, skipping event persistence")
            return
        
        try:
            db = get_db_connection()
            
            with db.get_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO events (
                        event_id, event_type, event_timestamp, source_component,
                        trace_id, correlation_id, workflow_id, payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event.event_id,
                        event.event_type,
                        event.event_timestamp,
                        event.source_component,
                        event.trace_id,
                        event.correlation_id,
                        event.workflow_id,
                        event.payload
                    )
                )
        
        except Exception as e:
            logger.error(f"Event persistence failed: {e}")
            # Don't raise - allow event delivery to continue
    
    def _deliver_event(self, event: Event) -> None:
        """
        Deliver event to all matching subscribers
        
        Args:
            event: Event to deliver
        """
        # Get subscriptions for this event type and wildcard subscriptions
        subscriptions = []
        with self._subscription_lock:
            subscriptions.extend(self._subscriptions.get(event.event_type, []))
            subscriptions.extend(self._subscriptions.get("*", []))
        
        # Deliver to each subscription
        for subscription in subscriptions:
            # Apply filter if present
            if subscription.filter_func and not subscription.filter_func(event):
                continue
            
            # Attempt delivery
            try:
                subscription.handler(event)
            
            except Exception as e:
                logger.error(
                    f"Event delivery failed: subscription={subscription.subscription_id}, "
                    f"event={event.event_id}, error={e}"
                )
                
                # Add to dead letter queue
                self._add_to_dead_letter_queue(event, subscription, str(e))
    
    def _add_to_dead_letter_queue(
        self,
        event: Event,
        subscription: Subscription,
        error_message: str
    ) -> None:
        """
        Add failed delivery to dead letter queue
        
        Args:
            event: Event that failed delivery
            subscription: Subscription that failed
            error_message: Error message
        """
        entry = DeadLetterEntry(
            entry_id=str(uuid4()),
            event=event,
            subscription_id=subscription.subscription_id,
            error_message=error_message,
            retry_count=0,
            created_at=datetime.utcnow()
        )
        
        with self._dlq_lock:
            self._dead_letter_queue.append(entry)
        
        logger.warning(
            f"Event added to dead letter queue: {entry.entry_id} "
            f"(event={event.event_id}, subscription={subscription.subscription_id})"
        )


# Global event bus instance
_event_bus: Optional[EventBus] = None


def initialize_event_bus(
    enable_persistence: bool = True,
    enable_ordering: bool = True,
    max_retry_attempts: int = 3
) -> EventBus:
    """
    Initialize global event bus
    
    Args:
        enable_persistence: Enable event persistence to database
        enable_ordering: Enable per-workflow event ordering
        max_retry_attempts: Maximum retry attempts for failed deliveries
    
    Returns:
        EventBus instance
    """
    global _event_bus
    
    _event_bus = EventBus(
        enable_persistence=enable_persistence,
        enable_ordering=enable_ordering,
        max_retry_attempts=max_retry_attempts
    )
    
    return _event_bus


def get_event_bus() -> EventBus:
    """
    Get global event bus instance
    
    Returns:
        EventBus instance
    
    Raises:
        RuntimeError: If event bus has not been initialized
    """
    global _event_bus
    
    if _event_bus is None:
        raise RuntimeError("Event bus has not been initialized. Call initialize_event_bus() first.")
    
    return _event_bus
