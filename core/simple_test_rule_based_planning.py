"""
Simple standalone tests for Rule-Based Planning

Tests the rule-based planning functionality without requiring
full system dependencies.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Initialize required systems before importing HybridPlanner
from observability import initialize_logging, initialize_tracing
from events import initialize_event_bus

# Initialize with minimal configuration
initialize_logging(log_level="ERROR", enable_console_output=False)
initialize_tracing(enable_tracing=False)
initialize_event_bus(enable_persistence=False, enable_ordering=False)


def test_template_library():
    """Test that template library is properly defined"""
    from hybrid_planner import HybridPlanner
    
    planner = HybridPlanner()
    
    # Check template library exists
    assert hasattr(planner, 'PLAN_TEMPLATES')
    assert len(planner.PLAN_TEMPLATES) > 0
    
    print(f"✓ Template library has {len(planner.PLAN_TEMPLATES)} templates")
    
    # Check all templates have required fields
    required_fields = ["keywords", "patterns", "parameters", "steps"]
    for template_name, template in planner.PLAN_TEMPLATES.items():
        for field in required_fields:
            assert field in template, f"Template {template_name} missing {field}"
    
    print(f"✓ All templates have required fields")
    
    # Check template categories
    file_ops = ["read_file", "write_file", "list_directory", "delete_file", "move_file", "copy_file"]
    web_ops = ["web_search", "fetch_url", "extract_web_content"]
    knowledge_ops = ["knowledge_search", "retrieve_memory", "summarize_content"]
    data_ops = ["process_data", "analyze_data"]
    system_ops = ["execute_command", "check_status"]
    composite_ops = ["read_and_summarize", "search_and_save"]
    
    all_expected = file_ops + web_ops + knowledge_ops + data_ops + system_ops + composite_ops
    
    for template_name in all_expected:
        assert template_name in planner.PLAN_TEMPLATES, f"Missing template: {template_name}"
    
    print(f"✓ All expected templates present:")
    print(f"  - File operations: {len(file_ops)}")
    print(f"  - Web operations: {len(web_ops)}")
    print(f"  - Knowledge operations: {len(knowledge_ops)}")
    print(f"  - Data operations: {len(data_ops)}")
    print(f"  - System operations: {len(system_ops)}")
    print(f"  - Composite operations: {len(composite_ops)}")


def test_template_matching():
    """Test template matching functionality"""
    from hybrid_planner import HybridPlanner
    
    planner = HybridPlanner()
    
    # Test cases: (goal, expected_template)
    test_cases = [
        ("read file test.txt", "read_file"),
        ("write to file output.txt", "write_file"),
        ("list files in /home/user", "list_directory"),
        ("search for python tutorials", "web_search"),
        ("fetch url https://example.com", "fetch_url"),
        ("read and summarize document.pdf", "read_and_summarize"),
    ]
    
    print("\n✓ Testing template matching:")
    for goal, expected_template in test_cases:
        match = planner._match_template(goal)
        assert match is not None, f"No match for: {goal}"
        
        template_name, template, confidence = match
        assert template_name == expected_template, \
            f"Expected {expected_template}, got {template_name} for: {goal}"
        assert confidence >= 0.3, f"Confidence too low: {confidence}"
        
        print(f"  ✓ '{goal}' → {template_name} (confidence: {confidence:.2f})")
    
    # Test no match for complex task
    complex_goal = "analyze the codebase and generate comprehensive report with recommendations"
    match = planner._match_template(complex_goal)
    assert match is None, "Complex task should not match any template"
    print(f"  ✓ Complex task correctly returns no match")


def test_parameter_extraction():
    """Test parameter extraction from goals"""
    from hybrid_planner import HybridPlanner
    
    planner = HybridPlanner()
    
    print("\n✓ Testing parameter extraction:")
    
    # Test file path extraction
    goal = "read file test.txt"
    template = planner.PLAN_TEMPLATES["read_file"]
    params = planner._extract_parameters(goal, template)
    assert "file_path" in params
    assert params["file_path"] == "test.txt"
    print(f"  ✓ Extracted file_path: {params['file_path']}")
    
    # Test quoted path extraction
    goal = 'read file "my document.txt"'
    params = planner._extract_parameters(goal, template)
    assert params["file_path"] == "my document.txt"
    print(f"  ✓ Extracted quoted path: {params['file_path']}")
    
    # Test URL extraction
    goal = "fetch url https://example.com/page"
    template = planner.PLAN_TEMPLATES["fetch_url"]
    params = planner._extract_parameters(goal, template)
    assert "url" in params
    assert params["url"] == "https://example.com/page"
    print(f"  ✓ Extracted URL: {params['url']}")
    
    # Test query extraction
    goal = "search for machine learning tutorials"
    template = planner.PLAN_TEMPLATES["web_search"]
    params = planner._extract_parameters(goal, template)
    assert "query" in params
    assert "machine learning tutorials" in params["query"]
    print(f"  ✓ Extracted query: {params['query']}")
    
    # Test multiple parameters
    goal = "move file source.txt to destination.txt"
    template = planner.PLAN_TEMPLATES["move_file"]
    params = planner._extract_parameters(goal, template)
    assert "source_path" in params
    assert "destination_path" in params
    assert params["source_path"] == "source.txt"
    assert params["destination_path"] == "destination.txt"
    print(f"  ✓ Extracted multiple params: {params['source_path']} → {params['destination_path']}")


def test_template_population():
    """Test template population with parameters"""
    from hybrid_planner import HybridPlanner
    
    planner = HybridPlanner()
    
    print("\n✓ Testing template population:")
    
    # Test simple template
    template = planner.PLAN_TEMPLATES["read_file"]
    parameters = {"file_path": "test.txt"}
    steps = planner._populate_template(template, parameters)
    
    assert len(steps) == 1
    assert steps[0]["tool"] == "file_manager"
    assert steps[0]["action"] == "read"
    assert steps[0]["param_value"] == "test.txt"
    print(f"  ✓ Populated simple template: {steps[0]['tool']}.{steps[0]['action']}({steps[0]['param_value']})")
    
    # Test multi-step template
    template = planner.PLAN_TEMPLATES["write_file"]
    parameters = {"file_path": "output.txt", "content": "Hello World"}
    steps = planner._populate_template(template, parameters)
    
    assert len(steps) == 2
    assert steps[0]["action"] == "validate_path"
    assert steps[1]["action"] == "write"
    assert steps[1]["param_value"] == "output.txt"
    print(f"  ✓ Populated multi-step template: {len(steps)} steps")


def test_plan_generation():
    """Test complete plan generation"""
    from hybrid_planner import HybridPlanner, PlanningContext, TaskComplexity
    
    planner = HybridPlanner()
    
    print("\n✓ Testing plan generation:")
    
    # Test read file plan
    goal = "read file test.txt"
    context = PlanningContext(available_tools=["file_manager"])
    complexity = planner.classify_task_complexity(goal)
    
    plan = planner._generate_rule_based_plan(goal, context, complexity)
    
    assert plan is not None
    assert plan.goal == goal
    assert plan.planning_approach == "rule_based"
    assert len(plan.steps) == 1
    assert plan.metadata["template_name"] == "read_file"
    assert "file_path" in plan.metadata["parameters"]
    print(f"  ✓ Generated plan for: {goal}")
    print(f"    - Plan ID: {plan.plan_id}")
    print(f"    - Steps: {len(plan.steps)}")
    print(f"    - Template: {plan.metadata['template_name']}")
    
    # Test composite operation plan
    goal = "read and summarize document.pdf"
    complexity = planner.classify_task_complexity(goal)
    plan = planner._generate_rule_based_plan(goal, context, complexity)
    
    assert plan is not None
    assert len(plan.steps) == 2
    assert plan.steps[0]["tool"] == "file_manager"
    assert plan.steps[1]["tool"] == "llm"
    print(f"  ✓ Generated composite plan: {len(plan.steps)} steps")


def test_case_insensitivity():
    """Test that matching is case insensitive"""
    from hybrid_planner import HybridPlanner
    
    planner = HybridPlanner()
    
    print("\n✓ Testing case insensitivity:")
    
    goals = [
        "read file test.txt",
        "READ FILE TEST.TXT",
        "Read File Test.txt"
    ]
    
    matches = [planner._match_template(goal) for goal in goals]
    
    # All should match
    assert all(m is not None for m in matches)
    
    # All should match same template
    template_names = [m[0] for m in matches]
    assert len(set(template_names)) == 1
    
    print(f"  ✓ All case variations matched: {template_names[0]}")


def test_confidence_scoring():
    """Test confidence scoring for matches"""
    from hybrid_planner import HybridPlanner
    
    planner = HybridPlanner()
    
    print("\n✓ Testing confidence scoring:")
    
    # Strong match (pattern + keywords)
    goal1 = "read file test.txt"
    match1 = planner._match_template(goal1)
    assert match1 is not None
    confidence1 = match1[2]
    
    # Weaker match (keywords only)
    goal2 = "show me something"
    match2 = planner._match_template(goal2)
    
    if match2:
        confidence2 = match2[2]
        print(f"  ✓ Strong match confidence: {confidence1:.2f}")
        print(f"  ✓ Weak match confidence: {confidence2:.2f}")
    else:
        print(f"  ✓ Strong match confidence: {confidence1:.2f}")
        print(f"  ✓ Weak match correctly rejected")


def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("RULE-BASED PLANNING TESTS")
    print("="*60)
    
    tests = [
        ("Template Library", test_template_library),
        ("Template Matching", test_template_matching),
        ("Parameter Extraction", test_parameter_extraction),
        ("Template Population", test_template_population),
        ("Plan Generation", test_plan_generation),
        ("Case Insensitivity", test_case_insensitivity),
        ("Confidence Scoring", test_confidence_scoring),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*60}")
            print(f"TEST: {test_name}")
            print(f"{'='*60}")
            test_func()
            passed += 1
            print(f"\n✓ {test_name} PASSED")
        except AssertionError as e:
            failed += 1
            print(f"\n✗ {test_name} FAILED: {e}")
        except Exception as e:
            failed += 1
            print(f"\n✗ {test_name} ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"TEST RESULTS")
    print(f"{'='*60}")
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n✓ ALL TESTS PASSED")
    else:
        print(f"\n✗ {failed} TEST(S) FAILED")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
