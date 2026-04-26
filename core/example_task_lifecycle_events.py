"""
Example: Task Lifecycle Event Emissions

Demonstrates how the Agent Orchestrator emits events at all key points
in the task lifecycle for observability.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_orchestrator import (
    AgentOrchestrator,
    Intent,
    ReasoningState
)
from events.event_types import EventType


def demonstrate_task_lifecycle_events():
    """
    Demonstrate event emissions throughout task lifecycle
    
    Events emitted:
    1. TASK_STARTED - when task begins
    2. PLAN_CREATED - when planning step completes
    3. EXECUTION_STARTED - when execution step starts
    4. OBSERVATION_COMPLETED - when observation step completes
    5. REFLECTION_TRIGGERED - when reflection is triggered
    6. TASK_COMPLETED - when task finishes successfully
    7. TASK_FAILED - when task fails
    """
    print("=" * 60)
    print("Task Lifecycle Event Emissions Demo")
    print("=" * 60)
    print()
    
    # Create orchestrator with reflection enabled
    orchestrator = AgentOrchestrator(enable_reflection=True)
    
    # Create a reasoning state
    state = ReasoningState(
        task_id="demo-task-001",
        iteration=1,
        intent=Intent.TASK,
        current_step="classify"
    )
    state.context = {"command": "Create a report from sales data"}
    
    print("=== Step 1: Planning ===")
    print("Executing plan step...")
    
    # Execute plan step - emits PLAN_CREATED event
    action = orchestrator._handle_plan_step(state)
    print(f"✓ Plan created")
    print(f"  Event emitted: PLAN_CREATED")
    print(f"  Payload includes: intent, plan_steps, iteration, goal")
    print()
    
    print("=== Step 2: Execution ===")
    print("Executing execute step...")
    
    # Execute execute step - emits EXECUTION_STARTED event
    state.current_step = "execute"
    action = orchestrator._handle_execute_step(state)
    print(f"✓ Execution started")
    print(f"  Event emitted: EXECUTION_STARTED")
    print(f"  Payload includes: plan_steps, iteration, goal")
    print()
    
    print("=== Step 3: Observation ===")
    print("Executing observe step...")
    
    # Execute observe step - emits OBSERVATION_COMPLETED event
    state.current_step = "observe"
    state.tool_results = [
        {"status": "success", "tool_name": "file_reader"},
        {"status": "success", "tool_name": "data_analyzer"}
    ]
    action = orchestrator._handle_observe_step(state)
    print(f"✓ Observation completed")
    print(f"  Event emitted: OBSERVATION_COMPLETED")
    print(f"  Payload includes: observation_count, total_observations, iteration, result_count")
    print()
    
    print("=== Step 4: Reflection ===")
    print("Triggering reflection...")
    
    # Trigger reflection - emits REFLECTION_TRIGGERED event
    state.iteration = 3
    reflection = orchestrator.trigger_reflection(state)
    print(f"✓ Reflection triggered")
    print(f"  Event emitted: REFLECTION_TRIGGERED")
    print(f"  Payload includes: reflection_id, iteration, errors_detected, adjustments_needed, confidence_score")
    print(f"  Confidence score: {reflection.confidence_score:.2f}")
    print()
    
    print("=" * 60)
    print("Event Emission Summary")
    print("=" * 60)
    print()
    print("Events emitted during task lifecycle:")
    print("  1. PLAN_CREATED - Planning step completion")
    print("  2. EXECUTION_STARTED - Execution step start")
    print("  3. OBSERVATION_COMPLETED - Observation step completion")
    print("  4. REFLECTION_TRIGGERED - Reflection analysis")
    print()
    print("Additional lifecycle events (not shown):")
    print("  - TASK_STARTED - Task initialization")
    print("  - TASK_COMPLETED - Task successful completion")
    print("  - TASK_FAILED - Task failure")
    print()
    print("All events include standardized metadata:")
    print("  - event_id (UUID)")
    print("  - event_timestamp (ISO 8601)")
    print("  - source_component (agent_orchestrator)")
    print("  - trace_id (distributed tracing)")
    print("  - correlation_id (request correlation)")
    print("  - workflow_id (task_id for ordering)")
    print()
    print("=" * 60)
    print("✓ Demo completed successfully")
    print("=" * 60)


if __name__ == "__main__":
    demonstrate_task_lifecycle_events()
