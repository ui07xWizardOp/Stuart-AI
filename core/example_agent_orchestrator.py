"""
Example: Agent Orchestrator Usage

Demonstrates how to use the Agent Orchestrator for intent classification,
reasoning step execution, and reflection.
"""

from core.agent_orchestrator import (
    AgentOrchestrator,
    Intent,
    ReasoningState,
    ReasoningAction,
    ReflectionResult
)
from observability import initialize_logging, initialize_tracing
from events import initialize_event_bus


def example_intent_classification():
    """Example: Classify user intents"""
    print("\n=== Intent Classification ===")
    
    orchestrator = AgentOrchestrator()
    
    commands = [
        "Create a report from the sales data",
        "Create workflow to backup files daily",
        "Remember that I prefer Python for scripting",
        "Search for documentation on REST APIs",
        "Run the data processing workflow",
        "Status of task abc-123"
    ]
    
    for command in commands:
        intent = orchestrator.classify_intent(command)
        print(f"Command: {command}")
        print(f"  Intent: {intent.value}\n")


def example_reasoning_loop():
    """Example: Execute reasoning loop steps"""
    print("\n=== Reasoning Loop Execution ===")
    
    orchestrator = AgentOrchestrator()
    
    # Initialize reasoning state
    state = ReasoningState(
        task_id="task-001",
        iteration=1,
        intent=Intent.TASK,
        current_step="classify"
    )
    
    print(f"Task ID: {state.task_id}")
    print(f"Initial step: {state.current_step}\n")
    
    # Simulate reasoning loop
    max_iterations = 5
    for i in range(max_iterations):
        print(f"Iteration {state.iteration}:")
        print(f"  Current step: {state.current_step}")
        
        # Execute reasoning step
        action = orchestrator.execute_reasoning_step(state)
        
        print(f"  Action: {action.action_type}")
        print(f"  Should continue: {action.should_continue}")
        print(f"  Reason: {action.reason}\n")
        
        if not action.should_continue:
            print("Task completed!")
            break
        
        # Update state for next iteration
        state.iteration += 1
        state.current_step = action.action_type
        
        # Simulate adding results based on action type
        if action.action_type == "execute":
            state.tool_results.append({
                "tool": "example_tool",
                "result": f"Result from iteration {state.iteration}"
            })
        elif action.action_type == "observe":
            state.observations.append(f"Observation from iteration {state.iteration}")


def example_reflection():
    """Example: Trigger reflection on reasoning state"""
    print("\n=== Reflection Step ===")
    
    orchestrator = AgentOrchestrator(
        enable_reflection=True,
        reflection_trigger_on_failure=True
    )
    
    # Create state with some execution history
    state = ReasoningState(
        task_id="task-002",
        iteration=3,
        intent=Intent.TASK,
        current_step="observe",
        plan={"steps": ["step1", "step2", "step3"], "total_steps": 3},
        tool_results=[
            {"tool": "file_reader", "status": "success"},
            {"tool": "data_processor", "status": "failed", "error": "Invalid format"}
        ],
        observations=["Read file successfully", "Processing failed"]
    )
    
    print(f"Task ID: {state.task_id}")
    print(f"Iteration: {state.iteration}")
    print(f"Tool results: {len(state.tool_results)}")
    print(f"Observations: {len(state.observations)}\n")
    
    # Trigger reflection
    reflection = orchestrator.trigger_reflection(state)
    
    print(f"Reflection ID: {reflection.reflection_id}")
    print(f"Timestamp: {reflection.timestamp}")
    print(f"Confidence score: {reflection.confidence_score}")
    print(f"Errors detected: {len(reflection.errors_detected)}")
    
    if reflection.errors_detected:
        print("\nErrors:")
        for error in reflection.errors_detected:
            print(f"  - {error}")
    
    if reflection.adjustments_needed:
        print("\nAdjustments needed:")
        for adjustment in reflection.adjustments_needed:
            print(f"  - {adjustment}")


def example_should_continue():
    """Example: Determine if reasoning should continue"""
    print("\n=== Should Continue Logic ===")
    
    orchestrator = AgentOrchestrator()
    
    # Test case 1: Plan in progress
    state1 = ReasoningState(
        task_id="task-003",
        iteration=2,
        intent=Intent.TASK,
        current_step="execute",
        plan={"total_steps": 3},
        tool_results=[{"result": "step1"}]
    )
    
    should_continue = orchestrator.should_continue(state1)
    print(f"Case 1 - Plan in progress:")
    print(f"  Completed: {len(state1.tool_results)}/{state1.plan['total_steps']}")
    print(f"  Should continue: {should_continue}\n")
    
    # Test case 2: Plan complete
    state2 = ReasoningState(
        task_id="task-004",
        iteration=3,
        intent=Intent.TASK,
        current_step="observe",
        plan={"total_steps": 2},
        tool_results=[{"result": "step1"}, {"result": "step2"}]
    )
    
    should_continue = orchestrator.should_continue(state2)
    print(f"Case 2 - Plan complete:")
    print(f"  Completed: {len(state2.tool_results)}/{state2.plan['total_steps']}")
    print(f"  Should continue: {should_continue}")


def example_with_observability():
    """Example: Orchestrator with full observability"""
    print("\n=== Orchestrator with Observability ===")
    
    # Initialize observability
    logger = initialize_logging(log_level="INFO")
    tracing = initialize_tracing(enable_tracing=True)
    event_bus = initialize_event_bus()
    
    orchestrator = AgentOrchestrator(
        enable_reflection=True,
        reflection_trigger_interval=3
    )
    
    # Execute a command
    command = "Analyze the log files and create a summary report"
    intent = orchestrator.classify_intent(command)
    
    print(f"Command: {command}")
    print(f"Intent: {intent.value}")
    
    # Create reasoning state
    state = ReasoningState(
        task_id="task-005",
        iteration=1,
        intent=intent,
        current_step="classify"
    )
    
    # Execute one reasoning step
    action = orchestrator.execute_reasoning_step(state)
    
    print(f"\nReasoning action:")
    print(f"  Type: {action.action_type}")
    print(f"  Should continue: {action.should_continue}")
    
    # Emit task event
    orchestrator.emit_task_event(
        event_type=EventType.TASK_STARTED,
        task_id=state.task_id,
        payload={
            "command": command,
            "intent": intent.value,
            "iteration": state.iteration
        }
    )
    
    print("\n✓ Task event emitted")


def example_reflection_triggers():
    """Example: Different reflection trigger scenarios"""
    print("\n=== Reflection Trigger Scenarios ===")
    
    # Scenario 1: Trigger on failure
    print("Scenario 1: Trigger on failure")
    orchestrator1 = AgentOrchestrator(
        enable_reflection=True,
        reflection_trigger_on_failure=True
    )
    
    state1 = ReasoningState(
        task_id="task-006",
        iteration=2,
        intent=Intent.TASK,
        current_step="observe",
        tool_results=[{"status": "failed", "error": "Connection timeout"}]
    )
    
    should_reflect = orchestrator1._should_trigger_reflection(state1)
    print(f"  Should trigger reflection: {should_reflect}\n")
    
    # Scenario 2: Trigger at interval
    print("Scenario 2: Trigger at interval (every 5 iterations)")
    orchestrator2 = AgentOrchestrator(
        enable_reflection=True,
        reflection_trigger_interval=5
    )
    
    for iteration in [1, 3, 5, 7, 10]:
        state2 = ReasoningState(
            task_id="task-007",
            iteration=iteration,
            intent=Intent.TASK,
            current_step="observe"
        )
        
        should_reflect = orchestrator2._should_trigger_reflection(state2)
        print(f"  Iteration {iteration}: {should_reflect}")
    
    # Scenario 3: Reflection disabled
    print("\nScenario 3: Reflection disabled")
    orchestrator3 = AgentOrchestrator(enable_reflection=False)
    
    state3 = ReasoningState(
        task_id="task-008",
        iteration=5,
        intent=Intent.TASK,
        current_step="observe",
        tool_results=[{"status": "failed"}]
    )
    
    should_reflect = orchestrator3._should_trigger_reflection(state3)
    print(f"  Should trigger reflection: {should_reflect}")


if __name__ == "__main__":
    print("=" * 60)
    print("Agent Orchestrator Examples")
    print("=" * 60)
    
    try:
        example_intent_classification()
        example_reasoning_loop()
        example_reflection()
        example_should_continue()
        example_with_observability()
        example_reflection_triggers()
        
        print("\n" + "=" * 60)
        print("✅ All examples completed successfully")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
