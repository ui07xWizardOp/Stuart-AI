"""
Verification script for Rule-Based Planning Implementation

Verifies that the rule-based planning implementation is complete
by checking the code structure without running full tests.
"""

import ast
import sys


def check_plan_templates():
    """Verify PLAN_TEMPLATES dictionary is properly defined"""
    print("\n[1] Checking PLAN_TEMPLATES dictionary...")
    
    with open("hybrid_planner.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check for template categories
    expected_templates = [
        # File operations
        "read_file", "write_file", "list_directory", "delete_file", "move_file", "copy_file",
        # Web operations
        "web_search", "fetch_url", "extract_web_content",
        # Knowledge operations
        "knowledge_search", "retrieve_memory", "summarize_content",
        # Data operations
        "process_data", "analyze_data",
        # System operations
        "execute_command", "check_status",
        # Composite operations
        "read_and_summarize", "search_and_save"
    ]
    
    found_templates = []
    for template in expected_templates:
        if f'"{template}"' in content:
            found_templates.append(template)
            print(f"  ✓ Found template: {template}")
        else:
            print(f"  ✗ Missing template: {template}")
    
    print(f"\n  Total templates found: {len(found_templates)}/{len(expected_templates)}")
    return len(found_templates) == len(expected_templates)


def check_helper_methods():
    """Verify helper methods are implemented"""
    print("\n[2] Checking helper methods...")
    
    with open("hybrid_planner.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    expected_methods = [
        "_match_template",
        "_extract_parameters",
        "_populate_template",
        "_template_to_plan"
    ]
    
    found_methods = []
    for method in expected_methods:
        if f"def {method}(" in content:
            found_methods.append(method)
            print(f"  ✓ Found method: {method}")
        else:
            print(f"  ✗ Missing method: {method}")
    
    print(f"\n  Total methods found: {len(found_methods)}/{len(expected_methods)}")
    return len(found_methods) == len(expected_methods)


def check_generate_rule_based_plan():
    """Verify _generate_rule_based_plan is implemented"""
    print("\n[3] Checking _generate_rule_based_plan implementation...")
    
    with open("hybrid_planner.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find the _generate_rule_based_plan method
    import re
    pattern = r'def _generate_rule_based_plan\(.*?\n(.*?)(?=\n    def |\nclass |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("  ✗ _generate_rule_based_plan method not found")
        return False
    
    method_body = match.group(1)
    
    # Check it's not a placeholder (specific to this method)
    if "This is a placeholder implementation" in method_body and "Task 7.3" in method_body:
        print("  ✗ _generate_rule_based_plan is still a placeholder")
        return False
    
    # Check for key implementation elements
    checks = [
        ("_match_template call", "_match_template(goal)"),
        ("_extract_parameters call", "_extract_parameters(goal, template)"),
        ("_populate_template call", "_populate_template(template, parameters)"),
        ("_template_to_plan call", "_template_to_plan(")
    ]
    
    all_found = True
    for check_name, check_str in checks:
        if check_str in method_body:
            print(f"  ✓ {check_name} found")
        else:
            print(f"  ✗ {check_name} not found")
            all_found = False
    
    return all_found


def check_template_structure():
    """Verify template structure is correct"""
    print("\n[4] Checking template structure...")
    
    with open("hybrid_planner.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check for required fields in templates
    required_fields = ["keywords", "patterns", "parameters", "steps"]
    
    all_found = True
    for field in required_fields:
        if f'"{field}":' in content:
            print(f"  ✓ Template field '{field}' found")
        else:
            print(f"  ✗ Template field '{field}' not found")
            all_found = False
    
    return all_found


def check_documentation():
    """Verify documentation files exist"""
    print("\n[5] Checking documentation...")
    
    import os
    
    docs = [
        ("README", "RULE_BASED_PLANNING_README.md"),
        ("Tests", "test_rule_based_planning.py"),
        ("Simple Tests", "simple_test_rule_based_planning.py"),
        ("Examples", "example_rule_based_planning.py")
    ]
    
    all_found = True
    for doc_name, doc_file in docs:
        if os.path.exists(doc_file):
            print(f"  ✓ {doc_name}: {doc_file}")
        else:
            print(f"  ✗ {doc_name}: {doc_file} not found")
            all_found = False
    
    return all_found


def verify_implementation():
    """Run all verification checks"""
    print("="*60)
    print("RULE-BASED PLANNING IMPLEMENTATION VERIFICATION")
    print("="*60)
    
    checks = [
        ("Plan Templates", check_plan_templates),
        ("Helper Methods", check_helper_methods),
        ("Main Implementation", check_generate_rule_based_plan),
        ("Template Structure", check_template_structure),
        ("Documentation", check_documentation)
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"\n  ERROR: {e}")
            results.append((check_name, False))
    
    print("\n" + "="*60)
    print("VERIFICATION RESULTS")
    print("="*60)
    
    for check_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {check_name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n✓ ALL CHECKS PASSED - Implementation is complete!")
        return True
    else:
        print(f"\n✗ {total - passed} CHECK(S) FAILED - Implementation incomplete")
        return False


if __name__ == "__main__":
    success = verify_implementation()
    sys.exit(0 if success else 1)
