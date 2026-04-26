"""
Tests for LLM-based planning functionality in HybridPlanner

Tests the _generate_llm_plan method and related functionality including:
- Prompt generation
- LLM call with retry logic
- Response parsing
- Error handling
- Integration with schema validator and retry manager
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from hybrid_planner import (
    HybridPlanner,
    TaskComplexity,
    ComplexityClassification,
    PlanningContext,
    TaskPlan,
    PlanStatus
)


class TestLLMPlanning:
    """Test suite for LLM-based planning"""
    
    @pytest.fixture
    def planner(self):
        """Create HybridPlanner instance"""
        return HybridPlanner(
            enable_llm_planning=True,
            enable_rule_based_planning=True,
            llm_fallback_enabled=True
        )
    
    @pytest.fixture
    def complex_classification(self):
        """Create complex task classification"""
        return ComplexityClassification(
            level=TaskComplexity.COMPLEX,
            requires_llm=True,
            estimated_steps=8,
            confidence=0.9,
            reasoning="Complex task requiring LLM planning",
            keywords_matched=["analyze", "refactor"],
            pattern_matches=[],
            multi_step_detected=True,
            dependency_count=2,
            resource_requirements={"llm": True, "filesystem": True}
        )
    
    @pytest.fixture
    def planning_context(self):
        """Create planning context"""
        return PlanningContext(
            available_tools=["file_manager", "code_analyzer", "llm", "browser_agent"],
            user_preferences={"verbose": True},
            constraints={"max_duration": 300},
            session_context={"user_id": "test_user"}
        )
    
    def test_create_planning_prompt(self, planner, complex_classification, planning_context):
        """Test prompt generation for LLM planning"""
        goal = "Analyze the codebase and suggest refactorings"
        
        prompt = planner._create_planning_prompt(goal, planning_context, complex_classification)
        
        # Verify prompt contains key elements
        assert goal in prompt
        assert "file_manager" in prompt
        assert "code_analyzer" in prompt
        assert "complex" in prompt.lower()
        assert "8" in prompt  # estimated steps
        assert "JSON" in prompt
        assert "step_id" in prompt
        assert "dependencies" in prompt
        
        # Verify JSON format instructions
        assert "valid JSON" in prompt
        assert "double quotes" in prompt
    
    def test_format_tools_list_simple(self, planner):
        """Test simple tools list formatting"""
        tools = ["tool1", "tool2", "tool3"]
        
        formatted = planner._format_tools_list(tools)
        
        assert "tool1" in formatted
        assert "tool2" in formatted
        assert "tool3" in formatted
        assert formatted.count("-") == 3  # Bullet points
    
    def test_format_tools_list_empty(self, planner):
        """Test empty tools list formatting"""
        tools = []
        
        formatted = planner._format_tools_list(tools)
        
        assert "No tools available" in formatted
    
    def test_format_tools_list_with_registry(self, planner):
        """Test tools list formatting with tool registry"""
        # Mock tool registry
        mock_registry = Mock()
        mock_tool = Mock()
        mock_tool.description = "Manages file operations"
        mock_registry.get_tool.return_value = mock_tool
        
        planner.tool_registry = mock_registry
        tools = ["file_manager"]
        
        formatted = planner._format_tools_list(tools)
        
        assert "file_manager" in formatted
        assert "Manages file operations" in formatted
    
    def test_mock_llm_response(self, planner, planning_context):
        """Test mock LLM response generation"""
        prompt = "**Goal:** Test goal\n\nGenerate a plan"
        
        response = planner._mock_llm_response(prompt, planning_context)
        
        # Verify response structure
        assert "goal" in response
        assert "steps" in response
        assert "estimated_total_duration_seconds" in response
        assert "complexity" in response
        assert "confidence" in response
        
        # Verify steps
        assert len(response["steps"]) > 0
        for step in response["steps"]:
            assert "step_id" in step
            assert "description" in step
            assert "tool" in step
            assert "parameters" in step
            assert "dependencies" in step
            assert "estimated_duration_seconds" in step
    
    def test_mock_llm_response_no_tools(self, planner):
        """Test mock LLM response with no available tools"""
        prompt = "**Goal:** Test goal"
        context = PlanningContext(available_tools=[])
        
        response = planner._mock_llm_response(prompt, context)
        
        # Should still generate a plan with generic step
        assert len(response["steps"]) == 1
        assert response["steps"][0]["tool"] == "generic_executor"
    
    def test_parse_llm_response_success(self, planner, complex_classification):
        """Test successful LLM response parsing"""
        goal = "Test goal"
        response = {
            "goal": goal,
            "steps": [
                {
                    "step_id": "step_1",
                    "description": "First step",
                    "tool": "file_manager",
                    "parameters": {"path": "/test"},
                    "dependencies": [],
                    "estimated_duration_seconds": 5
                },
                {
                    "step_id": "step_2",
                    "description": "Second step",
                    "tool": "code_analyzer",
                    "parameters": {"file": "test.py"},
                    "dependencies": ["step_1"],
                    "estimated_duration_seconds": 10
                }
            ],
            "estimated_total_duration_seconds": 15,
            "complexity": "complex",
            "confidence": 0.85
        }
        
        plan = planner._parse_llm_response(response, goal, complex_classification)
        
        # Verify plan structure
        assert plan is not None
        assert isinstance(plan, TaskPlan)
        assert plan.goal == goal
        assert len(plan.steps) == 2
        assert plan.complexity == TaskComplexity.COMPLEX
        assert plan.planning_approach == "llm_based"
        assert plan.status == PlanStatus.VALID
        assert plan.estimated_duration_seconds == 15
        
        # Verify metadata
        assert plan.metadata["llm_based"] is True
        assert plan.metadata["llm_confidence"] == 0.85
        assert plan.metadata["actual_steps"] == 2
        
        # Verify dependencies
        assert "step_1" in plan.dependencies
    
    def test_parse_llm_response_empty_steps(self, planner, complex_classification):
        """Test parsing LLM response with no steps"""
        goal = "Test goal"
        response = {
            "goal": goal,
            "steps": [],
            "estimated_total_duration_seconds": 0,
            "complexity": "simple",
            "confidence": 0.5
        }
        
        plan = planner._parse_llm_response(response, goal, complex_classification)
        
        # Should return None for empty steps
        assert plan is None
    
    def test_parse_llm_response_missing_fields(self, planner, complex_classification):
        """Test parsing LLM response with missing optional fields"""
        goal = "Test goal"
        response = {
            "goal": goal,
            "steps": [
                {
                    "step_id": "step_1",
                    "description": "Test step",
                    "tool": "test_tool",
                    "parameters": {},
                    "dependencies": [],
                    "estimated_duration_seconds": 5
                }
            ]
            # Missing estimated_total_duration_seconds, complexity, confidence
        }
        
        plan = planner._parse_llm_response(response, goal, complex_classification)
        
        # Should still parse successfully with defaults
        assert plan is not None
        assert plan.estimated_duration_seconds == 5  # Calculated from steps
    
    @patch('hybrid_planner.get_llm_schema_validator')
    @patch('hybrid_planner.get_llm_retry_manager')
    def test_call_llm_with_retry_success(
        self,
        mock_get_retry_manager,
        mock_get_validator,
        planner,
        planning_context
    ):
        """Test successful LLM call with retry logic"""
        # Mock validator
        mock_validator = Mock()
        mock_validator.validate_or_raise.return_value = {
            "goal": "Test",
            "steps": [{"step_id": "step_1", "description": "Test", "tool": "test", "parameters": {}, "dependencies": [], "estimated_duration_seconds": 5}],
            "estimated_total_duration_seconds": 5,
            "complexity": "simple",
            "confidence": 0.8
        }
        mock_get_validator.return_value = mock_validator
        
        # Mock retry manager
        mock_retry_manager = Mock()
        mock_retry_result = Mock()
        mock_retry_result.success = True
        mock_retry_result.attempts = 1
        mock_retry_result.total_delay_seconds = 0.0
        mock_retry_result.final_result = mock_validator.validate_or_raise.return_value
        mock_retry_manager.retry_with_validation.return_value = mock_retry_result
        mock_get_retry_manager.return_value = mock_retry_manager
        
        prompt = "Test prompt"
        
        response = planner._call_llm_with_retry(prompt, planning_context)
        
        # Verify success
        assert response is not None
        assert "goal" in response
        assert "steps" in response
        
        # Verify retry manager was called
        mock_retry_manager.retry_with_validation.assert_called_once()
    
    @patch('hybrid_planner.get_llm_schema_validator')
    @patch('hybrid_planner.get_llm_retry_manager')
    def test_call_llm_with_retry_failure(
        self,
        mock_get_retry_manager,
        mock_get_validator,
        planner,
        planning_context
    ):
        """Test LLM call failure after retries"""
        # Mock validator
        mock_validator = Mock()
        mock_get_validator.return_value = mock_validator
        
        # Mock retry manager with failure
        mock_retry_manager = Mock()
        mock_retry_result = Mock()
        mock_retry_result.success = False
        mock_retry_result.attempts = 3
        mock_retry_result.error = "Validation failed"
        mock_retry_manager.retry_with_validation.return_value = mock_retry_result
        mock_get_retry_manager.return_value = mock_retry_manager
        
        prompt = "Test prompt"
        
        response = planner._call_llm_with_retry(prompt, planning_context)
        
        # Should return None on failure
        assert response is None
    
    @patch('hybrid_planner.get_llm_schema_validator')
    @patch('hybrid_planner.get_llm_retry_manager')
    def test_generate_llm_plan_success(
        self,
        mock_get_retry_manager,
        mock_get_validator,
        planner,
        complex_classification,
        planning_context
    ):
        """Test successful LLM plan generation"""
        goal = "Analyze codebase and suggest improvements"
        
        # Mock validator
        mock_validator = Mock()
        valid_response = {
            "goal": goal,
            "steps": [
                {
                    "step_id": "step_1",
                    "description": "Read codebase",
                    "tool": "file_manager",
                    "parameters": {"path": "/code"},
                    "dependencies": [],
                    "estimated_duration_seconds": 10
                },
                {
                    "step_id": "step_2",
                    "description": "Analyze code",
                    "tool": "code_analyzer",
                    "parameters": {"files": "all"},
                    "dependencies": ["step_1"],
                    "estimated_duration_seconds": 20
                }
            ],
            "estimated_total_duration_seconds": 30,
            "complexity": "complex",
            "confidence": 0.9
        }
        mock_validator.validate_or_raise.return_value = valid_response
        mock_get_validator.return_value = mock_validator
        
        # Mock retry manager
        mock_retry_manager = Mock()
        mock_retry_result = Mock()
        mock_retry_result.success = True
        mock_retry_result.attempts = 1
        mock_retry_result.total_delay_seconds = 0.0
        mock_retry_result.final_result = valid_response
        mock_retry_manager.retry_with_validation.return_value = mock_retry_result
        mock_get_retry_manager.return_value = mock_retry_manager
        
        # Generate plan
        plan = planner._generate_llm_plan(goal, planning_context, complex_classification)
        
        # Verify plan
        assert plan is not None
        assert isinstance(plan, TaskPlan)
        assert plan.goal == goal
        assert len(plan.steps) == 2
        assert plan.planning_approach == "llm_based"
        assert plan.complexity == TaskComplexity.COMPLEX
        assert plan.estimated_duration_seconds == 30
    
    def test_generate_llm_plan_llm_call_failure(
        self,
        planner,
        complex_classification,
        planning_context
    ):
        """Test LLM plan generation when LLM call fails"""
        goal = "Test goal"
        
        # Mock _call_llm_with_retry to return None
        planner._call_llm_with_retry = Mock(return_value=None)
        
        plan = planner._generate_llm_plan(goal, planning_context, complex_classification)
        
        # Should return None when LLM call fails
        assert plan is None
    
    def test_generate_llm_plan_parse_failure(
        self,
        planner,
        complex_classification,
        planning_context
    ):
        """Test LLM plan generation when parsing fails"""
        goal = "Test goal"
        
        # Mock _call_llm_with_retry to return invalid response
        planner._call_llm_with_retry = Mock(return_value={"invalid": "response"})
        
        # Mock _parse_llm_response to return None
        planner._parse_llm_response = Mock(return_value=None)
        
        plan = planner._generate_llm_plan(goal, planning_context, complex_classification)
        
        # Should return None when parsing fails
        assert plan is None
    
    def test_generate_llm_plan_exception_handling(
        self,
        planner,
        complex_classification,
        planning_context
    ):
        """Test exception handling in LLM plan generation"""
        goal = "Test goal"
        
        # Mock _create_planning_prompt to raise exception
        planner._create_planning_prompt = Mock(side_effect=Exception("Test error"))
        
        plan = planner._generate_llm_plan(goal, planning_context, complex_classification)
        
        # Should return None and log error
        assert plan is None
    
    def test_create_plan_uses_llm_for_complex_task(
        self,
        planner,
        planning_context
    ):
        """Test that create_plan uses LLM for complex tasks"""
        goal = "Analyze the entire codebase, identify code smells, and suggest comprehensive refactorings"
        
        # Mock _generate_llm_plan
        mock_plan = TaskPlan(
            plan_id="test_plan",
            goal=goal,
            steps=[{"step_id": "step_1", "description": "Test", "tool": "test"}],
            complexity=TaskComplexity.COMPLEX,
            planning_approach="llm_based"
        )
        planner._generate_llm_plan = Mock(return_value=mock_plan)
        
        # Create plan
        plan = planner.create_plan(goal, planning_context)
        
        # Verify LLM planning was used
        assert plan.planning_approach == "llm_based"
        planner._generate_llm_plan.assert_called_once()
    
    def test_create_plan_llm_fallback(self, planner, planning_context):
        """Test fallback to LLM when rule-based planning fails"""
        goal = "Do something unusual that doesn't match any template"
        
        # Mock _generate_rule_based_plan to return None
        planner._generate_rule_based_plan = Mock(return_value=None)
        
        # Mock _generate_llm_plan to return a plan
        mock_plan = TaskPlan(
            plan_id="test_plan",
            goal=goal,
            steps=[{"step_id": "step_1", "description": "Test", "tool": "test"}],
            complexity=TaskComplexity.MODERATE,
            planning_approach="llm_based"
        )
        planner._generate_llm_plan = Mock(return_value=mock_plan)
        
        # Create plan
        plan = planner.create_plan(goal, planning_context)
        
        # Verify fallback to LLM
        assert plan.planning_approach == "llm_based"
        planner._generate_llm_plan.assert_called_once()


class TestLLMPlanningIntegration:
    """Integration tests for LLM planning with real components"""
    
    @pytest.fixture
    def planner(self):
        """Create HybridPlanner instance"""
        return HybridPlanner(
            enable_llm_planning=True,
            enable_rule_based_planning=True,
            llm_fallback_enabled=True
        )
    
    def test_end_to_end_llm_planning_with_mock(self, planner):
        """Test end-to-end LLM planning flow with mock LLM"""
        goal = "Research machine learning frameworks and create a comparison report"
        context = PlanningContext(
            available_tools=["browser_agent", "file_manager", "llm"],
            constraints={"max_duration": 600}
        )
        
        # This will use mock LLM since Model Router is not available
        plan = planner.create_plan(goal, context)
        
        # Verify plan was created
        assert plan is not None
        assert plan.goal == goal
        assert len(plan.steps) > 0
        assert plan.planning_approach in ["llm_based", "rule_based"]
    
    def test_prompt_contains_all_context(self, planner):
        """Test that prompt includes all relevant context"""
        goal = "Complex analysis task"
        context = PlanningContext(
            available_tools=["tool1", "tool2"],
            user_preferences={"style": "detailed"},
            constraints={"max_steps": 10},
            session_context={"user": "test"}
        )
        complexity = ComplexityClassification(
            level=TaskComplexity.COMPLEX,
            requires_llm=True,
            estimated_steps=5,
            confidence=0.9,
            reasoning="Test"
        )
        
        prompt = planner._create_planning_prompt(goal, context, complexity)
        
        # Verify all context is included
        assert goal in prompt
        assert "tool1" in prompt
        assert "tool2" in prompt
        assert "detailed" in prompt
        assert "10" in prompt
        assert "complex" in prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
