"""
Event types and Event dataclass for PCA Event Bus

Defines:
- Event dataclass with required metadata fields
- EventType enum with all supported event types
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from uuid import uuid4
import json


class EventSeverity(str, Enum):
    """Event severity levels for alerting and routing"""
    ROUTINE = "routine"
    PRIORITY = "priority"
    FLASH = "flash"


class EventType(str, Enum):
    """Supported event types in PCA"""
    
    # Task lifecycle events
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    PLAN_CREATED = "plan_created"
    EXECUTION_STARTED = "execution_started"
    OBSERVATION_COMPLETED = "observation_completed"
    REFLECTION_TRIGGERED = "reflection_triggered"
    
    # Workflow lifecycle events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    
    # Tool execution events
    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    
    # Knowledge management events
    DOCUMENT_INGESTED = "document_ingested"
    KNOWLEDGE_UPDATED = "knowledge_updated"
    
    # Approval system events
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    
    # Memory system events
    MEMORY_UPDATED = "memory_updated"
    MEMORY_PRUNED = "memory_pruned"
    
    # Health monitoring events
    HEALTH_CHECK_FAILED = "health_check_failed"
    
    # Configuration events
    CONFIG_HOT_RELOADED = "config_hot_reloaded"
    
    # Batch execution events (Feature #6)
    BATCH_STARTED = "batch_started"
    BATCH_COMPLETED = "batch_completed"
    BATCH_TASK_COMPLETED = "batch_task_completed"
    
    # Delegation / supervisor events (Feature #7)
    DELEGATION_STARTED = "delegation_started"
    DELEGATION_COMPLETED = "delegation_completed"
    
    # Skill evolution events (Feature #9)
    SKILL_EVOLVED = "skill_evolved"
    SKILL_PROMOTED = "skill_promoted"
    
    # Verification events (Feature #10)
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"


@dataclass
class Event:
    """
    Event dataclass with standardized metadata
    
    All events in the PCA system include:
    - event_id: Unique identifier (UUID)
    - event_type: Type of event (from EventType enum)
    - event_timestamp: When the event occurred (ISO 8601)
    - source_component: Component that generated the event
    - trace_id: Distributed trace identifier for observability
    - correlation_id: Request correlation identifier
    - workflow_id: Optional workflow identifier for ordering guarantees
    - payload: Event-specific data
    """
    
    event_id: str
    event_type: str
    event_timestamp: datetime
    source_component: str
    trace_id: str
    correlation_id: str
    workflow_id: Optional[str]
    payload: Dict[str, Any]
    severity: EventSeverity = EventSeverity.ROUTINE
    
    @classmethod
    def create(
        cls,
        event_type: EventType,
        source_component: str,
        payload: Dict[str, Any],
        trace_id: str,
        correlation_id: str,
        workflow_id: Optional[str] = None,
        **kwargs
    ) -> 'Event':
        """
        Create a new event with auto-generated ID and timestamp
        
        Args:
            event_type: Type of event
            source_component: Component generating the event
            payload: Event-specific data
            trace_id: Distributed trace ID
            correlation_id: Request correlation ID
            workflow_id: Optional workflow ID for ordering
            severity: Severity level (defaults to ROUTINE)
        
        Returns:
            New Event instance
        """
        return cls(
            event_id=str(uuid4()),
            event_type=event_type.value,
            event_timestamp=datetime.utcnow(),
            source_component=source_component,
            trace_id=trace_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            payload=payload,
            severity=kwargs.get('severity', EventSeverity.ROUTINE)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert event to dictionary
        
        Returns:
            Dictionary representation of event
        """
        data = asdict(self)
        # Convert datetime to ISO 8601 string
        data['event_timestamp'] = self.event_timestamp.isoformat() + 'Z'
        return data
    
    def to_json(self) -> str:
        """
        Convert event to JSON string
        
        Returns:
            JSON representation of event
        """
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """
        Create event from dictionary
        
        Args:
            data: Dictionary with event data
        
        Returns:
            Event instance
        """
        # Parse ISO 8601 timestamp
        if isinstance(data['event_timestamp'], str):
            # Remove 'Z' suffix if present
            timestamp_str = data['event_timestamp'].rstrip('Z')
            data['event_timestamp'] = datetime.fromisoformat(timestamp_str)
        
        return cls(**data)
    
    def validate(self) -> bool:
        """
        Validate that event has all required metadata fields
        
        Returns:
            True if valid, False otherwise
        """
        required_fields = [
            'event_id',
            'event_type',
            'event_timestamp',
            'source_component',
            'trace_id',
            'correlation_id',
            'payload'
        ]
        
        for field in required_fields:
            value = getattr(self, field, None)
            if value is None or (isinstance(value, str) and not value):
                return False
        
        # Validate event_type is a known type
        try:
            EventType(self.event_type)
        except ValueError:
            return False
        
        return True
