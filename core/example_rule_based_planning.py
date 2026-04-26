"""
Example: Rule-Based Planning with Templates

Demonstrates how the HybridPlanner uses rule-based templates to generate
plans for common tasks without requiring LLM calls.
"""

from hybrid_planner import HybridPlanner, PlanningContext
import json


def print_plan(plan):
    """Pretty print a task plan"""
    print(f"\n{'='*60}")
    print(f"Plan ID: {plan.plan_id}")
    print(f"Goal: {plan.goal}")
    print(f"Complexity: {plan.complexity.value}")
    print(f"Planning Approach: {plan.planning_approach}")
    print(f"Status: {plan.status.value}")
    print(f"Estimated Duration: {plan.estimated_duration_seconds}s")
    print(f"\nMetadata:")
    print(f"  Template: {plan.metadata.get('template_name', 'N/A')}")
    print(f"  Match Confidence: {plan.metadata.get('match_confidence', 'N/A'):.2f}")
    print(f"  Parameters: {plan.metadata.get('parameters', {})}")
    print(f"\nSteps ({len(plan.steps)}):")
    for i, step in enumerate(plan.steps, 1):
        print(f"  {i}. {step['tool']}.{step['action']}")
        print(f"     Description: {step['description']}")
        if 'param_value' in step:
            print(f"     Parameter: {step['param_value']}")
    print(f"{'='*60}\n")


def example_file_operations():
    """Example: File operation templates"""
    print("\n" + "="*60)
    print("EXAMPLE 1: File Operations")
    print("="*60)
    
    planner = HybridPlanner(
        enable_llm_planning=False,  # Only use rule-based
        enable_rule_based_planning=True
    )
    
    context = PlanningContext(
        available_tools=["file_manager", "llm"]
    )
    
    # Example 1: Read file
    print("\n1. Read File:")
    goal = "read file /home/user/document.txt"
    plan = planner.create_plan(goal, context)
    print_plan(plan)
    
    # Example 2: Write file
    print("\n2. Write File:")
    goal = "write to file output.txt"
    plan = planner.create_plan(goal, context)
    print_plan(plan)
    
    # Example 3: List directory
    print("\n3. List Directory:")
    goal = "list files in /home/user/projects"
    plan = planner.create_plan(goal, context)
    print_plan(plan)
    
    # Example 4: Move file
    print("\n4. Move File:")
    goal = "move file source.txt to destination.txt"
    plan = planner.create_plan(goal, context)
    print_plan(plan)


def example_web_operations():
    """Example: Web operation templates"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Web Operations")
    print("="*60)
    
    planner = HybridPlanner(
        enable_llm_planning=False,
        enable_rule_based_planning=True
    )
    
    context = PlanningContext(
        available_tools=["browser_agent"]
    )
    
    # Example 1: Web search
    print("\n1. Web Search:")
    goal = "search for python machine learning tutorials"
    plan = planner.create_plan(goal, context)
    print_plan(plan)
    
    # Example 2: Fetch URL
    print("\n2. Fetch URL:")
    goal = "fetch url https://example.com/api/data"
    plan = planner.create_plan(goal, context)
    print_plan(plan)
    
    # Example 3: Extract content
    print("\n3. Extract Web Content:")
    goal = "extract content from https://example.com using selector .article"
    plan = planner.create_plan(goal, context)
    print_plan(plan)


def example_knowledge_operations():
    """Example: Knowledge operation templates"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Knowledge Operations")
    print("="*60)
    
    planner = HybridPlanner(
        enable_llm_planning=False,
        enable_rule_based_planning=True
    )
    
    context = PlanningContext(
        available_tools=["knowledge_manager", "memory_system", "llm"]
    )
    
    # Example 1: Knowledge search
    print("\n1. Knowledge Search:")
    goal = "search knowledge base for machine learning concepts"
    plan = planner.create_plan(goal, context)
    print_plan(plan)
    
    # Example 2: Retrieve memory
    print("\n2. Retrieve Memory:")
    goal = "remember what we discussed about project deadlines"
    plan = planner.create_plan(goal, context)
    print_plan(plan)
    
    # Example 3: Summarize content
    print("\n3. Summarize Content:")
    goal = "summarize this long article"
    plan = planner.create_plan(goal, context)
    print_plan(plan)


def example_composite_operations():
    """Example: Composite operation templates"""
    print("\n" + "="*60)
    print("EXAMPLE 4: Composite Operations")
    print("="*60)
    
    planner = HybridPlanner(
        enable_llm_planning=False,
        enable_rule_based_planning=True
    )
    
    context = PlanningContext(
        available_tools=["file_manager", "browser_agent", "llm"]
    )
    
    # Example 1: Read and summarize
    print("\n1. Read and Summarize:")
    goal = "read and summarize document.pdf"
    plan = planner.create_plan(goal, context)
    print_plan(plan)
    
    # Example 2: Search and save
    print("\n2. Search and Save:")
    goal = "search for AI news and save to results.txt"
    plan = planner.create_plan(goal, context)
    print_plan(plan)


def example_template_matching():
    """Example: Template matching with different phrasings"""
    print("\n" + "="*60)
    print("EXAMPLE 5: Template Matching Variations")
    print("="*60)
    
    planner = HybridPlanner(
        enable_llm_planning=False,
        enable_rule_based_planning=True
    )
    
    context = PlanningContext(
        available_tools=["file_manager"]
    )
    
    # Different ways to express the same intent
    variations = [
        "read file test.txt",
        "open test.txt",
        "show me test.txt",
        "cat test.txt",
        "display the file test.txt"
    ]
    
    print("\nDifferent phrasings for reading a file:")
    for goal in variations:
        match = planner._match_template(goal)
        if match:
            template_name, template, confidence = match
            print(f"\n  Goal: '{goal}'")
            print(f"  → Matched: {template_name} (confidence: {confidence:.2f})")
        else:
            print(f"\n  Goal: '{goal}'")
            print(f"  → No match")


def example_parameter_extraction():
    """Example: Parameter extraction from natural language"""
    print("\n" + "="*60)
    print("EXAMPLE 6: Parameter Extraction")
    print("="*60)
    
    planner = HybridPlanner()
    
    test_cases = [
        ("read file test.txt", "read_file"),
        ('read file "my document.txt"', "read_file"),
        ("search for machine learning tutorials", "web_search"),
        ("move file source.txt to destination.txt", "move_file"),
        ("fetch url https://example.com/api", "fetch_url"),
    ]
    
    print("\nParameter extraction examples:")
    for goal, template_name in test_cases:
        template = planner.PLAN_TEMPLATES[template_name]
        params = planner._extract_parameters(goal, template)
        print(f"\n  Goal: '{goal}'")
        print(f"  Template: {template_name}")
        print(f"  Extracted parameters:")
        for param_name, param_value in params.items():
            print(f"    - {param_name}: {param_value}")


def example_fallback_behavior():
    """Example: Fallback when no template matches"""
    print("\n" + "="*60)
    print("EXAMPLE 7: Fallback Behavior")
    print("="*60)
    
    planner = HybridPlanner(
        enable_llm_planning=False,  # LLM disabled
        enable_rule_based_planning=True,
        llm_fallback_enabled=False  # Fallback disabled
    )
    
    context = PlanningContext(
        available_tools=["file_manager", "browser_agent"]
    )
    
    # Complex task that won't match any template
    goal = "analyze the codebase and generate a comprehensive report with recommendations"
    
    print(f"\nGoal: '{goal}'")
    print("\nAttempting rule-based planning...")
    
    try:
        plan = planner.create_plan(goal, context)
        print("Plan created (unexpected)")
    except ValueError as e:
        print(f"Failed as expected: {e}")
        print("\nThis task is too complex for rule-based templates.")
        print("Would require LLM-based planning.")


def example_template_library():
    """Example: Browse available templates"""
    print("\n" + "="*60)
    print("EXAMPLE 8: Template Library")
    print("="*60)
    
    planner = HybridPlanner()
    
    print(f"\nTotal templates available: {len(planner.PLAN_TEMPLATES)}")
    
    # Group templates by category
    categories = {
        "File Operations": [],
        "Web Operations": [],
        "Knowledge Operations": [],
        "Data Operations": [],
        "System Operations": [],
        "Composite Operations": []
    }
    
    for template_name, template in planner.PLAN_TEMPLATES.items():
        steps = template.get("steps", [])
        if not steps:
            continue
        
        primary_tool = steps[0]["tool"]
        
        if primary_tool == "file_manager":
            if len(steps) > 1 and steps[1]["tool"] != "file_manager":
                categories["Composite Operations"].append(template_name)
            else:
                categories["File Operations"].append(template_name)
        elif primary_tool == "browser_agent":
            if len(steps) > 2:
                categories["Composite Operations"].append(template_name)
            else:
                categories["Web Operations"].append(template_name)
        elif primary_tool in ["knowledge_manager", "memory_system", "llm"]:
            categories["Knowledge Operations"].append(template_name)
        elif primary_tool == "data_processor":
            categories["Data Operations"].append(template_name)
        elif primary_tool in ["system_executor", "system_monitor"]:
            categories["System Operations"].append(template_name)
    
    for category, templates in categories.items():
        if templates:
            print(f"\n{category}:")
            for template_name in sorted(templates):
                template = planner.PLAN_TEMPLATES[template_name]
                keywords = template.get("keywords", [])
                print(f"  - {template_name}")
                print(f"    Keywords: {', '.join(keywords[:3])}...")
                print(f"    Steps: {len(template.get('steps', []))}")


def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("RULE-BASED PLANNING EXAMPLES")
    print("="*60)
    
    try:
        example_file_operations()
        example_web_operations()
        example_knowledge_operations()
        example_composite_operations()
        example_template_matching()
        example_parameter_extraction()
        example_fallback_behavior()
        example_template_library()
        
        print("\n" + "="*60)
        print("ALL EXAMPLES COMPLETED")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
