"""
Example: Enhanced Task Complexity Classification

Demonstrates the enhanced task complexity classification features in HybridPlanner:
- Weighted keyword scoring
- Pattern recognition for common task types
- Multi-step task detection
- Dependency analysis
- Resource requirement estimation
- Confidence calibration based on multiple signals
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Mock dependencies
mock_span = MagicMock()
mock_span.__enter__ = Mock(return_value=mock_span)
mock_span.__exit__ = Mock(return_value=False)
mock_span.set_attribute = Mock()

mock_tracer = Mock()
mock_tracer.start_span = Mock(return_value=mock_span)

sys.modules['observability'] = MagicMock()
sys.modules['observability'].get_logging_system = Mock(return_value=Mock())
sys.modules['observability'].get_tracing_system = Mock(return_value=mock_tracer)
sys.modules['observability'].get_correlation_id = Mock(return_value="example_correlation_id")
sys.modules['observability'].get_trace_id = Mock(return_value="example_trace_id")

sys.modules['events'] = MagicMock()
sys.modules['events'].get_event_bus = Mock(return_value=Mock())
sys.modules['events'].EventType = MagicMock()
sys.modules['events'].Event = MagicMock()

# Import HybridPlanner
import importlib.util
spec = importlib.util.spec_from_file_location(
    "hybrid_planner",
    Path(__file__).parent / "hybrid_planner.py"
)
hybrid_planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hybrid_planner)

HybridPlanner = hybrid_planner.HybridPlanner


def print_classification(goal: str, result):
    """Pretty print classification results"""
    print(f"\nTask: '{goal}'")
    print(f"  Level: {result.level.value}")
    print(f"  Requires LLM: {result.requires_llm}")
    print(f"  Estimated Steps: {result.estimated_steps}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Keywords Matched: {result.keywords_matched}")
    if result.pattern_matches:
        print(f"  Pattern Matches: {result.pattern_matches}")
    print(f"  Multi-Step Detected: {result.multi_step_detected}")
    print(f"  Dependency Count: {result.dependency_count}")
    if result.resource_requirements:
        print(f"  Resource Requirements: {list(result.resource_requirements.keys())}")
    print(f"  Reasoning: {result.reasoning}")


def main():
    """Demonstrate enhanced complexity classification"""
    print("=" * 80)
    print("Enhanced Task Complexity Classification Examples")
    print("=" * 80)
    
    planner = HybridPlanner()
    
    # Example 1: Simple task with pattern match
    print("\n1. SIMPLE TASK WITH PATTERN MATCH")
    print("-" * 80)
    goal = "read file example.txt"
    result = planner.classify_task_complexity(goal)
    print_classification(goal, result)
    
    # Example 2: Complex task with multiple keywords
    print("\n2. COMPLEX TASK WITH MULTIPLE KEYWORDS")
    print("-" * 80)
    goal = "analyze the codebase and suggest refactorings for better performance"
    result = planner.classify_task_complexity(goal)
    print_classification(goal, result)
    
    # Example 3: Multi-step task detection
    print("\n3. MULTI-STEP TASK DETECTION")
    print("-" * 80)
    goal = "read the file and then process the data and save results"
    result = planner.classify_task_complexity(goal)
    print_classification(goal, result)
    
    # Example 4: Task with dependencies
    print("\n4. TASK WITH DEPENDENCIES")
    print("-" * 80)
    goal = "after reading the file, process it, then save results once validation passes"
    result = planner.classify_task_complexity(goal)
    print_classification(goal, result)
    
    # Example 5: Task with conditional logic
    print("\n5. TASK WITH CONDITIONAL LOGIC")
    print("-" * 80)
    goal = "if the file exists, read it and summarize, otherwise create it"
    result = planner.classify_task_complexity(goal)
    print_classification(goal, result)
    
    # Example 6: Task with iteration
    print("\n6. TASK WITH ITERATION")
    print("-" * 80)
    goal = "process each file in the directory and extract metadata"
    result = planner.classify_task_complexity(goal)
    print_classification(goal, result)
    
    # Example 7: Research task
    print("\n7. RESEARCH TASK")
    print("-" * 80)
    goal = "research machine learning algorithms and compare their performance"
    result = planner.classify_task_complexity(goal)
    print_classification(goal, result)
    
    # Example 8: Code analysis task
    print("\n8. CODE ANALYSIS TASK")
    print("-" * 80)
    goal = "analyze code quality in the project"
    result = planner.classify_task_complexity(goal)
    print_classification(goal, result)
    
    # Example 9: Multiple resource requirements
    print("\n9. MULTIPLE RESOURCE REQUIREMENTS")
    print("-" * 80)
    goal = "search the web for documentation, read local files, and query the database"
    result = planner.classify_task_complexity(goal)
    print_classification(goal, result)
    
    # Example 10: Ambiguous task (lower confidence)
    print("\n10. AMBIGUOUS TASK (LOWER CONFIDENCE)")
    print("-" * 80)
    goal = "do something with the data"
    result = planner.classify_task_complexity(goal)
    print_classification(goal, result)
    
    print("\n" + "=" * 80)
    print("Enhanced Features Demonstrated:")
    print("=" * 80)
    print("? Weighted keyword scoring")
    print("? Pattern recognition for common task types")
    print("? Multi-step task detection")
    print("? Dependency analysis")
    print("? Resource requirement estimation")
    print("? Confidence calibration based on multiple signals")
    print("? Improved reasoning explanations")
    print("\n")


if __name__ == "__main__":
    main()
