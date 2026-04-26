"""
Example usage of LLM-based planning in HybridPlanner

Demonstrates how to use the LLM planning functionality for complex tasks.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock dependencies
from unittest.mock import MagicMock
sys.modules['observability'] = MagicMock()
sys.modules['events'] = MagicMock()
sys.modules['database'] = MagicMock()

from hybrid_planner import (
    HybridPlanner,
    PlanningContext,
    TaskComplexity,
    ComplexityClassification
)
import json


def example_1_basic_llm_planning():
    """Example 1: Basic LLM planning for complex task"""
    print("\n" + "="*60)
    print("Example 1: Basic LLM Planning")
    print("="*60 + "\n")
    
    # Create planner with LLM enabled
    planner = HybridPlanner(
        enable_llm_planning=True,
        enable_rule_based_planning=True,
        llm_fallback_enabled=True
    )
    
    # Define complex task
    goal = "Analyze the codebase, identify code smells, and suggest refactorings"
    
    # Create planning context
    context = PlanningContext(
        available_tools=["file_manager", "code_analyzer", "llm", "browser_agent"],
        user_preferences={"verbose": True, "detail_level": "high"},
        constraints={"max_duration": 600, "max_files": 100}
    )
    
    print(f"Goal: {goal}\n")
    print(f"Available tools: {', '.join(context.available_tools)}\n")
    
    # Generate plan (automatically uses LLM for complex tasks)
    plan = planner.create_plan(goal, context)
    
    # Display plan details
    print(f"Plan ID: {plan.plan_id}")
    print(f"Planning Approach: {plan.planning_approach}")
    print(f"Complexity: {plan.complexity.value}")
    print(f"Status: {plan.status.value}")
    print(f"Estimated Duration: {plan.estimated_duration_seconds}s")
    print(f"Number of Steps: {len(plan.steps)}\n")
    
    # Display steps
    print("Plan Steps:")
    for i, step in enumerate(plan.steps, 1):
        print(f"\n  Step {i}: {step.get('step_id', 'N/A')}")
        print(f"    Description: {step.get('description', 'N/A')}")
        print(f"    Tool: {step.get('tool', 'N/A')}")
        print(f"    Parameters: {json.dumps(step.get('parameters', {}), indent=6)}")
        print(f"    Dependencies: {step.get('dependencies', [])}")
        print(f"    Duration: {step.get('estimated_duration_seconds', 0)}s")
    
    # Display metadata
    print(f"\nMetadata:")
    for key, value in plan.metadata.items():
        print(f"  {key}: {value}")


def example_2_direct_llm_planning():
    """Example 2: Direct LLM planning with custom complexity"""
    print("\n" + "="*60)
    print("Example 2: Direct LLM Planning")
    print("="*60 + "\n")
    
    planner = HybridPlanner(enable_llm_planning=True)
    
    goal = "Research machine learning frameworks and create a comparison report"
    
    context = PlanningContext(
        available_tools=["browser_agent", "file_manager", "llm", "data_processor"]
    )
    
    # Create custom complexity classification
    complexity = ComplexityClassification(
        level=TaskComplexity.COMPLEX,
        requires_llm=True,
        estimated_steps=10,
        confidence=0.95,
        reasoning="Multi-step research and analysis task",
        keywords_matched=["research", "compare", "create"],
        pattern_matches=[],
        multi_step_detected=True,
        dependency_count=3,
        resource_requirements={"network": True, "llm": True, "filesystem": True}
    )
    
    print(f"Goal: {goal}\n")
    print(f"Complexity Classification:")
    print(f"  Level: {complexity.level.value}")
    print(f"  Requires LLM: {complexity.requires_llm}")
    print(f"  Estimated Steps: {complexity.estimated_steps}")
    print(f"  Confidence: {complexity.confidence}")
    print(f"  Reasoning: {complexity.reasoning}\n")
    
    # Generate plan using LLM directly
    plan = planner._generate_llm_plan(goal, context, complexity)
    
    if plan:
        print(f"✓ Plan generated successfully")
        print(f"  Steps: {len(plan.steps)}")
        print(f"  Duration: {plan.estimated_duration_seconds}s")
        print(f"  Approach: {plan.planning_approach}")
    else:
        print("✗ Plan generation failed")


def example_3_prompt_inspection():
    """Example 3: Inspect generated prompt"""
    print("\n" + "="*60)
    print("Example 3: Prompt Inspection")
    print("="*60 + "\n")
    
    planner = HybridPlanner()
    
    goal = "Analyze database schema and suggest optimizations"
    
    context = PlanningContext(
        available_tools=["database_query", "llm", "file_manager"],
        user_preferences={"optimization_focus": "performance"},
        constraints={"max_queries": 50}
    )
    
    complexity = ComplexityClassification(
        level=TaskComplexity.COMPLEX,
        requires_llm=True,
        estimated_steps=6,
        confidence=0.85,
        reasoning="Database analysis requires complex reasoning"
    )
    
    # Generate prompt
    prompt = planner._create_planning_prompt(goal, context, complexity)
    
    print("Generated Prompt:")
    print("-" * 60)
    print(prompt)
    print("-" * 60)


def example_4_mock_llm_response():
    """Example 4: Mock LLM response for testing"""
    print("\n" + "="*60)
    print("Example 4: Mock LLM Response")
    print("="*60 + "\n")
    
    planner = HybridPlanner()
    
    prompt = "**Goal:** Test goal for mock response\n\nGenerate a plan"
    
    context = PlanningContext(
        available_tools=["tool1", "tool2", "tool3"]
    )
    
    # Generate mock response
    response = planner._mock_llm_response(prompt, context)
    
    print("Mock LLM Response:")
    print(json.dumps(response, indent=2))


def example_5_response_parsing():
    """Example 5: Parse LLM response into TaskPlan"""
    print("\n" + "="*60)
    print("Example 5: Response Parsing")
    print("="*60 + "\n")
    
    planner = HybridPlanner()
    
    goal = "Process data and generate report"
    
    complexity = ComplexityClassification(
        level=TaskComplexity.MODERATE,
        requires_llm=True,
        estimated_steps=4,
        confidence=0.8,
        reasoning="Data processing task"
    )
    
    # Simulate LLM response
    llm_response = {
        "goal": goal,
        "steps": [
            {
                "step_id": "step_1",
                "description": "Load data from file",
                "tool": "file_manager",
                "parameters": {"path": "/data/input.csv", "mode": "read"},
                "dependencies": [],
                "estimated_duration_seconds": 5
            },
            {
                "step_id": "step_2",
                "description": "Validate data format",
                "tool": "data_processor",
                "parameters": {"validation_rules": "strict"},
                "dependencies": ["step_1"],
                "estimated_duration_seconds": 10
            },
            {
                "step_id": "step_3",
                "description": "Process and transform data",
                "tool": "data_processor",
                "parameters": {"operation": "transform", "format": "json"},
                "dependencies": ["step_2"],
                "estimated_duration_seconds": 15
            },
            {
                "step_id": "step_4",
                "description": "Generate summary report",
                "tool": "llm",
                "parameters": {"task": "summarize", "output_format": "markdown"},
                "dependencies": ["step_3"],
                "estimated_duration_seconds": 10
            }
        ],
        "estimated_total_duration_seconds": 40,
        "complexity": "moderate",
        "confidence": 0.88
    }
    
    print("LLM Response:")
    print(json.dumps(llm_response, indent=2))
    print()
    
    # Parse response
    plan = planner._parse_llm_response(llm_response, goal, complexity)
    
    if plan:
        print("✓ Parsed successfully into TaskPlan")
        print(f"  Plan ID: {plan.plan_id}")
        print(f"  Steps: {len(plan.steps)}")
        print(f"  Dependencies: {plan.dependencies}")
        print(f"  Metadata: {json.dumps(plan.metadata, indent=2)}")
    else:
        print("✗ Parsing failed")


def example_6_integration_scenarios():
    """Example 6: Various integration scenarios"""
    print("\n" + "="*60)
    print("Example 6: Integration Scenarios")
    print("="*60 + "\n")
    
    planner = HybridPlanner(
        enable_llm_planning=True,
        enable_rule_based_planning=True,
        llm_fallback_enabled=True
    )
    
    scenarios = [
        {
            "name": "Code Analysis",
            "goal": "Analyze Python files and identify security vulnerabilities",
            "tools": ["file_manager", "code_analyzer", "security_scanner", "llm"]
        },
        {
            "name": "Research Task",
            "goal": "Research best practices for API design and create guidelines",
            "tools": ["browser_agent", "llm", "file_manager"]
        },
        {
            "name": "Data Pipeline",
            "goal": "Build ETL pipeline to process user data and generate insights",
            "tools": ["database_query", "data_processor", "llm", "file_manager"]
        },
        {
            "name": "Documentation",
            "goal": "Generate comprehensive API documentation from code",
            "tools": ["file_manager", "code_analyzer", "llm"]
        }
    ]
    
    for scenario in scenarios:
        print(f"\nScenario: {scenario['name']}")
        print(f"Goal: {scenario['goal']}")
        
        context = PlanningContext(
            available_tools=scenario['tools']
        )
        
        plan = planner.create_plan(scenario['goal'], context)
        
        print(f"  ✓ Plan created: {len(plan.steps)} steps, {plan.planning_approach} approach")


def example_7_error_handling():
    """Example 7: Error handling scenarios"""
    print("\n" + "="*60)
    print("Example 7: Error Handling")
    print("="*60 + "\n")
    
    planner = HybridPlanner()
    
    # Test 1: Empty steps
    print("Test 1: Empty steps response")
    response_empty = {
        "goal": "Test",
        "steps": [],
        "estimated_total_duration_seconds": 0,
        "complexity": "simple",
        "confidence": 0.5
    }
    
    complexity = ComplexityClassification(
        level=TaskComplexity.SIMPLE,
        requires_llm=False,
        estimated_steps=0,
        confidence=0.5,
        reasoning="Test"
    )
    
    plan = planner._parse_llm_response(response_empty, "Test", complexity)
    print(f"  Result: {'✗ None (expected)' if plan is None else '✓ Plan created'}")
    
    # Test 2: Missing optional fields
    print("\nTest 2: Missing optional fields")
    response_minimal = {
        "goal": "Test",
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
    }
    
    plan = planner._parse_llm_response(response_minimal, "Test", complexity)
    print(f"  Result: {'✓ Plan created with defaults' if plan else '✗ Failed'}")
    
    # Test 3: No tools available
    print("\nTest 3: No tools available")
    context_no_tools = PlanningContext(available_tools=[])
    response = planner._mock_llm_response("**Goal:** Test", context_no_tools)
    print(f"  Result: ✓ Generated {len(response['steps'])} step(s) with generic tool")


def run_all_examples():
    """Run all examples"""
    print("\n" + "="*70)
    print(" LLM-Based Planning Examples")
    print("="*70)
    
    examples = [
        example_1_basic_llm_planning,
        example_2_direct_llm_planning,
        example_3_prompt_inspection,
        example_4_mock_llm_response,
        example_5_response_parsing,
        example_6_integration_scenarios,
        example_7_error_handling
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"\n✗ Example failed: {e}")
    
    print("\n" + "="*70)
    print(" Examples completed")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_all_examples()
