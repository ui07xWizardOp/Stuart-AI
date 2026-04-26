"""
Example usage of HybridPlanner

Demonstrates task complexity classification, plan generation,
validation, and tool selection.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Mock dependencies for standalone execution
mock_span = MagicMock()
mock_span.__enter__ = Mock(return_value=mock_span)
mock_span.__exit__ = Mock(return_value=False)
mock_span.set_attribute = Mock()

mock_tracer = Mock()
mock_tracer.start_span = Mock(return_value=mock_span)

sys.modules['observability'] = MagicMock()
sys.modules['observability'].get_logging_system = Mock(return_value=Mock())
sys.modules['observability'].get_tracing_system = Mock(return_value=mock_tracer)
sys.modules['observability'].get_correlation_id = Mock(return_value="test_correlation_id")
sys.modules['observability'].get_trace_id = Mock(return_value="test_trace_id")

sys.modules['events'] = MagicMock()
sys.modules['events'].get_event_bus = Mock(return_value=Mock())
sys.modules['events'].EventType = MagicMock()
sys.modules['events'].Event = MagicMock()

# Import directly from file
import importlib.util
spec = importlib.util.spec_from_file_location(
    "hybrid_planner",
    Path(__file__).parent / "hybrid_planner.py"
)
hybrid_planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hybrid_planner)

HybridPlanner = hybrid_planner.HybridPlanner
PlanningContext = hybrid_planner.PlanningContext


def example_complexity_classification():
    """Example: Classify task complexity"""
    print("=" * 60)
    print("Example 1: Task Complexity Classification")
    print("=" * 60)
    
    planner = HybridPlanner()
    
    # Test various task types
    tasks = [
        "read file example.txt",
        "search for information about Python",
        "analyze the codebase and suggest refactorings",
        "if the file exists, read it, otherwise create it",
        "debug the authentication issue across multiple services"
    ]
    
    for task in tasks:
        result = planner.classify_task_complexity(task)
        print(f"\nTask: {task}")
        print(f"  Complexity: {result.level.value}")
        print(f"  Requires LLM: {result.requires_llm}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Estimated Steps: {result.estimated_steps}")
        print(f"  Keywords: {', '.join(result.keywords_matched)}")
        print(f"  Reasoning: {result.reasoning}")


def example_tool_selection():
    """Example: Select appropriate tools for tasks"""
    print("\n" + "=" * 60)
    print("Example 2: Tool Selection")
    print("=" * 60)
    
    planner = HybridPlanner()
    
    available_tools = [
        "file_manager",
        "browser_agent",
        "llm",
        "knowledge_manager",
        "python_executor"
    ]
    
    task_steps = [
        {"action": "read_file", "param": "config.json"},
        {"action": "search_web", "param": "latest Python features"},
        {"action": "execute_code", "param": "data_analysis.py"},
        {"action": "query_knowledge", "param": "machine learning"}
    ]
    
    for step in task_steps:
        selection = planner.select_tool(step, available_tools)
        print(f"\nTask Step: {step['action']}")
        print(f"  Selected Tool: {selection.tool_name}")
        print(f"  Confidence: {selection.confidence:.2f}")
        print(f"  Reasoning: {selection.reasoning}")


def example_plan_templates():
    """Example: Show available plan templates"""
    print("\n" + "=" * 60)
    print("Example 3: Available Plan Templates")
    print("=" * 60)
    
    print("\nThe HybridPlanner includes predefined templates for common tasks:")
    
    for template_name, steps in HybridPlanner.PLAN_TEMPLATES.items():
        print(f"\n{template_name}:")
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step['tool']} - {step['action']}")


def example_planning_context():
    """Example: Create and use planning context"""
    print("\n" + "=" * 60)
    print("Example 4: Planning Context")
    print("=" * 60)
    
    # Create a planning context with available tools and constraints
    context = PlanningContext(
        available_tools=[
            "file_manager",
            "browser_agent",
            "llm",
            "knowledge_manager"
        ],
        user_preferences={
            "verbose": True,
            "auto_approve_low_risk": True
        },
        execution_history=[
            {"task": "read_file", "success": True, "duration": 0.5}
        ],
        constraints={
            "max_steps": 10,
            "max_duration": 300,
            "allowed_tools": ["file_manager", "llm"]
        },
        session_context={
            "user_id": "user_123",
            "session_id": "session_456"
        }
    )
    
    print("\nPlanning Context:")
    print(f"  Available Tools: {', '.join(context.available_tools)}")
    print(f"  User Preferences: {context.user_preferences}")
    print(f"  Constraints: {context.constraints}")
    print(f"  Session Context: {context.session_context}")
    
    # Convert to dictionary for serialization
    context_dict = context.to_dict()
    print(f"\n  Serialized: {len(str(context_dict))} characters")


def example_planner_configuration():
    """Example: Configure planner with different settings"""
    print("\n" + "=" * 60)
    print("Example 5: Planner Configuration")
    print("=" * 60)
    
    # Configuration 1: LLM-only planning
    planner1 = HybridPlanner(
        enable_llm_planning=True,
        enable_rule_based_planning=False,
        llm_fallback_enabled=False
    )
    print("\nConfiguration 1: LLM-only")
    print(f"  LLM Planning: {planner1.enable_llm_planning}")
    print(f"  Rule-based Planning: {planner1.enable_rule_based_planning}")
    
    # Configuration 2: Rule-based with LLM fallback
    planner2 = HybridPlanner(
        enable_llm_planning=True,
        enable_rule_based_planning=True,
        llm_fallback_enabled=True,
        max_plan_steps=15,
        max_repair_attempts=5
    )
    print("\nConfiguration 2: Hybrid with fallback")
    print(f"  LLM Planning: {planner2.enable_llm_planning}")
    print(f"  Rule-based Planning: {planner2.enable_rule_based_planning}")
    print(f"  LLM Fallback: {planner2.llm_fallback_enabled}")
    print(f"  Max Plan Steps: {planner2.max_plan_steps}")
    print(f"  Max Repair Attempts: {planner2.max_repair_attempts}")
    
    # Configuration 3: Rule-based only
    planner3 = HybridPlanner(
        enable_llm_planning=False,
        enable_rule_based_planning=True,
        llm_fallback_enabled=False
    )
    print("\nConfiguration 3: Rule-based only")
    print(f"  LLM Planning: {planner3.enable_llm_planning}")
    print(f"  Rule-based Planning: {planner3.enable_rule_based_planning}")


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("HybridPlanner Usage Examples")
    print("=" * 60)
    
    example_complexity_classification()
    example_tool_selection()
    example_plan_templates()
    example_planning_context()
    example_planner_configuration()
    
    print("\n" + "=" * 60)
    print("Examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
