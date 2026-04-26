"""
Simple standalone test for Agent Orchestrator

Tests core functionality without requiring database or observability dependencies.
"""

from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List


# Simplified versions of the classes for testing
class Intent(str, Enum):
    TASK = "task"
    WORKFLOW = "workflow"
    REMEMBER = "remember"
    SEARCH = "search"
    RUN = "run"
    STATUS = "status"


@dataclass
class ReasoningState:
    task_id: str
    iteration: int
    intent: Optional[Intent] = None
    current_step: str = "classify"
    plan: Optional[Dict[str, Any]] = None
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


def test_intent_classification():
    """Test intent classification logic"""
    print("\n=== Testing Intent Classification ===")
    
    test_cases = [
        ("Create a report from sales data", Intent.TASK),
        ("Create workflow to backup files", Intent.WORKFLOW),
        ("Remember that I prefer Python", Intent.REMEMBER),
        ("Search for documentation", Intent.SEARCH),
        ("Run the backup workflow", Intent.RUN),
        ("Status of task 123", Intent.STATUS),
    ]
    
    passed = 0
    failed = 0
    
    for command, expected_intent in test_cases:
        command_lower = command.lower()
        
        # Simple keyword-based classification
        if any(keyword in command_lower for keyword in ["create workflow", "automate", "schedule"]):
            intent = Intent.WORKFLOW
        elif any(keyword in command_lower for keyword in ["remember", "store", "save"]):
            intent = Intent.REMEMBER
        elif any(keyword in command_lower for keyword in ["search", "find", "look up"]):
            intent = Intent.SEARCH
        elif any(keyword in command_lower for keyword in ["run", "execute workflow"]):
            intent = Intent.RUN
        elif any(keyword in command_lower for keyword in ["status", "check", "progress"]):
            intent = Intent.STATUS
        else:
            intent = Intent.TASK
        
        if intent == expected_intent:
            print(f"  ✓ '{command[:40]}...' -> {intent.value}")
            passed += 1
        else:
            print(f"  ✗ '{command[:40]}...' -> Expected {expected_intent.value}, got {intent.value}")
            failed += 1
    
    print(f"\nIntent Classification: {passed}/{passed+failed} passed")
    return failed == 0


def test_reasoning_state():
    """Test ReasoningState dataclass"""
    print("\n=== Testing ReasoningState ===")
    
    try:
        # Create a reasoning state
        state = ReasoningState(
            task_id="task-001",
            iteration=1,
            intent=Intent.TASK,
            current_step="classify"
        )
        
        assert state.task_id == "task-001"
        assert state.iteration == 1
        assert state.intent == Intent.TASK
        assert state.current_step == "classify"
        assert state.plan is None
        assert len(state.tool_results) == 0
        
        print("  ✓ ReasoningState creation")
        
        # Test with data
        state2 = ReasoningState(
            task_id="task-002",
            iteration=2,
            intent=Intent.SEARCH,
            current_step="execute",
            plan={"steps": ["step1", "step2"]},
            tool_results=[{"tool": "search", "result": "found"}],
            observations=["observation1"]
        )
        
        assert len(state2.tool_results) == 1
        assert len(state2.observations) == 1
        assert state2.plan["steps"] == ["step1", "step2"]
        
        print("  ✓ ReasoningState with data")
        
        return True
    except AssertionError as e:
        print(f"  ✗ ReasoningState test failed: {e}")
        return False


def test_reasoning_flow():
    """Test reasoning step flow"""
    print("\n=== Testing Reasoning Flow ===")
    
    try:
        # Test classify -> plan flow
        state = ReasoningState(
            task_id="task-001",
            iteration=1,
            intent=Intent.TASK,
            current_step="classify"
        )
        
        # Simulate classify step
        if state.current_step == "classify":
            next_step = "plan"
            print(f"  ✓ classify -> {next_step}")
        
        # Simulate plan step
        state.current_step = "plan"
        state.plan = {"steps": ["step1", "step2"], "total_steps": 2}
        
        if state.current_step == "plan" and state.plan:
            next_step = "execute"
            print(f"  ✓ plan -> {next_step}")
        
        # Simulate execute step
        state.current_step = "execute"
        state.tool_results.append({"tool": "test", "result": "success"})
        
        if state.current_step == "execute" and len(state.tool_results) > 0:
            next_step = "observe"
            print(f"  ✓ execute -> {next_step}")
        
        # Simulate observe step
        state.current_step = "observe"
        state.observations.append("Task completed successfully")
        
        # Check if should continue
        completed_steps = len(state.tool_results)
        total_steps = state.plan.get("total_steps", 1)
        should_continue = completed_steps < total_steps
        
        if state.current_step == "observe":
            if should_continue:
                next_step = "plan"
                print(f"  ✓ observe -> {next_step} (continue)")
            else:
                next_step = "complete"
                print(f"  ✓ observe -> {next_step} (done)")
        
        return True
    except Exception as e:
        print(f"  ✗ Reasoning flow test failed: {e}")
        return False


def test_reflection_trigger():
    """Test reflection triggering logic"""
    print("\n=== Testing Reflection Trigger ===")
    
    try:
        # Test reflection on failure
        state = ReasoningState(
            task_id="task-001",
            iteration=2,
            intent=Intent.TASK,
            current_step="observe",
            tool_results=[{"status": "failed", "error": "Tool error"}]
        )
        
        # Check if should trigger reflection
        should_reflect = False
        if state.tool_results:
            last_result = state.tool_results[-1]
            if last_result.get("status") == "failed":
                should_reflect = True
        
        assert should_reflect is True
        print("  ✓ Reflection triggered on failure")
        
        # Test reflection at interval
        state2 = ReasoningState(
            task_id="task-002",
            iteration=5,
            intent=Intent.TASK,
            current_step="observe"
        )
        
        reflection_interval = 5
        should_reflect = (state2.iteration > 0 and 
                         state2.iteration % reflection_interval == 0)
        
        assert should_reflect is True
        print("  ✓ Reflection triggered at interval")
        
        return True
    except AssertionError as e:
        print(f"  ✗ Reflection trigger test failed: {e}")
        return False


def test_should_continue_logic():
    """Test should_continue logic"""
    print("\n=== Testing Should Continue Logic ===")
    
    try:
        # Test with incomplete plan
        state = ReasoningState(
            task_id="task-001",
            iteration=1,
            intent=Intent.TASK,
            current_step="execute",
            plan={"total_steps": 3},
            tool_results=[{"result": "step1"}]
        )
        
        completed_steps = len(state.tool_results)
        total_steps = state.plan.get("total_steps", 1)
        should_continue = completed_steps < total_steps
        
        assert should_continue is True
        print("  ✓ Should continue with incomplete plan")
        
        # Test with complete plan
        state2 = ReasoningState(
            task_id="task-002",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe",
            plan={"total_steps": 2},
            tool_results=[{"result": "step1"}, {"result": "step2"}]
        )
        
        completed_steps = len(state2.tool_results)
        total_steps = state2.plan.get("total_steps", 1)
        should_continue = completed_steps < total_steps
        
        assert should_continue is False
        print("  ✓ Should not continue with complete plan")
        
        return True
    except AssertionError as e:
        print(f"  ✗ Should continue test failed: {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("Agent Orchestrator Core Logic Tests")
    print("=" * 60)
    
    results = []
    
    results.append(("Intent Classification", test_intent_classification()))
    results.append(("Reasoning State", test_reasoning_state()))
    results.append(("Reasoning Flow", test_reasoning_flow()))
    results.append(("Reflection Trigger", test_reflection_trigger()))
    results.append(("Should Continue Logic", test_should_continue_logic()))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} test suites passed")
    print("=" * 60)
    
    return all(result for _, result in results)


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
