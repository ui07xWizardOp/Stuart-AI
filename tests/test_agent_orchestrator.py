"""
Unit tests for Agent Orchestrator

Tests intent classification, reasoning step execution, reflection,
and event emission.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from core.agent_orchestrator import (
    AgentOrchestrator,
    Intent,
    IntentClassificationResult,
    ReasoningState,
    ReasoningAction,
    ReflectionResult
)


class TestIntentClassification:
    """Test intent classification from natural language commands"""
    
    def test_classify_task_intent(self):
        """Test classification of task commands"""
        orchestrator = AgentOrchestrator()
        
        commands = [
            "Create a report from sales data",
            "Analyze the logs and find errors",
            "Generate a summary of recent events"
        ]
        
        for command in commands:
            result = orchestrator.classify_intent(command)
            assert isinstance(result, IntentClassificationResult)
            assert result.intent == Intent.TASK
            assert 0.0 <= result.confidence <= 1.0
            assert result.reasoning is not None
    
    def test_classify_workflow_intent(self):
        """Test classification of workflow commands"""
        orchestrator = AgentOrchestrator()
        
        commands = [
            "Create workflow to backup files daily",
            "Automate the data processing pipeline",
            "Schedule a report generation every Monday"
        ]
        
        for command in commands:
            result = orchestrator.classify_intent(command)
            assert isinstance(result, IntentClassificationResult)
            assert result.intent == Intent.WORKFLOW
            assert result.confidence > 0.5
    
    def test_classify_remember_intent(self):
        """Test classification of memory commands"""
        orchestrator = AgentOrchestrator()
        
        commands = [
            "Remember that I prefer Python",
            "Store this information for later",
            "Note that the API key is in the config"
        ]
        
        for command in commands:
            result = orchestrator.classify_intent(command)
            assert isinstance(result, IntentClassificationResult)
            assert result.intent == Intent.REMEMBER
            assert result.confidence > 0.5
    
    def test_classify_search_intent(self):
        """Test classification of search commands"""
        orchestrator = AgentOrchestrator()
        
        commands = [
            "Search for documentation on APIs",
            "Find information about machine learning",
            "Look up the latest news on AI"
        ]
        
        for command in commands:
            result = orchestrator.classify_intent(command)
            assert isinstance(result, IntentClassificationResult)
            assert result.intent == Intent.SEARCH
            assert result.confidence > 0.5
    
    def test_classify_run_intent(self):
        """Test classification of run commands"""
        orchestrator = AgentOrchestrator()
        
        commands = [
            "Run the backup workflow",
            "Execute workflow named daily-report",
            "Start workflow for data processing"
        ]
        
        for command in commands:
            result = orchestrator.classify_intent(command)
            assert isinstance(result, IntentClassificationResult)
            assert result.intent == Intent.RUN
            assert result.confidence > 0.5
    
    def test_classify_status_intent(self):
        """Test classification of status commands"""
        orchestrator = AgentOrchestrator()
        
        commands = [
            "Status of task 123",
            "Check the progress of my workflow",
            "What's happening with the report generation?"
        ]
        
        for command in commands:
            result = orchestrator.classify_intent(command)
            assert isinstance(result, IntentClassificationResult)
            assert result.intent == Intent.STATUS
            assert result.confidence > 0.5
    
    def test_classification_result_structure(self):
        """Test that classification result has all required fields"""
        orchestrator = AgentOrchestrator()
        
        result = orchestrator.classify_intent("Create a report")
        
        assert hasattr(result, 'intent')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'reasoning')
        assert hasattr(result, 'alternatives')
        assert isinstance(result.alternatives, list)
    
    def test_classification_confidence_range(self):
        """Test that confidence scores are in valid range"""
        orchestrator = AgentOrchestrator()
        
        commands = [
            "Create a report",
            "Remember my preference",
            "Search for docs",
            "Run workflow",
            "Check status"
        ]
        
        for command in commands:
            result = orchestrator.classify_intent(command)
            assert 0.0 <= result.confidence <= 1.0, f"Confidence {result.confidence} out of range for: {command}"
    
    def test_classification_alternatives(self):
        """Test that alternatives are provided"""
        orchestrator = AgentOrchestrator()
        
        result = orchestrator.classify_intent("Create a report")
        
        # Should have some alternatives
        assert len(result.alternatives) > 0
        
        # Each alternative should be a tuple of (Intent, float)
        for alt_intent, alt_score in result.alternatives:
            assert isinstance(alt_intent, Intent)
            assert isinstance(alt_score, float)
            assert 0.0 <= alt_score <= 1.0
    
    def test_classification_to_dict(self):
        """Test converting classification result to dictionary"""
        orchestrator = AgentOrchestrator()
        
        result = orchestrator.classify_intent("Search for information")
        result_dict = result.to_dict()
        
        assert "intent" in result_dict
        assert "confidence" in result_dict
        assert "reasoning" in result_dict
        assert "alternatives" in result_dict
        assert isinstance(result_dict["alternatives"], list)


class TestReasoningState:
    """Test ReasoningState dataclass"""
    
    def test_create_reasoning_state(self):
        """Test creating a reasoning state"""
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
        assert len(state.observations) == 0
    
    def test_reasoning_state_to_dict(self):
        """Test converting reasoning state to dictionary"""
        state = ReasoningState(
            task_id="task-002",
            iteration=2,
            intent=Intent.SEARCH,
            current_step="execute",
            plan={"steps": ["step1", "step2"]},
            tool_results=[{"tool": "search", "result": "found"}],
            observations=["observation1"]
        )
        
        state_dict = state.to_dict()
        
        assert state_dict["task_id"] == "task-002"
        assert state_dict["iteration"] == 2
        assert state_dict["intent"] == "search"
        assert state_dict["current_step"] == "execute"
        assert state_dict["plan"] == {"steps": ["step1", "step2"]}
        assert len(state_dict["tool_results"]) == 1
        assert len(state_dict["observations"]) == 1


class TestReasoningAction:
    """Test ReasoningAction dataclass"""
    
    def test_create_reasoning_action(self):
        """Test creating a reasoning action"""
        action = ReasoningAction(
            action_type="plan",
            action_data={"intent": "task"},
            should_continue=True,
            reason="Intent classified"
        )
        
        assert action.action_type == "plan"
        assert action.action_data == {"intent": "task"}
        assert action.should_continue is True
        assert action.reason == "Intent classified"
    
    def test_reasoning_action_to_dict(self):
        """Test converting reasoning action to dictionary"""
        action = ReasoningAction(
            action_type="execute",
            action_data={"plan": {"steps": []}},
            should_continue=True
        )
        
        action_dict = action.to_dict()
        
        assert action_dict["action_type"] == "execute"
        assert "action_data" in action_dict
        assert action_dict["should_continue"] is True


class TestReflectionResult:
    """Test ReflectionResult dataclass"""
    
    def test_create_reflection_result(self):
        """Test creating a reflection result"""
        result = ReflectionResult(
            reflection_id="ref-001",
            timestamp=datetime.utcnow(),
            errors_detected=["error1"],
            adjustments_needed=["adjustment1"],
            confidence_score=0.8
        )
        
        assert result.reflection_id == "ref-001"
        assert len(result.errors_detected) == 1
        assert len(result.adjustments_needed) == 1
        assert result.confidence_score == 0.8
    
    def test_reflection_result_to_dict(self):
        """Test converting reflection result to dictionary"""
        timestamp = datetime.utcnow()
        result = ReflectionResult(
            reflection_id="ref-002",
            timestamp=timestamp,
            errors_detected=["error1", "error2"],
            adjustments_needed=["adjustment1"]
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["reflection_id"] == "ref-002"
        assert isinstance(result_dict["timestamp"], str)
        assert len(result_dict["errors_detected"]) == 2
        assert len(result_dict["adjustments_needed"]) == 1


class TestAgentOrchestrator:
    """Test AgentOrchestrator class"""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization"""
        orchestrator = AgentOrchestrator(
            enable_reflection=True,
            reflection_trigger_on_failure=True,
            reflection_trigger_interval=5
        )
        
        assert orchestrator.enable_reflection is True
        assert orchestrator.reflection_trigger_on_failure is True
        assert orchestrator.reflection_trigger_interval == 5
    
    def test_execute_reasoning_step_classify(self):
        """Test reasoning step execution for classify step"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-001",
            iteration=1,
            intent=Intent.TASK,
            current_step="classify"
        )
        
        action = orchestrator.execute_reasoning_step(state)
        
        assert action.action_type == "plan"
        assert action.should_continue is True
    
    def test_execute_reasoning_step_plan(self):
        """Test reasoning step execution for plan step"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-002",
            iteration=1,
            intent=Intent.TASK,
            current_step="plan",
            plan={"steps": ["step1"]}
        )
        
        action = orchestrator.execute_reasoning_step(state)
        
        assert action.action_type == "execute"
        assert action.should_continue is True
    
    def test_execute_reasoning_step_execute(self):
        """Test reasoning step execution for execute step"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-003",
            iteration=1,
            intent=Intent.TASK,
            current_step="execute",
            tool_results=[{"tool": "test", "result": "success"}]
        )
        
        action = orchestrator.execute_reasoning_step(state)
        
        assert action.action_type == "observe"
        assert action.should_continue is True
    
    def test_trigger_reflection(self):
        """Test triggering reflection step"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-004",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe"
        )
        
        reflection = orchestrator.trigger_reflection(state)
        
        assert reflection.reflection_id is not None
        assert reflection.timestamp is not None
        assert isinstance(reflection.errors_detected, list)
        assert isinstance(reflection.adjustments_needed, list)
        assert 0.0 <= reflection.confidence_score <= 1.0
    
    def test_should_continue_with_plan(self):
        """Test should_continue with active plan"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-005",
            iteration=1,
            intent=Intent.TASK,
            current_step="execute",
            plan={"total_steps": 3},
            tool_results=[{"result": "step1"}]
        )
        
        should_continue = orchestrator.should_continue(state)
        
        assert should_continue is True
    
    def test_should_continue_plan_complete(self):
        """Test should_continue when plan is complete"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-006",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe",
            plan={"total_steps": 2},
            tool_results=[{"result": "step1"}, {"result": "step2"}]
        )
        
        should_continue = orchestrator.should_continue(state)
        
        assert should_continue is False
    
    def test_reflection_trigger_on_failure(self):
        """Test reflection triggering on failure"""
        orchestrator = AgentOrchestrator(
            enable_reflection=True,
            reflection_trigger_on_failure=True
        )
        
        state = ReasoningState(
            task_id="task-007",
            iteration=2,
            intent=Intent.TASK,
            current_step="observe",
            tool_results=[{"status": "failed", "error": "Tool error"}]
        )
        
        should_reflect = orchestrator._should_trigger_reflection(state)
        
        assert should_reflect is True
    
    def test_reflection_trigger_at_interval(self):
        """Test reflection triggering at intervals"""
        orchestrator = AgentOrchestrator(
            enable_reflection=True,
            reflection_trigger_interval=5
        )
        
        state = ReasoningState(
            task_id="task-008",
            iteration=5,
            intent=Intent.TASK,
            current_step="observe"
        )
        
        should_reflect = orchestrator._should_trigger_reflection(state)
        
        assert should_reflect is True
    
    def test_reflection_disabled(self):
        """Test that reflection doesn't trigger when disabled"""
        orchestrator = AgentOrchestrator(enable_reflection=False)
        
        state = ReasoningState(
            task_id="task-009",
            iteration=5,
            intent=Intent.TASK,
            current_step="observe",
            tool_results=[{"status": "failed"}]
        )
        
        should_reflect = orchestrator._should_trigger_reflection(state)
        
        assert should_reflect is False
    
    def test_reflection_no_progress_detection(self):
        """Test reflection detects no progress pattern"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-010",
            iteration=5,
            intent=Intent.TASK,
            current_step="observe",
            tool_results=[]  # No tool execution
        )
        
        reflection = orchestrator.trigger_reflection(state)
        
        assert len(reflection.errors_detected) > 0
        assert any("No tool execution" in error for error in reflection.errors_detected)
        assert reflection.confidence_score < 1.0
        assert reflection.plan_modifications is not None
        assert reflection.plan_modifications.get("add_tool_execution") is True
    
    def test_reflection_repeated_tool_failures(self):
        """Test reflection detects repeated tool failures"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-011",
            iteration=4,
            intent=Intent.TASK,
            current_step="observe",
            tool_results=[
                {"tool_name": "file_reader", "status": "failed"},
                {"tool_name": "file_reader", "status": "failed"},
                {"tool_name": "file_reader", "status": "failed"}
            ]
        )
        
        reflection = orchestrator.trigger_reflection(state)
        
        assert len(reflection.errors_detected) > 0
        assert any("file_reader" in error for error in reflection.errors_detected)
        assert reflection.confidence_score < 0.5
        assert reflection.plan_modifications is not None
        assert "file_reader" in reflection.plan_modifications.get("replace_failing_tools", [])
    
    def test_reflection_infinite_loop_detection(self):
        """Test reflection detects infinite loop pattern"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-012",
            iteration=7,
            intent=Intent.TASK,
            current_step="observe",
            tool_results=[
                {"tool_name": "search", "status": "success"},
                {"tool_name": "fetch", "status": "success"},
                {"tool_name": "search", "status": "success"},
                {"tool_name": "fetch", "status": "success"},
                {"tool_name": "search", "status": "success"}
            ]
        )
        
        reflection = orchestrator.trigger_reflection(state)
        
        assert len(reflection.errors_detected) > 0
        assert any("loop" in error.lower() for error in reflection.errors_detected)
        assert reflection.confidence_score < 0.5
        assert reflection.plan_modifications is not None
        assert reflection.plan_modifications.get("break_loop") is True
    
    def test_reflection_observation_error_detection(self):
        """Test reflection detects errors in observations"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-013",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe",
            observations=[
                "Attempting to read file",
                "File not found error occurred",
                "Failed to complete operation"
            ]
        )
        
        reflection = orchestrator.trigger_reflection(state)
        
        assert len(reflection.errors_detected) > 0
        assert any("observation" in error.lower() for error in reflection.errors_detected)
        assert reflection.confidence_score < 1.0
    
    def test_reflection_stalled_progress_detection(self):
        """Test reflection detects stalled progress"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-014",
            iteration=5,
            intent=Intent.TASK,
            current_step="observe",
            observations=[
                "No progress made",
                "Waiting for response",
                "No progress detected",
                "Still waiting"
            ]
        )
        
        reflection = orchestrator.trigger_reflection(state)
        
        assert len(reflection.errors_detected) > 0
        assert any("stalled" in error.lower() for error in reflection.errors_detected)
        assert reflection.plan_modifications is not None
        assert reflection.plan_modifications.get("strategy_change_needed") is True
    
    def test_reflection_plan_not_started(self):
        """Test reflection detects plan that hasn't started"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-015",
            iteration=5,
            intent=Intent.TASK,
            current_step="observe",
            plan={"steps": ["step1", "step2", "step3"]},
            tool_results=[]
        )
        
        reflection = orchestrator.trigger_reflection(state)
        
        assert len(reflection.errors_detected) > 0
        assert any("no steps completed" in error.lower() for error in reflection.errors_detected)
        assert reflection.plan_modifications is not None
        assert reflection.plan_modifications.get("simplify_plan") is True
    
    def test_reflection_complex_plan_detection(self):
        """Test reflection detects overly complex plans"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-016",
            iteration=2,
            intent=Intent.TASK,
            current_step="observe",
            plan={"steps": [f"step{i}" for i in range(15)]}
        )
        
        reflection = orchestrator.trigger_reflection(state)
        
        assert len(reflection.adjustments_needed) > 0
        assert any("breaking" in adj.lower() for adj in reflection.adjustments_needed)
        assert reflection.plan_modifications is not None
        assert reflection.plan_modifications.get("split_plan") is True
    
    def test_reflection_high_iteration_count(self):
        """Test reflection detects high iteration count"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-017",
            iteration=10,
            intent=Intent.TASK,
            current_step="observe"
        )
        
        reflection = orchestrator.trigger_reflection(state)
        
        assert len(reflection.errors_detected) > 0
        assert any("iteration" in error.lower() for error in reflection.errors_detected)
        assert reflection.plan_modifications is not None
        assert reflection.plan_modifications.get("request_user_input") is True
    
    def test_reflection_success_rate_tracking(self):
        """Test reflection tracks success rate"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        # High success rate
        state_success = ReasoningState(
            task_id="task-018",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe",
            tool_results=[
                {"status": "success"},
                {"status": "success"},
                {"status": "success"},
                {"status": "failed"}
            ]
        )
        
        reflection_success = orchestrator.trigger_reflection(state_success)
        assert reflection_success.confidence_score >= 0.8
        
        # Low success rate
        state_failure = ReasoningState(
            task_id="task-019",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe",
            tool_results=[
                {"status": "failed"},
                {"status": "failed"},
                {"status": "failed"},
                {"status": "success"}
            ]
        )
        
        reflection_failure = orchestrator.trigger_reflection(state_failure)
        assert reflection_failure.confidence_score < 0.5
        assert any("success rate" in error.lower() for error in reflection_failure.errors_detected)
    
    def test_reflection_history_tracking(self):
        """Test reflection history is stored in state metadata"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-020",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe",
            tool_results=[{"status": "failed"}]
        )
        
        # First reflection
        reflection1 = orchestrator.trigger_reflection(state)
        assert "reflection_history" in state.metadata
        assert len(state.metadata["reflection_history"]) == 1
        assert state.metadata["reflection_history"][0]["reflection_id"] == reflection1.reflection_id
        
        # Second reflection
        state.iteration = 5
        reflection2 = orchestrator.trigger_reflection(state)
        assert len(state.metadata["reflection_history"]) == 2
        assert state.metadata["reflection_history"][1]["reflection_id"] == reflection2.reflection_id
    
    def test_reflection_event_emission(self):
        """Test reflection emits event to event bus"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-021",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe"
        )
        
        # Trigger reflection
        reflection = orchestrator.trigger_reflection(state)
        
        # Event should be published (we can't easily verify without mocking,
        # but we can verify the method completes without error)
        assert reflection.reflection_id is not None
    
    def test_reflection_no_issues_detected(self):
        """Test reflection when no issues are detected"""
        orchestrator = AgentOrchestrator(enable_reflection=True)
        
        state = ReasoningState(
            task_id="task-022",
            iteration=2,
            intent=Intent.TASK,
            current_step="observe",
            tool_results=[
                {"status": "success"},
                {"status": "success"}
            ],
            observations=["Operation completed successfully"]
        )
        
        reflection = orchestrator.trigger_reflection(state)
        
        assert reflection.confidence_score >= 0.8
        assert "No significant issues" in reflection.reasoning or "Good progress" in reflection.reasoning


def run_tests():
    """Run all tests"""
    print("=" * 60)
    print("Running Agent Orchestrator Tests")
    print("=" * 60)
    
    test_classes = [
        TestIntentClassification(),
        TestReasoningState(),
        TestReasoningAction(),
        TestReflectionResult(),
        TestAgentOrchestrator()
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        print(f"\n{class_name}:")
        
        # Get all test methods
        test_methods = [method for method in dir(test_class) if method.startswith("test_")]
        
        for method_name in test_methods:
            total_tests += 1
            try:
                method = getattr(test_class, method_name)
                method()
                print(f"  ? {method_name}")
                passed_tests += 1
            except AssertionError as e:
                print(f"  ? {method_name}: {e}")
                failed_tests += 1
            except Exception as e:
                print(f"  ? {method_name}: {type(e).__name__}: {e}")
                failed_tests += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed_tests}/{total_tests} passed, {failed_tests} failed")
    print("=" * 60)
    
    return failed_tests == 0


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)


class TestReasoningLoopContinuation:
    """Test reasoning loop continuation logic (Task 6.8)"""
    
    def test_goal_achieved_stops_reasoning(self):
        """Test that reasoning stops when goal is achieved"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-goal-001",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe",
            plan={"total_steps": 5},
            tool_results=[{"status": "success"}],
            context={"goal_achieved": True}
        )
        
        should_continue = orchestrator._should_continue_reasoning(state)
        
        assert should_continue is False, "Should stop when goal is achieved"
    
    def test_plan_steps_remaining(self):
        """Test continuation when plan has remaining steps"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-steps-001",
            iteration=2,
            intent=Intent.TASK,
            current_step="execute",
            plan={"total_steps": 5},
            tool_results=[
                {"status": "success", "tool_name": "tool1"},
                {"status": "success", "tool_name": "tool2"}
            ]
        )
        
        should_continue = orchestrator._should_continue_reasoning(state)
        
        assert should_continue is True, "Should continue with remaining steps"
    
    def test_plan_complete_successful(self):
        """Test stopping when all plan steps complete successfully"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-complete-001",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe",
            plan={"total_steps": 3},
            tool_results=[
                {"status": "success", "tool_name": "tool1"},
                {"status": "success", "tool_name": "tool2"},
                {"status": "success", "tool_name": "tool3"}
            ]
        )
        
        should_continue = orchestrator._should_continue_reasoning(state)
        
        assert should_continue is False, "Should stop when all steps complete successfully"
    
    def test_plan_complete_last_failed(self):
        """Test continuation when last step failed (may need replanning)"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-failed-001",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe",
            plan={"total_steps": 3},
            tool_results=[
                {"status": "success", "tool_name": "tool1"},
                {"status": "success", "tool_name": "tool2"},
                {"status": "failed", "tool_name": "tool3", "error": "Tool error"}
            ]
        )
        
        should_continue = orchestrator._should_continue_reasoning(state)
        
        assert should_continue is True, "Should continue to allow replanning after failure"
    
    def test_no_progress_stops_reasoning(self):
        """Test that reasoning stops when no progress is detected"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-noprogress-001",
            iteration=5,
            intent=Intent.UNKNOWN,
            current_step="observe",
            plan=None,
            tool_results=[]
        )
        
        should_continue = orchestrator._should_continue_reasoning(state)
        
        assert should_continue is False, "Should stop when no progress is made"
    
    def test_early_stage_continues(self):
        """Test continuation in early reasoning stages"""
        orchestrator = AgentOrchestrator()
        
        # Test classify stage
        state_classify = ReasoningState(
            task_id="task-early-001",
            iteration=1,
            intent=Intent.TASK,
            current_step="classify"
        )
        
        should_continue = orchestrator._should_continue_reasoning(state_classify)
        assert should_continue is True, "Should continue in classify stage"
        
        # Test plan stage
        state_plan = ReasoningState(
            task_id="task-early-002",
            iteration=1,
            intent=Intent.TASK,
            current_step="plan"
        )
        
        should_continue = orchestrator._should_continue_reasoning(state_plan)
        assert should_continue is True, "Should continue in plan stage"
    
    def test_no_plan_continues_to_create_one(self):
        """Test continuation when no plan exists yet"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-noplan-001",
            iteration=2,
            intent=Intent.TASK,
            current_step="execute",
            plan=None
        )
        
        should_continue = orchestrator._should_continue_reasoning(state)
        
        assert should_continue is True, "Should continue to create a plan"
    
    def test_is_making_progress_early_iterations(self):
        """Test progress detection in early iterations"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-progress-001",
            iteration=1,
            intent=Intent.TASK,
            current_step="classify"
        )
        
        is_progressing = orchestrator._is_making_progress(state)
        
        assert is_progressing is True, "Should assume progress in early iterations"
    
    def test_is_making_progress_with_results(self):
        """Test progress detection with tool results"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-progress-002",
            iteration=5,
            intent=Intent.TASK,
            current_step="execute",
            tool_results=[{"status": "success"}]
        )
        
        is_progressing = orchestrator._is_making_progress(state)
        
        assert is_progressing is True, "Should detect progress with tool results"
    
    def test_is_making_progress_with_plan(self):
        """Test progress detection with plan created"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-progress-003",
            iteration=5,
            intent=Intent.TASK,
            current_step="execute",
            plan={"total_steps": 3}
        )
        
        is_progressing = orchestrator._is_making_progress(state)
        
        assert is_progressing is True, "Should detect progress with plan"
    
    def test_is_making_progress_with_intent(self):
        """Test progress detection with classified intent"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-progress-004",
            iteration=5,
            intent=Intent.TASK,
            current_step="plan"
        )
        
        is_progressing = orchestrator._is_making_progress(state)
        
        assert is_progressing is True, "Should detect progress with classified intent"
    
    def test_is_making_progress_no_indicators(self):
        """Test progress detection with no indicators"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-progress-005",
            iteration=5,
            intent=Intent.UNKNOWN,
            current_step="observe",
            plan=None,
            tool_results=[]
        )
        
        is_progressing = orchestrator._is_making_progress(state)
        
        assert is_progressing is False, "Should detect no progress"
    
    def test_is_stuck_in_loop_early_iterations(self):
        """Test loop detection doesn't trigger in early iterations"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-loop-001",
            iteration=2,
            intent=Intent.TASK,
            current_step="execute"
        )
        
        is_stuck = orchestrator._is_stuck_in_loop(state)
        
        assert is_stuck is False, "Should not detect loop in early iterations"
    
    def test_is_stuck_in_loop_repeated_failures(self):
        """Test loop detection with repeated failures"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-loop-002",
            iteration=5,
            intent=Intent.TASK,
            current_step="execute",
            tool_results=[
                {"status": "failed", "error": "Connection timeout", "tool_name": "api_call"},
                {"status": "failed", "error": "Connection timeout", "tool_name": "api_call"},
                {"status": "failed", "error": "Connection timeout", "tool_name": "api_call"}
            ]
        )
        
        is_stuck = orchestrator._is_stuck_in_loop(state)
        
        assert is_stuck is True, "Should detect loop with repeated same errors"
    
    def test_is_stuck_in_loop_repeated_tool_calls(self):
        """Test loop detection with repeated tool calls"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-loop-003",
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
        
        is_stuck = orchestrator._is_stuck_in_loop(state)
        
        assert is_stuck is True, "Should detect loop with repeated tool calls"
    
    def test_is_stuck_in_loop_different_tools(self):
        """Test loop detection doesn't trigger with different tools"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-loop-004",
            iteration=6,
            intent=Intent.TASK,
            current_step="execute",
            tool_results=[
                {"status": "success", "tool_name": "search"},
                {"status": "success", "tool_name": "analyze"},
                {"status": "success", "tool_name": "format"},
                {"status": "success", "tool_name": "save"}
            ]
        )
        
        is_stuck = orchestrator._is_stuck_in_loop(state)
        
        assert is_stuck is False, "Should not detect loop with different tools"
    
    def test_is_stuck_in_loop_different_errors(self):
        """Test loop detection doesn't trigger with different errors"""
        orchestrator = AgentOrchestrator()
        
        state = ReasoningState(
            task_id="task-loop-005",
            iteration=5,
            intent=Intent.TASK,
            current_step="execute",
            tool_results=[
                {"status": "failed", "error": "Connection timeout", "tool_name": "api_call"},
                {"status": "failed", "error": "Invalid response", "tool_name": "api_call"},
                {"status": "failed", "error": "Rate limit exceeded", "tool_name": "api_call"}
            ]
        )
        
        is_stuck = orchestrator._is_stuck_in_loop(state)
        
        assert is_stuck is False, "Should not detect loop with different errors"
    
    def test_integration_with_reflection(self):
        """Test that continuation logic integrates with reflection"""
        orchestrator = AgentOrchestrator(
            enable_reflection=True,
            reflection_trigger_on_failure=True
        )
        
        state = ReasoningState(
            task_id="task-reflect-001",
            iteration=3,
            intent=Intent.TASK,
            current_step="observe",
            plan={"total_steps": 5},
            tool_results=[
                {"status": "success", "tool_name": "tool1"},
                {"status": "failed", "error": "Tool error", "tool_name": "tool2"}
            ]
        )
        
        # should_continue will trigger reflection due to failure
        should_continue = orchestrator.should_continue(state)
        
        # Should continue to allow replanning after reflection
        assert should_continue is True, "Should continue after reflection on failure"


def run_continuation_tests():
    """Run all continuation logic tests"""
    test_class = TestReasoningLoopContinuation()
    
    tests = [
        ("Goal Achieved", test_class.test_goal_achieved_stops_reasoning),
        ("Plan Steps Remaining", test_class.test_plan_steps_remaining),
        ("Plan Complete Successful", test_class.test_plan_complete_successful),
        ("Plan Complete Last Failed", test_class.test_plan_complete_last_failed),
        ("No Progress Stops", test_class.test_no_progress_stops_reasoning),
        ("Early Stage Continues", test_class.test_early_stage_continues),
        ("No Plan Continues", test_class.test_no_plan_continues_to_create_one),
        ("Progress Early Iterations", test_class.test_is_making_progress_early_iterations),
        ("Progress With Results", test_class.test_is_making_progress_with_results),
        ("Progress With Plan", test_class.test_is_making_progress_with_plan),
        ("Progress With Intent", test_class.test_is_making_progress_with_intent),
        ("Progress No Indicators", test_class.test_is_making_progress_no_indicators),
        ("Loop Early Iterations", test_class.test_is_stuck_in_loop_early_iterations),
        ("Loop Repeated Failures", test_class.test_is_stuck_in_loop_repeated_failures),
        ("Loop Repeated Tools", test_class.test_is_stuck_in_loop_repeated_tool_calls),
        ("Loop Different Tools", test_class.test_is_stuck_in_loop_different_tools),
        ("Loop Different Errors", test_class.test_is_stuck_in_loop_different_errors),
        ("Integration With Reflection", test_class.test_integration_with_reflection)
    ]
    
    print("\n" + "=" * 70)
    print("REASONING LOOP CONTINUATION TESTS (Task 6.8)")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            print(f"? {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"? {test_name}: {str(e)}")
            failed += 1
        except Exception as e:
            print(f"? {test_name}: Unexpected error - {str(e)}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    # Run existing tests
    print("Running all Agent Orchestrator tests...")
    
    # Run continuation tests
    success = run_continuation_tests()
    
    if success:
        print("\n? All continuation tests passed!")
    else:
        print("\n? Some continuation tests failed")
        sys.exit(1)
