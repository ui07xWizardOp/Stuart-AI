"""
Unit tests for HybridPlanner

Tests task complexity classification, plan generation, validation,
repair, and tool selection functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from cognitive.hybrid_planner import (
    HybridPlanner,
    TaskComplexity,
    PlanStatus,
    ComplexityClassification,
    TaskPlan,
    PlanningContext,
    ToolSelection,
    ValidationResult,
    PlanError
)


@pytest.fixture
def planner():
    """Create HybridPlanner instance for testing"""
    planner = HybridPlanner(
        enable_llm_planning=True,
        enable_rule_based_planning=True,
        llm_fallback_enabled=True,
        max_plan_steps=20,
        max_repair_attempts=3
    )
    
    # Mock dependencies
    planner.model_router = Mock()
    planner.tool_registry = Mock()
    planner.prompt_manager = Mock()
    
    return planner


@pytest.fixture
def planning_context():
    """Create PlanningContext for testing"""
    return PlanningContext(
        available_tools=["file_manager", "browser_agent", "llm", "knowledge_manager"],
        user_preferences={"verbose": True},
        execution_history=[],
        constraints={"max_steps": 10},
        session_context={"user_id": "test_user"}
    )


class TestComplexityClassification:
    """Tests for task complexity classification"""

    def test_classify_simple_task(self, planner):
        """Test classification of simple tasks"""
        goal = "read file example.txt"
        
        result = planner.classify_task_complexity(goal)
        
        assert result.level == TaskComplexity.SIMPLE
        assert result.requires_llm is False
        assert result.confidence >= 0.8
        assert "read" in result.keywords_matched
        assert "simple" in result.reasoning.lower()
    
    def test_classify_complex_task(self, planner):
        """Test classification of complex tasks"""
        goal = "analyze the codebase and suggest refactorings for better performance"
        
        result = planner.classify_task_complexity(goal)
        
        assert result.level == TaskComplexity.COMPLEX
        assert result.requires_llm is True
        assert result.confidence >= 0.7
        assert any(kw in result.keywords_matched for kw in ["analyze", "refactor"])
        assert "complex" in result.reasoning.lower()
    
    def test_classify_moderate_task_with_conditional(self, planner):
        """Test classification of moderate tasks with conditionals"""
        goal = "if the file exists, read it and summarize, otherwise create it"
        
        result = planner.classify_task_complexity(goal)
        
        assert result.level in [TaskComplexity.MODERATE, TaskComplexity.COMPLEX]
        assert result.requires_llm is True
        assert "conditional" in result.reasoning.lower() or result.multi_step_detected
    
    def test_classify_moderate_task_with_multiple_sentences(self, planner):
        """Test classification of moderate tasks with multiple sentences"""
        goal = "Read the file. Extract the data. Save it to database."
        
        result = planner.classify_task_complexity(goal)
        
        assert result.level in [TaskComplexity.MODERATE, TaskComplexity.COMPLEX]
        assert result.estimated_steps >= 2
        assert result.multi_step_detected is True
    
    def test_classify_long_task(self, planner):
        """Test classification of tasks with many words"""
        goal = "search for information about machine learning algorithms and compare their performance characteristics"
        
        result = planner.classify_task_complexity(goal)
        
        assert result.level in [TaskComplexity.MODERATE, TaskComplexity.COMPLEX]
        assert result.estimated_steps >= 3
    
    def test_weighted_keyword_scoring(self, planner):
        """Test that weighted keywords affect classification"""
        # Task with high-weight simple keyword
        goal1 = "list all files in directory"
        result1 = planner.classify_task_complexity(goal1)
        
        # Task with low-weight simple keyword
        goal2 = "find some information"
        result2 = planner.classify_task_complexity(goal2)
        
        # Both should be simple/moderate, but confidence may differ
        assert result1.level in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE]
        assert result2.level in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE]
    
    def test_pattern_recognition(self, planner):
        """Test pattern recognition for common task types"""
        # File read pattern
        goal1 = "read file test.txt"
        result1 = planner.classify_task_complexity(goal1)
        assert "file_read" in result1.pattern_matches or result1.level == TaskComplexity.SIMPLE
        
        # Code analysis pattern
        goal2 = "analyze code quality in the project"
        result2 = planner.classify_task_complexity(goal2)
        assert result2.level == TaskComplexity.COMPLEX
    
    def test_multi_step_detection(self, planner):
        """Test detection of multi-step tasks"""
        goal = "read the file and then process the data and save results"
        
        result = planner.classify_task_complexity(goal)
        
        assert result.multi_step_detected is True
        assert result.estimated_steps >= 3
    
    def test_dependency_analysis(self, planner):
        """Test dependency detection"""
        goal = "after reading the file, process it, then save results once validation passes"
        
        result = planner.classify_task_complexity(goal)
        
        assert result.dependency_count >= 2
        assert result.estimated_steps >= 4
    
    def test_resource_requirement_estimation(self, planner):
        """Test resource requirement detection"""
        # Filesystem resource
        goal1 = "read file and write output"
        result1 = planner.classify_task_complexity(goal1)
        assert result1.resource_requirements.get('filesystem') is True
        
        # Network resource
        goal2 = "search the web for information"
        result2 = planner.classify_task_complexity(goal2)
        assert result2.resource_requirements.get('network') is True
        
        # LLM resource
        goal3 = "analyze and summarize the document"
        result3 = planner.classify_task_complexity(goal3)
        assert result3.resource_requirements.get('llm') is True
    
    def test_confidence_calibration(self, planner):
        """Test confidence scoring based on multiple signals"""
        # Clear simple task - high confidence
        goal1 = "read file test.txt"
        result1 = planner.classify_task_complexity(goal1)
        
        # Ambiguous task - lower confidence
        goal2 = "do something with the data"
        result2 = planner.classify_task_complexity(goal2)
        
        # Complex task with clear indicators - high confidence
        goal3 = "analyze the codebase, debug issues, and refactor for performance"
        result3 = planner.classify_task_complexity(goal3)
        
        assert result1.confidence >= 0.7
        assert result3.confidence >= 0.7
    
    def test_loop_detection(self, planner):
        """Test detection of tasks requiring iteration"""
        goal = "process each file in the directory"
        
        result = planner.classify_task_complexity(goal)
        
        assert result.level in [TaskComplexity.MODERATE, TaskComplexity.COMPLEX]
        assert result.multi_step_detected is True
    
    def test_classification_serialization(self, planner):
        """Test that enhanced classification can be serialized"""
        goal = "analyze code and suggest improvements"
        
        result = planner.classify_task_complexity(goal)
        data = result.to_dict()
        
        assert "pattern_matches" in data
        assert "multi_step_detected" in data
        assert "dependency_count" in data
        assert "resource_requirements" in data
        assert isinstance(data["pattern_matches"], list)
        assert isinstance(data["multi_step_detected"], bool)
        assert isinstance(data["dependency_count"], int)
        assert isinstance(data["resource_requirements"], dict)


class TestPlanGeneration:
    """Tests for plan generation"""
    
    def test_create_plan_caches_result(self, planner, planning_context):
        """Test that plans are cached for repeated goals"""
        goal = "read file test.txt"
        
        # Mock the internal methods to return a valid plan
        mock_plan = TaskPlan(
            plan_id="test_plan_1",
            goal=goal,
            steps=[{"tool": "file_manager", "action": "read"}],
            complexity=TaskComplexity.SIMPLE,
            planning_approach="rule_based"
        )
        
        with patch.object(planner, '_generate_rule_based_plan', return_value=mock_plan):
            with patch.object(planner, 'validate_plan', return_value=ValidationResult(is_valid=True, status=PlanStatus.VALID)):
                # First call
                plan1 = planner.create_plan(goal, planning_context)
                
                # Second call should use cache
                plan2 = planner.create_plan(goal, planning_context)
                
                assert plan1.plan_id == plan2.plan_id
                assert len(planner._plan_cache) > 0

    def test_create_plan_validates_and_repairs(self, planner, planning_context):
        """Test that invalid plans are repaired"""
        goal = "test goal"
        
        mock_plan = TaskPlan(
            plan_id="test_plan_2",
            goal=goal,
            steps=[{"tool": "unknown_tool"}],
            complexity=TaskComplexity.SIMPLE,
            planning_approach="rule_based"
        )
        
        # First validation fails, second succeeds
        validation_results = [
            ValidationResult(is_valid=False, status=PlanStatus.INVALID, errors=["Unknown tool"]),
            ValidationResult(is_valid=True, status=PlanStatus.VALID)
        ]
        
        with patch.object(planner, '_generate_rule_based_plan', return_value=mock_plan):
            with patch.object(planner, 'validate_plan', side_effect=validation_results):
                with patch.object(planner, 'repair_plan', return_value=mock_plan):
                    plan = planner.create_plan(goal, planning_context)
                    
                    assert plan is not None
                    # repair_plan should have been called
                    planner.repair_plan.assert_called_once()
    
    def test_create_plan_raises_on_failure(self, planner, planning_context):
        """Test that plan creation raises error when all approaches fail"""
        goal = "impossible task"
        
        with patch.object(planner, '_generate_rule_based_plan', return_value=None):
            with patch.object(planner, '_generate_llm_plan', return_value=None):
                with pytest.raises(ValueError, match="Failed to generate plan"):
                    planner.create_plan(goal, planning_context)


class TestToolSelection:
    """Tests for tool selection"""
    
    def test_select_tool_returns_selection(self, planner):
        """Test that tool selection returns a ToolSelection"""
        task_step = {"action": "read_file", "param": "test.txt"}
        available_tools = ["file_manager", "browser_agent"]
        
        selection = planner.select_tool(task_step, available_tools)
        
        assert isinstance(selection, ToolSelection)
        assert selection.tool_name in available_tools
        assert 0.0 <= selection.confidence <= 1.0
        assert selection.reasoning is not None
    
    def test_select_tool_with_empty_tools(self, planner):
        """Test tool selection with no available tools"""
        task_step = {"action": "read_file"}
        available_tools = []
        
        selection = planner.select_tool(task_step, available_tools)
        
        assert selection.tool_name == "unknown"
        assert selection.confidence <= 1.0


class TestPlanValidation:
    """Tests for plan validation"""
    
    def test_validate_plan_returns_result(self, planner, planning_context):
        """Test that plan validation returns ValidationResult"""
        plan = TaskPlan(
            plan_id="test_plan_3",
            goal="test",
            steps=[{"tool": "file_manager"}],
            complexity=TaskComplexity.SIMPLE,
            planning_approach="rule_based"
        )
        
        result = planner.validate_plan(plan, planning_context)
        
        assert isinstance(result, ValidationResult)
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.status, PlanStatus)


class TestPlanRepair:
    """Tests for plan repair"""
    
    def test_repair_plan_updates_status(self, planner, planning_context):
        """Test that plan repair updates plan status"""
        plan = TaskPlan(
            plan_id="test_plan_4",
            goal="test",
            steps=[],
            complexity=TaskComplexity.SIMPLE,
            planning_approach="rule_based",
            status=PlanStatus.INVALID
        )
        
        error = PlanError(
            error_type="missing_steps",
            description="Plan has no steps"
        )
        
        repaired = planner.repair_plan(plan, error, planning_context)
        
        assert repaired.status == PlanStatus.REPAIRED



class TestDataClasses:
    """Tests for dataclass serialization"""
    
    def test_complexity_classification_to_dict(self):
        """Test ComplexityClassification serialization"""
        classification = ComplexityClassification(
            level=TaskComplexity.SIMPLE,
            requires_llm=False,
            estimated_steps=2,
            confidence=0.9,
            reasoning="Test reasoning",
            keywords_matched=["read", "file"]
        )
        
        data = classification.to_dict()
        
        assert data["level"] == "simple"
        assert data["requires_llm"] is False
        assert data["estimated_steps"] == 2
        assert data["confidence"] == 0.9
        assert "read" in data["keywords_matched"]
    
    def test_task_plan_to_dict(self):
        """Test TaskPlan serialization"""
        plan = TaskPlan(
            plan_id="test_plan_5",
            goal="test goal",
            steps=[{"tool": "file_manager"}],
            complexity=TaskComplexity.MODERATE,
            planning_approach="llm_based",
            status=PlanStatus.VALID
        )
        
        data = plan.to_dict()
        
        assert data["plan_id"] == "test_plan_5"
        assert data["goal"] == "test goal"
        assert data["complexity"] == "moderate"
        assert data["planning_approach"] == "llm_based"
        assert data["status"] == "valid"
        assert isinstance(data["created_at"], str)
    
    def test_tool_selection_to_dict(self):
        """Test ToolSelection serialization"""
        selection = ToolSelection(
            tool_name="file_manager",
            confidence=0.85,
            reasoning="Best match for file operations",
            parameters={"path": "/test"},
            alternatives=[("browser_agent", 0.3)],
            fallback_tool="llm"
        )
        
        data = selection.to_dict()
        
        assert data["tool_name"] == "file_manager"
        assert data["confidence"] == 0.85
        assert data["fallback_tool"] == "llm"
        assert len(data["alternatives"]) == 1
    
    def test_validation_result_to_dict(self):
        """Test ValidationResult serialization"""
        result = ValidationResult(
            is_valid=False,
            status=PlanStatus.INVALID,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
            suggestions=["Suggestion 1"]
        )
        
        data = result.to_dict()
        
        assert data["is_valid"] is False
        assert data["status"] == PlanStatus.INVALID
        assert len(data["errors"]) == 2
        assert len(data["warnings"]) == 1
        assert len(data["suggestions"]) == 1


class TestPlannerConfiguration:
    """Tests for planner configuration"""
    
    def test_planner_initialization(self):
        """Test planner initializes with correct configuration"""
        planner = HybridPlanner(
            enable_llm_planning=False,
            enable_rule_based_planning=True,
            llm_fallback_enabled=False,
            max_plan_steps=15,
            max_repair_attempts=5
        )
        
        assert planner.enable_llm_planning is False
        assert planner.enable_rule_based_planning is True
        assert planner.llm_fallback_enabled is False
        assert planner.max_plan_steps == 15
        assert planner.max_repair_attempts == 5
    
    def test_planner_has_plan_templates(self):
        """Test planner has predefined plan templates"""
        assert "read_and_summarize" in HybridPlanner.PLAN_TEMPLATES
        assert "web_search" in HybridPlanner.PLAN_TEMPLATES
        assert "file_operation" in HybridPlanner.PLAN_TEMPLATES
        assert "knowledge_search" in HybridPlanner.PLAN_TEMPLATES
    
    def test_planner_has_complexity_keywords(self):
        """Test planner has complexity classification keywords"""
        assert len(HybridPlanner.SIMPLE_TASK_KEYWORDS) > 0
        assert len(HybridPlanner.COMPLEX_TASK_KEYWORDS) > 0
        assert "read" in HybridPlanner.SIMPLE_TASK_KEYWORDS
        assert "analyze" in HybridPlanner.COMPLEX_TASK_KEYWORDS
        # Verify they are dictionaries with weights
        assert isinstance(HybridPlanner.SIMPLE_TASK_KEYWORDS, dict)
        assert isinstance(HybridPlanner.COMPLEX_TASK_KEYWORDS, dict)
        assert isinstance(HybridPlanner.SIMPLE_TASK_KEYWORDS["read"], float)
    
    def test_planner_has_task_patterns(self):
        """Test planner has task pattern definitions"""
        assert hasattr(HybridPlanner, 'TASK_PATTERNS')
        assert isinstance(HybridPlanner.TASK_PATTERNS, dict)
        assert len(HybridPlanner.TASK_PATTERNS) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
