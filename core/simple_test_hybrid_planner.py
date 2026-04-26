"""
Simple standalone test for HybridPlanner

Tests basic functionality without requiring full environment setup.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Mock the dependencies before any imports
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

# Import directly from the file, not through the package
import importlib.util
spec = importlib.util.spec_from_file_location(
    "hybrid_planner",
    Path(__file__).parent / "hybrid_planner.py"
)
hybrid_planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hybrid_planner)

# Extract classes
HybridPlanner = hybrid_planner.HybridPlanner
TaskComplexity = hybrid_planner.TaskComplexity
PlanStatus = hybrid_planner.PlanStatus
ComplexityClassification = hybrid_planner.ComplexityClassification
TaskPlan = hybrid_planner.TaskPlan
PlanningContext = hybrid_planner.PlanningContext
ToolSelection = hybrid_planner.ToolSelection
ValidationResult = hybrid_planner.ValidationResult
PlanError = hybrid_planner.PlanError


def test_planner_initialization():
    """Test that HybridPlanner initializes correctly"""
    print("Testing planner initialization...")
    
    planner = HybridPlanner(
        enable_llm_planning=True,
        enable_rule_based_planning=True,
        llm_fallback_enabled=True,
        max_plan_steps=20,
        max_repair_attempts=3
    )
    
    assert planner.enable_llm_planning is True
    assert planner.enable_rule_based_planning is True
    assert planner.llm_fallback_enabled is True
    assert planner.max_plan_steps == 20
    assert planner.max_repair_attempts == 3
    
    print("✓ Planner initialization test passed")


def test_complexity_classification_simple():
    """Test classification of simple tasks"""
    print("Testing simple task classification...")
    
    planner = HybridPlanner()
    goal = "read file example.txt"
    
    result = planner.classify_task_complexity(goal)
    
    assert result.level == TaskComplexity.SIMPLE
    assert result.requires_llm is False
    assert result.confidence >= 0.8
    assert "read" in result.keywords_matched
    
    print(f"✓ Simple task classified correctly: {result.level.value}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Keywords: {result.keywords_matched}")


def test_complexity_classification_complex():
    """Test classification of complex tasks"""
    print("\nTesting complex task classification...")
    
    planner = HybridPlanner()
    goal = "analyze the codebase and suggest refactorings for better performance"
    
    result = planner.classify_task_complexity(goal)
    
    assert result.level == TaskComplexity.COMPLEX
    assert result.requires_llm is True
    assert result.confidence >= 0.7
    
    print(f"✓ Complex task classified correctly: {result.level.value}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Keywords: {result.keywords_matched}")


def test_complexity_classification_moderate():
    """Test classification of moderate tasks"""
    print("\nTesting moderate task classification...")
    
    planner = HybridPlanner()
    goal = "if the file exists, read it and summarize, otherwise create it"
    
    result = planner.classify_task_complexity(goal)
    
    # Enhanced classification may classify this as complex due to conditional logic
    assert result.level in [TaskComplexity.MODERATE, TaskComplexity.COMPLEX]
    assert result.requires_llm is True
    
    print(f"✓ Task classified correctly: {result.level.value}")
    print(f"  Reasoning: {result.reasoning}")


def test_tool_selection():
    """Test tool selection functionality"""
    print("\nTesting tool selection...")
    
    planner = HybridPlanner()
    task_step = {"action": "read_file", "param": "test.txt"}
    available_tools = ["file_manager", "browser_agent", "llm"]
    
    selection = planner.select_tool(task_step, available_tools)
    
    assert isinstance(selection, ToolSelection)
    assert selection.tool_name in available_tools
    assert 0.0 <= selection.confidence <= 1.0
    
    print(f"✓ Tool selected: {selection.tool_name}")
    print(f"  Confidence: {selection.confidence}")


def test_dataclass_serialization():
    """Test dataclass to_dict methods"""
    print("\nTesting dataclass serialization...")
    
    # Test ComplexityClassification
    classification = ComplexityClassification(
        level=TaskComplexity.SIMPLE,
        requires_llm=False,
        estimated_steps=2,
        confidence=0.9,
        reasoning="Test reasoning",
        keywords_matched=["read"]
    )
    data = classification.to_dict()
    assert data["level"] == "simple"
    assert data["confidence"] == 0.9
    
    # Test TaskPlan
    plan = TaskPlan(
        plan_id="test_plan",
        goal="test goal",
        steps=[{"tool": "file_manager"}],
        complexity=TaskComplexity.MODERATE,
        planning_approach="rule_based"
    )
    data = plan.to_dict()
    assert data["plan_id"] == "test_plan"
    assert data["complexity"] == "moderate"
    
    # Test ToolSelection
    selection = ToolSelection(
        tool_name="file_manager",
        confidence=0.85,
        reasoning="Best match"
    )
    data = selection.to_dict()
    assert data["tool_name"] == "file_manager"
    assert data["confidence"] == 0.85
    
    print("✓ All dataclass serialization tests passed")


def test_plan_templates():
    """Test that plan templates are defined"""
    print("\nTesting plan templates...")
    
    assert "read_and_summarize" in HybridPlanner.PLAN_TEMPLATES
    assert "web_search" in HybridPlanner.PLAN_TEMPLATES
    assert "file_operation" in HybridPlanner.PLAN_TEMPLATES
    assert "knowledge_search" in HybridPlanner.PLAN_TEMPLATES
    
    print(f"✓ Found {len(HybridPlanner.PLAN_TEMPLATES)} plan templates")
    for template_name in HybridPlanner.PLAN_TEMPLATES.keys():
        print(f"  - {template_name}")


def test_complexity_keywords():
    """Test that complexity keywords are defined"""
    print("\nTesting complexity keywords...")
    
    assert len(HybridPlanner.SIMPLE_TASK_KEYWORDS) > 0
    assert len(HybridPlanner.COMPLEX_TASK_KEYWORDS) > 0
    
    # Keywords are now dictionaries with weights
    simple_keywords = list(HybridPlanner.SIMPLE_TASK_KEYWORDS.keys())
    complex_keywords = list(HybridPlanner.COMPLEX_TASK_KEYWORDS.keys())
    
    print(f"✓ Simple task keywords: {len(HybridPlanner.SIMPLE_TASK_KEYWORDS)}")
    print(f"  Examples: {', '.join(simple_keywords[:5])}")
    print(f"✓ Complex task keywords: {len(HybridPlanner.COMPLEX_TASK_KEYWORDS)}")
    print(f"  Examples: {', '.join(complex_keywords[:5])}")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("Running HybridPlanner Simple Tests")
    print("=" * 60)
    
    try:
        test_planner_initialization()
        test_complexity_classification_simple()
        test_complexity_classification_complex()
        test_complexity_classification_moderate()
        test_tool_selection()
        test_dataclass_serialization()
        test_plan_templates()
        test_complexity_keywords()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
