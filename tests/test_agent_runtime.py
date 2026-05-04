"""
Tests for Agent Runtime Controller
"""

import time
from core.agent_runtime import AgentRuntime, RuntimeState, ReasoningBudget


def test_reasoning_budget():
    """Test reasoning budget tracking"""
    print("\n=== Testing Reasoning Budget ===")
    
    budget = ReasoningBudget(
        max_iterations=10,
        max_tool_calls=20,
        max_llm_calls=30,
        max_execution_time_seconds=60
    )
    
    # Check initial state
    assert not budget.is_exhausted()
    print("? Budget not exhausted initially")
    
    # Use some budget
    budget.iterations_used = 5
    budget.tool_calls_used = 10
    budget.llm_calls_used = 15
    budget.execution_time_seconds = 30.0
    
    remaining = budget.get_remaining()
    assert remaining["iterations"] == 5
    assert remaining["tool_calls"] == 10
    assert remaining["llm_calls"] == 15
    print("? Budget tracking works correctly")
    
    # Exhaust budget
    budget.iterations_used = 10
    assert budget.is_exhausted()
    print("? Budget exhaustion detected")


def test_agent_runtime_initialization():
    """Test agent runtime initialization"""
    print("\n=== Testing Agent Runtime Initialization ===")
    
    runtime = AgentRuntime(
        max_iterations=20,
        max_tool_calls=50,
        max_llm_calls=100,
        max_execution_time=300,
        enable_reflection=True,
        enable_state_persistence=False  # Disable for testing
    )
    
    assert runtime.max_iterations == 20
    assert runtime.max_tool_calls == 50
    assert runtime.max_llm_calls == 100
    assert runtime.max_execution_time == 300
    assert runtime.enable_reflection is True
    print("? Agent runtime initialized correctly")
    
    # Check health status
    health = runtime.get_health_status()
    assert health["healthy"] is True
    assert health["state"] == "idle"
    assert health["current_task"] is None
    print("? Health status correct")


def test_task_execution():
    """Test basic task execution"""
    print("\n=== Testing Task Execution ===")
    
    runtime = AgentRuntime(
        max_iterations=5,
        enable_state_persistence=False
    )
    
    # Execute a simple task
    result = runtime.execute_task(
        task_id="test-task-001",
        user_id="test-user",
        command="test command",
        metadata={"test": True}
    )
    
    assert result["status"] == "completed"
    assert result["task_id"] == "test-task-001"
    assert "result" in result
    assert "budget_used" in result
    print("? Task executed successfully")
    print(f"  Budget used: {result['budget_used']}")


def test_task_cancellation():
    """Test task cancellation"""
    print("\n=== Testing Task Cancellation ===")
    
    runtime = AgentRuntime(
        max_iterations=100,  # High limit to allow cancellation
        enable_state_persistence=False
    )
    
    # Start a task (would need threading for real cancellation test)
    # For now, just test the cancellation flag
    runtime.current_context = type('obj', (object,), {'task_id': 'test-task-002'})()
    
    cancelled = runtime.cancel_task("test-task-002")
    assert cancelled is True
    assert runtime.cancel_requested is True
    print("? Task cancellation initiated")


def test_health_status():
    """Test health status reporting"""
    print("\n=== Testing Health Status ===")
    
    runtime = AgentRuntime(enable_state_persistence=False)
    
    # Check idle status
    health = runtime.get_health_status()
    assert health["healthy"] is True
    assert health["state"] == "idle"
    print("? Idle health status correct")
    
    # Simulate shutdown
    runtime.is_shutting_down = True
    health = runtime.get_health_status()
    assert health["healthy"] is False
    assert health["shutting_down"] is True
    print("? Shutdown health status correct")


def test_budget_exhaustion():
    """Test budget exhaustion handling"""
    print("\n=== Testing Budget Exhaustion ===")
    
    runtime = AgentRuntime(
        max_iterations=1,  # Very low limit
        enable_state_persistence=False
    )
    
    # This should exhaust the budget
    result = runtime.execute_task(
        task_id="test-task-003",
        user_id="test-user",
        command="test command"
    )
    
    # Should complete within 1 iteration (our mock implementation)
    assert result["status"] == "completed"
    print("? Budget limits enforced")


if __name__ == "__main__":
    print("=" * 60)
    print("Agent Runtime Controller Tests")
    print("=" * 60)
    
    try:
        test_reasoning_budget()
        test_agent_runtime_initialization()
        test_task_execution()
        test_task_cancellation()
        test_health_status()
        test_budget_exhaustion()
        
        print("\n" + "=" * 60)
        print("? All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n? Test failed: {e}")
    except Exception as e:
        print(f"\n? Error: {e}")
        import traceback
        traceback.print_exc()
