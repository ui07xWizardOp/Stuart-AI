"""
Example: Enhanced Reasoning Step Execution Coordination

Demonstrates the enhanced execute_reasoning_step() method with:
- Proper component coordination for each OODA step
- State management and transitions
- Error handling and validation
- Event emission for observability
- Placeholder methods for components not yet implemented

Usage:
    Run from the Stuart-AI directory:
    $ cd "Personal Agent/Stuart-AI"
    $ python -c "import sys; sys.path.insert(0, '.'); exec(open('core/example_reasoning_coordination.py').read())"
    
    Or run the simple test instead:
    $ python core/simple_test_orchestrator.py
"""

from core.agent_orchestrator import (
    AgentOrchestrator,
    ReasoningState,
    Intent
)
from datetime import datetime


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print('=' * 60)


def print_action(action, iteration: int):
    """Print reasoning action details"""
    print(f"\nIteration {iteration}:")
    print(f"  Action Type: {action.action_type}")
    print(f"  Should Continue: {action.should_continue}")
    print(f"  Reason: {action.reason}")
    if action.action_data:
        print(f"  Data: {action.action_data}")


def example_full_reasoning_loop():
    """
    Example: Complete reasoning loop through all OODA steps
    
    Demonstrates:
    - classify -> plan -> execute -> observe -> reason flow
    - State transitions between steps
    - Component coordination (with placeholders)
    """
    print_section("Example 1: Full Reasoning Loop")
    
    orchestrator = AgentOrchestrator()
    
    # Initialize reasoning state
    state = ReasoningState(
        task_id="task-001",
        iteration=1,
        intent=Intent.TASK,
        current_step="classify",
        plan=None,
        tool_results=[],
        observations=[],
        context={"command": "Create a summary report from sales data"},
        metadata={}
    )
    
    print(f"\nInitial State:")
    print(f"  Task ID: {state.task_id}")
    print(f"  Intent: {state.intent.value}")
    print(f"  Command: {state.context['command']}")
    
    # Execute reasoning loop
    max_iterations = 5
    for i in range(max_iterations):
        print(f"\n--- Step: {state.current_step} ---")
        
        # Execute reasoning step
        action = orchestrator.execute_reasoning_step(state)
        print_action(action, state.iteration)
        
        # Check if we should continue
        if not action.should_continue:
            print(f"\n✓ Task completed after {state.iteration} iterations")
            break
        
        # Update state for next iteration
        state.current_step = action.action_type
        state.iteration += 1
        
        # Simulate some data updates based on step
        if action.action_type == "execute":
            # Simulate plan being created
            state.plan = action.action_data.get("plan", {})
        elif action.action_type == "observe":
            # Simulate execution results
            state.tool_results = action.action_data.get("results", [])
    else:
        print(f"\n⚠ Reached max iterations ({max_iterations})")


def example_error_handling():
    """
    Example: Error handling in reasoning steps
    
    Demonstrates:
    - Invalid state handling
    - Component error recovery
    - Graceful degradation
    """
    print_section("Example 2: Error Handling")
    
    orchestrator = AgentOrchestrator()
    
    # Test with invalid state (missing task_id)
    print("\nTest 1: Missing task_id")
    invalid_state = ReasoningState(
        task_id="",  # Invalid
        iteration=1,
        intent=Intent.TASK,
        current_step="plan",
        plan=None,
        tool_results=[],
        observations=[],
        context={},
        metadata={}
    )
    
    action = orchestrator.execute_reasoning_step(invalid_state)
    print(f"  Result: {action.action_type}")
    print(f"  Reason: {action.reason}")
    print(f"  Error: {action.action_data.get('error', 'None')}")
    
    # Test with unknown step
    print("\nTest 2: Unknown step")
    unknown_step_state = ReasoningState(
        task_id="task-002",
        iteration=1,
        intent=Intent.TASK,
        current_step="invalid_step",  # Unknown
        plan=None,
        tool_results=[],
        observations=[],
        context={},
        metadata={}
    )
    
    action = orchestrator.execute_reasoning_step(unknown_step_state)
    print(f"  Result: {action.action_type}")
    print(f"  Reason: {action.reason}")
    print(f"  Error: {action.action_data.get('error', 'None')}")


def example_state_management():
    """
    Example: State management across reasoning steps
    
    Demonstrates:
    - State updates between steps
    - Metadata tracking
    - Context preservation
    """
    print_section("Example 3: State Management")
    
    orchestrator = AgentOrchestrator()
    
    state = ReasoningState(
        task_id="task-003",
        iteration=1,
        intent=Intent.TASK,
        current_step="classify",
        plan=None,
        tool_results=[],
        observations=[],
        context={
            "command": "Analyze log files",
            "user_id": "user-123"
        },
        metadata={
            "start_time": datetime.utcnow().isoformat()
        }
    )
    
    print(f"\nInitial metadata: {state.metadata}")
    
    # Execute a few steps
    for step_name in ["classify", "plan", "execute"]:
        state.current_step = step_name
        action = orchestrator.execute_reasoning_step(state)
        
        print(f"\nAfter {step_name} step:")
        print(f"  Next action: {action.action_type}")
        print(f"  Metadata: {state.metadata}")
        
        # Update for next step
        state.current_step = action.action_type
        state.iteration += 1


def example_component_coordination():
    """
    Example: Component coordination with placeholders
    
    Demonstrates:
    - Planner coordination (placeholder)
    - Executor coordination (placeholder)
    - Observer coordination (placeholder)
    - Event emission
    """
    print_section("Example 4: Component Coordination")
    
    orchestrator = AgentOrchestrator()
    
    # Test plan step (Planner coordination)
    print("\nTest: Plan Step (Planner coordination)")
    plan_state = ReasoningState(
        task_id="task-004",
        iteration=1,
        intent=Intent.TASK,
        current_step="plan",
        plan=None,
        tool_results=[],
        observations=[],
        context={"command": "Generate report"},
        metadata={}
    )
    
    action = orchestrator.execute_reasoning_step(plan_state)
    print(f"  Action: {action.action_type}")
    print(f"  Plan created: {plan_state.plan is not None}")
    print(f"  Plan data: {plan_state.plan}")
    
    # Test execute step (Executor coordination)
    print("\nTest: Execute Step (Executor coordination)")
    execute_state = ReasoningState(
        task_id="task-005",
        iteration=2,
        intent=Intent.TASK,
        current_step="execute",
        plan={"steps": ["step1", "step2"], "goal": "test"},
        tool_results=[],
        observations=[],
        context={},
        metadata={}
    )
    
    action = orchestrator.execute_reasoning_step(execute_state)
    print(f"  Action: {action.action_type}")
    print(f"  Results stored: {len(execute_state.tool_results)}")
    
    # Test observe step (Observer coordination)
    print("\nTest: Observe Step (Observer coordination)")
    observe_state = ReasoningState(
        task_id="task-006",
        iteration=3,
        intent=Intent.TASK,
        current_step="observe",
        plan={"steps": []},
        tool_results=[{"tool": "test", "result": "success"}],
        observations=[],
        context={},
        metadata={}
    )
    
    action = orchestrator.execute_reasoning_step(observe_state)
    print(f"  Action: {action.action_type}")
    print(f"  Observations: {observe_state.observations}")


def example_reflection_integration():
    """
    Example: Reflection integration in reasoning loop
    
    Demonstrates:
    - Reflection triggering
    - Plan adjustment based on reflection
    - Continued reasoning after reflection
    """
    print_section("Example 5: Reflection Integration")
    
    orchestrator = AgentOrchestrator(
        enable_reflection=True,
        reflection_trigger_on_failure=True,
        reflection_trigger_interval=3
    )
    
    state = ReasoningState(
        task_id="task-007",
        iteration=3,  # At reflection interval
        intent=Intent.TASK,
        current_step="reason",
        plan={"steps": ["step1"]},
        tool_results=[{"status": "failed"}],  # Failure to trigger reflection
        observations=["Step 1 failed"],
        context={},
        metadata={}
    )
    
    print(f"\nState before reasoning:")
    print(f"  Iteration: {state.iteration}")
    print(f"  Tool results: {state.tool_results}")
    
    action = orchestrator.execute_reasoning_step(state)
    
    print(f"\nAction after reasoning:")
    print(f"  Action type: {action.action_type}")
    print(f"  Reason: {action.reason}")
    print(f"  Reflection triggered: {'last_reflection' in state.metadata}")
    
    if "last_reflection" in state.metadata:
        reflection = state.metadata["last_reflection"]
        print(f"  Errors detected: {reflection.get('errors_detected', [])}")
        print(f"  Adjustments needed: {reflection.get('adjustments_needed', [])}")


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("Enhanced Reasoning Step Execution Coordination Examples")
    print("=" * 60)
    
    example_full_reasoning_loop()
    example_error_handling()
    example_state_management()
    example_component_coordination()
    example_reflection_integration()
    
    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
