"""
Example: Agent Runtime Usage

Demonstrates how to use the Agent Runtime Controller.
"""

from core.agent_runtime import AgentRuntime, RuntimeState
from observability import initialize_logging, initialize_tracing
from events import initialize_event_bus
from database import get_db_connection


def example_basic_execution():
    """Example: Basic task execution"""
    print("\n=== Basic Task Execution ===")
    
    # Initialize runtime
    runtime = AgentRuntime(
        max_iterations=20,
        max_tool_calls=50,
        max_llm_calls=100,
        max_execution_time=300,
        enable_state_persistence=False  # Disable for example
    )
    
    # Execute a task
    result = runtime.execute_task(
        task_id="task-001",
        user_id="user-123",
        command="Analyze the sales data and create a report",
        metadata={"priority": "high"}
    )
    
    print(f"Status: {result['status']}")
    print(f"Task ID: {result['task_id']}")
    print(f"Budget used:")
    for key, value in result['budget_used'].items():
        print(f"  {key}: {value}")


def example_with_observability():
    """Example: Task execution with full observability"""
    print("\n=== Task Execution with Observability ===")
    
    # Initialize observability
    logger = initialize_logging(log_level="INFO")
    tracing = initialize_tracing(enable_tracing=True)
    
    # Initialize runtime
    runtime = AgentRuntime(
        max_iterations=10,
        enable_state_persistence=False
    )
    
    # Execute task
    result = runtime.execute_task(
        task_id="task-002",
        user_id="user-456",
        command="Generate a summary of recent events"
    )
    
    # Query traces
    spans = tracing.query_spans(operation_name="agent_runtime.execute_task", limit=5)
    print(f"\nTraces captured: {len(spans)}")
    for span in spans:
        print(f"  - {span.operation_name}: {span.duration_ms}ms")


def example_health_monitoring():
    """Example: Health status monitoring"""
    print("\n=== Health Status Monitoring ===")
    
    runtime = AgentRuntime(enable_state_persistence=False)
    
    # Check health before execution
    health = runtime.get_health_status()
    print("Health status (idle):")
    print(f"  Healthy: {health['healthy']}")
    print(f"  State: {health['state']}")
    print(f"  Current task: {health['current_task']}")
    
    # Execute a task
    result = runtime.execute_task(
        task_id="task-003",
        user_id="user-789",
        command="Process incoming data"
    )
    
    # Check health after execution
    health = runtime.get_health_status()
    print("\nHealth status (after execution):")
    print(f"  Healthy: {health['healthy']}")
    print(f"  State: {health['state']}")


def example_budget_limits():
    """Example: Budget limit enforcement"""
    print("\n=== Budget Limit Enforcement ===")
    
    # Create runtime with very low limits
    runtime = AgentRuntime(
        max_iterations=2,
        max_tool_calls=5,
        max_llm_calls=10,
        max_execution_time=30,
        enable_state_persistence=False
    )
    
    print("Runtime configured with low limits:")
    print(f"  Max iterations: {runtime.max_iterations}")
    print(f"  Max tool calls: {runtime.max_tool_calls}")
    print(f"  Max LLM calls: {runtime.max_llm_calls}")
    
    # Execute task
    result = runtime.execute_task(
        task_id="task-004",
        user_id="user-999",
        command="Complex analysis task"
    )
    
    print(f"\nTask completed: {result['status']}")
    print("Budget consumption:")
    budget = result['budget_used']
    print(f"  Iterations: {budget['iterations_used']}/{budget['max_iterations']}")
    print(f"  Tool calls: {budget['tool_calls_used']}/{budget['max_tool_calls']}")
    print(f"  LLM calls: {budget['llm_calls_used']}/{budget['max_llm_calls']}")


def example_task_cancellation():
    """Example: Task cancellation"""
    print("\n=== Task Cancellation ===")
    
    runtime = AgentRuntime(enable_state_persistence=False)
    
    # In a real scenario, you would cancel from another thread
    # For this example, we'll just demonstrate the API
    
    print("Starting task...")
    # runtime.execute_task(...) would be running in a thread
    
    # Simulate having a running task
    from core.agent_runtime import RuntimeContext, ReasoningBudget
    runtime.current_context = RuntimeContext(
        task_id="task-005",
        user_id="user-111",
        command="Long running task"
    )
    
    print("Cancelling task...")
    cancelled = runtime.cancel_task("task-005")
    
    if cancelled:
        print("? Task cancellation initiated")
        print(f"  Cancel flag: {runtime.cancel_requested}")
    else:
        print("? Task not found or already completed")


def example_graceful_shutdown():
    """Example: Graceful shutdown"""
    print("\n=== Graceful Shutdown ===")
    
    runtime = AgentRuntime(enable_state_persistence=False)
    
    print("Runtime running...")
    health = runtime.get_health_status()
    print(f"  Healthy: {health['healthy']}")
    print(f"  Shutting down: {health['shutting_down']}")
    
    print("\nInitiating graceful shutdown...")
    runtime.shutdown(wait_for_completion=True)
    
    health = runtime.get_health_status()
    print(f"  Healthy: {health['healthy']}")
    print(f"  Shutting down: {health['shutting_down']}")


if __name__ == "__main__":
    print("=" * 60)
    print("Agent Runtime Controller Examples")
    print("=" * 60)
    
    try:
        example_basic_execution()
        example_with_observability()
        example_health_monitoring()
        example_budget_limits()
        example_task_cancellation()
        example_graceful_shutdown()
        
        print("\n" + "=" * 60)
        print("? All examples completed successfully")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n? Error: {e}")
        import traceback
        traceback.print_exc()
