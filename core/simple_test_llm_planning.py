"""
Simple standalone tests for LLM-based planning functionality

Tests the LLM planning implementation without requiring full environment setup.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock dependencies before importing
from unittest.mock import Mock, MagicMock
import json

# Mock observability modules
sys.modules['observability'] = MagicMock()
sys.modules['events'] = MagicMock()
sys.modules['database'] = MagicMock()

# Now import the module
from hybrid_planner import (
    HybridPlanner,
    TaskComplexity,
    ComplexityClassification,
    PlanningContext,
    TaskPlan,
    PlanStatus
)


def test_create_planning_prompt():
    """Test prompt generation for LLM planning"""
    print("Testing prompt generation...")
    
    planner = HybridPlanner(enable_llm_planning=True)
    
    goal = "Analyze the codebase and suggest refactorings"
    context = PlanningContext(
        available_tools=["file_manager", "code_analyzer", "llm"],
        user_preferences={"verbose": True},
        constraints={"max_duration": 300}
    )
    complexity = ComplexityClassification(
        level=TaskComplexity.COMPLEX,
        requires_llm=True,
        estimated_steps=8,
        confidence=0.9,
        reasoning="Complex task"
    )
    
    prompt = planner._create_planning_prompt(goal, context, complexity)
    
    # Verify prompt contains key elements
    assert goal in prompt, "Goal not in prompt"
    assert "file_manager" in prompt, "Tools not in prompt"
    assert "complex" in prompt.lower(), "Complexity not in prompt"
    assert "JSON" in prompt, "JSON format not mentioned"
    assert "step_id" in prompt, "Step structure not described"
    
    print("✓ Prompt generation test passed")
    return True


def test_format_tools_list():
    """Test tools list formatting"""
    print("Testing tools list formatting...")
    
    planner = HybridPlanner()
    
    # Test with tools
    tools = ["tool1", "tool2", "tool3"]
    formatted = planner._format_tools_list(tools)
    assert "tool1" in formatted
    assert "tool2" in formatted
    assert "tool3" in formatted
    
    # Test empty list
    empty_formatted = planner._format_tools_list([])
    assert "No tools available" in empty_formatted
    
    print("✓ Tools list formatting test passed")
    return True


def test_mock_llm_response():
    """Test mock LLM response generation"""
    print("Testing mock LLM response...")
    
    planner = HybridPlanner()
    
    prompt = "**Goal:** Test goal\n\nGenerate a plan"
    context = PlanningContext(
        available_tools=["file_manager", "browser_agent"]
    )
    
    response = planner._mock_llm_response(prompt, context)
    
    # Verify response structure
    assert "goal" in response, "Missing goal"
    assert "steps" in response, "Missing steps"
    assert "estimated_total_duration_seconds" in response, "Missing duration"
    assert "complexity" in response, "Missing complexity"
    assert "confidence" in response, "Missing confidence"
    
    # Verify steps structure
    assert len(response["steps"]) > 0, "No steps generated"
    for step in response["steps"]:
        assert "step_id" in step
        assert "description" in step
        assert "tool" in step
        assert "parameters" in step
        assert "dependencies" in step
        assert "estimated_duration_seconds" in step
    
    print("✓ Mock LLM response test passed")
    return True


def test_mock_llm_response_no_tools():
    """Test mock LLM response with no tools"""
    print("Testing mock LLM response with no tools...")
    
    planner = HybridPlanner()
    
    prompt = "**Goal:** Test goal"
    context = PlanningContext(available_tools=[])
    
    response = planner._mock_llm_response(prompt, context)
    
    # Should still generate a plan
    assert len(response["steps"]) == 1
    assert response["steps"][0]["tool"] == "generic_executor"
    
    print("✓ Mock LLM response (no tools) test passed")
    return True


def test_parse_llm_response():
    """Test LLM response parsing"""
    print("Testing LLM response parsing...")
    
    planner = HybridPlanner()
    
    goal = "Test goal"
    complexity = ComplexityClassification(
        level=TaskComplexity.COMPLEX,
        requires_llm=True,
        estimated_steps=2,
        confidence=0.9,
        reasoning="Test"
    )
    
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
    
    plan = planner._parse_llm_response(response, goal, complexity)
    
    # Verify plan
    assert plan is not None, "Plan is None"
    assert isinstance(plan, TaskPlan), "Not a TaskPlan"
    assert plan.goal == goal, "Goal mismatch"
    assert len(plan.steps) == 2, "Wrong number of steps"
    assert plan.complexity == TaskComplexity.COMPLEX, "Wrong complexity"
    assert plan.planning_approach == "llm_based", "Wrong approach"
    assert plan.status == PlanStatus.VALID, "Wrong status"
    assert plan.estimated_duration_seconds == 15, "Wrong duration"
    
    # Verify metadata
    assert plan.metadata["llm_based"] is True
    assert plan.metadata["llm_confidence"] == 0.85
    assert plan.metadata["actual_steps"] == 2
    
    # Verify dependencies
    assert "step_1" in plan.dependencies
    
    print("✓ LLM response parsing test passed")
    return True


def test_parse_llm_response_empty_steps():
    """Test parsing response with no steps"""
    print("Testing parsing with empty steps...")
    
    planner = HybridPlanner()
    
    goal = "Test goal"
    complexity = ComplexityClassification(
        level=TaskComplexity.SIMPLE,
        requires_llm=False,
        estimated_steps=0,
        confidence=0.5,
        reasoning="Test"
    )
    
    response = {
        "goal": goal,
        "steps": [],
        "estimated_total_duration_seconds": 0,
        "complexity": "simple",
        "confidence": 0.5
    }
    
    plan = planner._parse_llm_response(response, goal, complexity)
    
    # Should return None for empty steps
    assert plan is None, "Should return None for empty steps"
    
    print("✓ Empty steps parsing test passed")
    return True


def test_parse_llm_response_missing_fields():
    """Test parsing with missing optional fields"""
    print("Testing parsing with missing fields...")
    
    planner = HybridPlanner()
    
    goal = "Test goal"
    complexity = ComplexityClassification(
        level=TaskComplexity.MODERATE,
        requires_llm=True,
        estimated_steps=1,
        confidence=0.7,
        reasoning="Test"
    )
    
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
        # Missing optional fields
    }
    
    plan = planner._parse_llm_response(response, goal, complexity)
    
    # Should still parse with defaults
    assert plan is not None, "Should parse with missing optional fields"
    assert plan.estimated_duration_seconds == 5  # Calculated from steps
    
    print("✓ Missing fields parsing test passed")
    return True


def test_generate_llm_plan_with_mock():
    """Test full LLM plan generation with mock"""
    print("Testing full LLM plan generation...")
    
    planner = HybridPlanner(enable_llm_planning=True)
    
    goal = "Analyze codebase and suggest improvements"
    context = PlanningContext(
        available_tools=["file_manager", "code_analyzer", "llm"]
    )
    complexity = ComplexityClassification(
        level=TaskComplexity.COMPLEX,
        requires_llm=True,
        estimated_steps=5,
        confidence=0.9,
        reasoning="Complex analysis task"
    )
    
    # This will use mock LLM since Model Router is not available
    plan = planner._generate_llm_plan(goal, context, complexity)
    
    # Verify plan was created
    assert plan is not None, "Plan generation failed"
    assert isinstance(plan, TaskPlan), "Not a TaskPlan"
    assert plan.goal == goal, "Goal mismatch"
    assert len(plan.steps) > 0, "No steps generated"
    assert plan.planning_approach == "llm_based", "Wrong approach"
    
    print("✓ Full LLM plan generation test passed")
    return True


def test_integration_create_plan_complex():
    """Test integration with create_plan for complex task"""
    print("Testing integration with create_plan...")
    
    planner = HybridPlanner(
        enable_llm_planning=True,
        enable_rule_based_planning=True,
        llm_fallback_enabled=True
    )
    
    # Complex task that should use LLM
    goal = "Research machine learning frameworks, compare their features, and create a detailed report"
    context = PlanningContext(
        available_tools=["browser_agent", "file_manager", "llm"]
    )
    
    plan = planner.create_plan(goal, context)
    
    # Verify plan was created
    assert plan is not None, "Plan creation failed"
    assert plan.goal == goal, "Goal mismatch"
    assert len(plan.steps) > 0, "No steps in plan"
    # Should use LLM for complex task
    assert plan.planning_approach in ["llm_based", "rule_based"], "Invalid approach"
    
    print("✓ Integration test passed")
    return True


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("Running LLM Planning Tests")
    print("="*60 + "\n")
    
    tests = [
        test_create_planning_prompt,
        test_format_tools_list,
        test_mock_llm_response,
        test_mock_llm_response_no_tools,
        test_parse_llm_response,
        test_parse_llm_response_empty_steps,
        test_parse_llm_response_missing_fields,
        test_generate_llm_plan_with_mock,
        test_integration_create_plan_complex
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            failed += 1
        print()
    
    print("="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
