"""
Tests for Agent Runtime Controller
"""

import time
import pytest
from core.agent_runtime import AgentRuntime, RuntimeState, ReasoningBudget

class MockOrchestrator:
    def __init__(self, answer="mock answer", is_final=True, error=None, tool_call=None):
        self.toolset_distributor = None
        self.executor = type('obj', (object,), {'registry': type('obj', (object,), {'get_all_tools': lambda *a, **kw: []})()})()
        self.plan_library = None
        self.answer = answer
        self.is_final = is_final
        self.error = error
        self.tool_call = tool_call

    def run_reasoning_step(self, **kwargs):
        class ReasoningStepResult:
            def __init__(self, answer, is_final, error, tool_call):
                self.answer = answer
                self.is_final = is_final
                self.error = error
                self.tool_call = tool_call
                self.observation = None
        return ReasoningStepResult(self.answer, self.is_final, self.error, self.tool_call)


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


def test_task_execution():
    """Test standard task execution"""
    print("\n=== Testing Task Execution ===")
    
    runtime = AgentRuntime(
        max_iterations=5,
        enable_state_persistence=False
    )
    runtime.orchestrator = MockOrchestrator(answer="task completed successfully", is_final=True)
    
    result = runtime.execute_task(
        task_id="test-task-001",
        user_id="test-user",
        command="execute command"
    )
    
    assert result["status"] == "completed"
    assert result["result"] == "task completed successfully"
    print("? Task execution works correctly")


def test_task_cancellation():
    """Test task cancellation"""
    print("\n=== Testing Task Cancellation ===")
    
    runtime = AgentRuntime(
        max_iterations=100,
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
    
    # We assign an orchestrator that is not final, so it exhausts the budget
    runtime.orchestrator = MockOrchestrator(is_final=False)
    
    result = runtime.execute_task(
        task_id="test-task-003",
        user_id="test-user",
        command="test command"
    )
    
    assert result["status"] == "failed"
    assert "budget exhausted" in result["error"].lower()
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
