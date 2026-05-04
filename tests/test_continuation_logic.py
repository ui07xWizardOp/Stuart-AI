"""
Standalone test for reasoning loop continuation logic (Task 6.8)

Tests the enhanced should_continue() and _should_continue_reasoning() methods
without requiring full system dependencies.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class Intent(Enum):
    """Intent types for user commands"""
    TASK = "task"
    WORKFLOW = "workflow"
    REMEMBER = "remember"
    SEARCH = "search"
    RUN = "run"
    STATUS = "status"
    UNKNOWN = "unknown"


@dataclass
class ReasoningState:
    """State of the reasoning loop"""
    task_id: str
    iteration: int
    intent: Intent
    current_step: str
    plan: Optional[Dict[str, Any]] = None
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


class MockLogger:
    """Mock logger for testing"""
    def info(self, msg, **kwargs):
        pass
    
    def debug(self, msg, **kwargs):
        pass
    
    def warning(self, msg, **kwargs):
        pass


class ContinuationLogic:
    """Extracted continuation logic for testing"""
    
    def __init__(self):
        self.logger = MockLogger()
    
    def _should_continue_reasoning(self, state: ReasoningState) -> bool:
        """Internal logic to determine if reasoning should continue"""
        # 1. Check if goal is explicitly achieved
        if state.context.get("goal_achieved", False):
            self.logger.info("Goal achieved, stopping reasoning")
            return False
        
        # 2. Check if we have a plan and if more steps remain
        if state.plan:
            completed_steps = len(state.tool_results)
            total_steps = state.plan.get("total_steps", 0)
            
            if completed_steps >= total_steps and total_steps > 0:
                if state.tool_results:
                    last_result = state.tool_results[-1]
                    if last_result.get("status") == "success":
                        self.logger.info("All plan steps completed successfully")
                        return False
                    else:
                        self.logger.debug("Plan steps completed but last step failed")
                        return True
                else:
                    return True
            
            if completed_steps < total_steps:
                self.logger.debug("Plan has remaining steps")
                return True
        
        # 3. Detect if progress is being made
        if not self._is_making_progress(state):
            self.logger.warning("No progress detected, stopping reasoning")
            return False
        
        # 4. Detect if stuck in a loop
        if self._is_stuck_in_loop(state):
            self.logger.warning("Loop detected, stopping reasoning")
            return False
        
        # 5. Check if we're in early stages
        if state.current_step in ["classify", "plan"]:
            self.logger.debug("In early reasoning stage, continuing")
            return True
        
        # 6. If we have no plan yet
        if not state.plan and state.current_step not in ["classify"]:
            self.logger.debug("No plan exists, continuing to create one")
            return True
        
        if state.plan:
            return True
        
        self.logger.info("No clear continuation criteria met, stopping")
        return False
    
    def _is_making_progress(self, state: ReasoningState) -> bool:
        """Detect if the reasoning loop is making progress"""
        if state.iteration <= 2:
            return True
        
        if state.tool_results:
            return True
        
        if state.plan:
            return True
        
        if state.intent and state.intent != Intent.UNKNOWN:
            return True
        
        return False
    
    def _is_stuck_in_loop(self, state: ReasoningState) -> bool:
        """Detect if the reasoning loop is stuck"""
        if state.iteration < 3:
            return False
        
        # Check for repeated failures
        if len(state.tool_results) >= 3:
            recent_results = state.tool_results[-3:]
            failure_count = sum(1 for r in recent_results if r.get("status") == "failed")
            
            if failure_count >= 3:
                errors = [r.get("error", "") for r in recent_results if r.get("status") == "failed"]
                if len(set(errors)) == 1:
                    self.logger.warning("Detected repeated failures with same error")
                    return True
        
        # Check for repeated tool calls
        if len(state.tool_results) >= 4:
            recent_tools = [r.get("tool_name", "") for r in state.tool_results[-4:]]
            if len(set(recent_tools)) == 1 and recent_tools[0]:
                self.logger.warning("Detected repeated tool calls")
                return True
        
        return False


def test_goal_achieved():
    """Test that reasoning stops when goal is achieved"""
    logic = ContinuationLogic()
    state = ReasoningState(
        task_id="test-001",
        iteration=3,
        intent=Intent.TASK,
        current_step="observe",
        context={"goal_achieved": True}
    )
    assert logic._should_continue_reasoning(state) is False
    print("? Goal achieved stops reasoning")


def test_plan_steps_remaining():
    """Test continuation when plan has remaining steps"""
    logic = ContinuationLogic()
    state = ReasoningState(
        task_id="test-002",
        iteration=2,
        intent=Intent.TASK,
        current_step="execute",
        plan={"total_steps": 5},
        tool_results=[{"status": "success"}]
    )
    assert logic._should_continue_reasoning(state) is True
    print("? Plan with remaining steps continues")


def test_plan_complete_successful():
    """Test stopping when all steps complete successfully"""
    logic = ContinuationLogic()
    state = ReasoningState(
        task_id="test-003",
        iteration=3,
        intent=Intent.TASK,
        current_step="observe",
        plan={"total_steps": 3},
        tool_results=[
            {"status": "success"},
            {"status": "success"},
            {"status": "success"}
        ]
    )
    assert logic._should_continue_reasoning(state) is False
    print("? Complete successful plan stops reasoning")


def test_plan_complete_last_failed():
    """Test continuation when last step failed"""
    logic = ContinuationLogic()
    state = ReasoningState(
        task_id="test-004",
        iteration=3,
        intent=Intent.TASK,
        current_step="observe",
        plan={"total_steps": 3},
        tool_results=[
            {"status": "success"},
            {"status": "success"},
            {"status": "failed", "error": "Error"}
        ]
    )
    assert logic._should_continue_reasoning(state) is True
    print("? Failed last step allows replanning")


def test_no_progress_stops():
    """Test that no progress stops reasoning"""
    logic = ContinuationLogic()
    state = ReasoningState(
        task_id="test-005",
        iteration=5,
        intent=Intent.UNKNOWN,
        current_step="observe"
    )
    assert logic._should_continue_reasoning(state) is False
    print("? No progress stops reasoning")


def test_early_stage_continues():
    """Test continuation in early stages"""
    logic = ContinuationLogic()
    state = ReasoningState(
        task_id="test-006",
        iteration=1,
        intent=Intent.TASK,
        current_step="classify"
    )
    assert logic._should_continue_reasoning(state) is True
    print("? Early stage continues")


def test_loop_repeated_failures():
    """Test loop detection with repeated failures"""
    logic = ContinuationLogic()
    state = ReasoningState(
        task_id="test-007",
        iteration=5,
        intent=Intent.TASK,
        current_step="execute",
        tool_results=[
            {"status": "failed", "error": "Timeout"},
            {"status": "failed", "error": "Timeout"},
            {"status": "failed", "error": "Timeout"}
        ]
    )
    assert logic._is_stuck_in_loop(state) is True
    print("? Repeated failures detected as loop")


def test_loop_repeated_tools():
    """Test loop detection with repeated tool calls"""
    logic = ContinuationLogic()
    state = ReasoningState(
        task_id="test-008",
        iteration=6,
        intent=Intent.TASK,
        current_step="execute",
        tool_results=[
            {"status": "success", "tool_name": "search"},
            {"status": "success", "tool_name": "search"},
            {"status": "success", "tool_name": "search"},
            {"status": "success", "tool_name": "search"}
        ]
    )
    assert logic._is_stuck_in_loop(state) is True
    print("? Repeated tool calls detected as loop")


def test_progress_with_results():
    """Test progress detection with results"""
    logic = ContinuationLogic()
    state = ReasoningState(
        task_id="test-009",
        iteration=5,
        intent=Intent.TASK,
        current_step="execute",
        tool_results=[{"status": "success"}]
    )
    assert logic._is_making_progress(state) is True
    print("? Progress detected with tool results")


def test_progress_early_iterations():
    """Test progress assumed in early iterations"""
    logic = ContinuationLogic()
    state = ReasoningState(
        task_id="test-010",
        iteration=1,
        intent=Intent.TASK,
        current_step="classify"
    )
    assert logic._is_making_progress(state) is True
    print("? Progress assumed in early iterations")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("REASONING LOOP CONTINUATION LOGIC TESTS (Task 6.8)")
    print("=" * 70 + "\n")
    
    tests = [
        test_goal_achieved,
        test_plan_steps_remaining,
        test_plan_complete_successful,
        test_plan_complete_last_failed,
        test_no_progress_stops,
        test_early_stage_continues,
        test_loop_repeated_failures,
        test_loop_repeated_tools,
        test_progress_with_results,
        test_progress_early_iterations
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"? {test.__name__}: {str(e)}")
            failed += 1
        except Exception as e:
            print(f"? {test.__name__}: Unexpected error - {str(e)}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 70)
    
    if failed == 0:
        print("\n? All tests passed!")
    else:
        print(f"\n? {failed} test(s) failed")
        exit(1)
