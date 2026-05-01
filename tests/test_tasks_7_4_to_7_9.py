"""
Tests for Tasks 7.4 - 7.9: LLM Planning, Validation, Repair, Fallback, Tool Selection, Optimization
"""
import sys
from unittest.mock import Mock, MagicMock
from pathlib import Path

# Mock dependencies
mock_span = MagicMock()
mock_span.__enter__ = Mock(return_value=mock_span)
mock_span.__exit__ = Mock(return_value=False)
mock_span.set_attribute = Mock()
mock_tracer = Mock()
mock_tracer.start_span = Mock(return_value=mock_span)



sys.modules['observability'].get_correlation_id = Mock(return_value='test')
sys.modules['observability'].get_trace_id = Mock(return_value='test')

import importlib.util
spec = importlib.util.spec_from_file_location('hybrid_planner', Path(__file__).parent / 'hybrid_planner.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

HybridPlanner = m.HybridPlanner
TaskPlan = m.TaskPlan
TaskComplexity = m.TaskComplexity
PlanStatus = m.PlanStatus
PlanningContext = m.PlanningContext
PlanError = m.PlanError
ValidationResult = m.ValidationResult
ToolSelection = m.ToolSelection


def make_planner():
    return HybridPlanner()


def make_context(tools=None):
    return PlanningContext(available_tools=tools or ['file_manager', 'browser_agent', 'llm'])


# ============================================================
# Task 7.5: Plan Validation
# ============================================================

def test_validate_valid_plan():
    """Valid plan with proper steps and dependencies passes validation"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p1', goal='test',
        steps=[
            {'step_id': 'step_1', 'tool': 'file_manager', 'description': 'Read file', 'dependencies': []},
            {'step_id': 'step_2', 'tool': 'llm', 'description': 'Summarize', 'dependencies': ['step_1']}
        ],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based'
    )
    result = planner.validate_plan(plan, ctx)
    assert result.is_valid, f'Expected valid, got errors: {result.errors}'
    assert result.status == PlanStatus.VALID
    print('PASS: validate_valid_plan')


def test_validate_unavailable_tool():
    """Plan referencing unavailable tool fails validation"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p2', goal='test',
        steps=[{'step_id': 'step_1', 'tool': 'nonexistent_tool', 'description': 'Do something', 'dependencies': []}],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based'
    )
    result = planner.validate_plan(plan, ctx)
    assert not result.is_valid
    assert any('nonexistent_tool' in e for e in result.errors), f'Expected tool error, got: {result.errors}'
    assert len(result.suggestions) > 0, 'Expected suggestions for tool replacement'
    print('PASS: validate_unavailable_tool')


def test_validate_circular_dependency():
    """Plan with circular dependency fails validation"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p3', goal='test',
        steps=[
            {'step_id': 'step_1', 'tool': 'file_manager', 'description': 'A', 'dependencies': ['step_2']},
            {'step_id': 'step_2', 'tool': 'llm', 'description': 'B', 'dependencies': ['step_1']}
        ],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based'
    )
    result = planner.validate_plan(plan, ctx)
    assert not result.is_valid
    assert any('circular' in e.lower() for e in result.errors), f'Expected cycle error, got: {result.errors}'
    print('PASS: validate_circular_dependency')


def test_validate_empty_plan():
    """Empty plan returns INCOMPLETE status"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p4', goal='test', steps=[],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based'
    )
    result = planner.validate_plan(plan, ctx)
    assert not result.is_valid
    assert result.status == PlanStatus.INCOMPLETE
    print('PASS: validate_empty_plan')


def test_validate_invalid_dependency_reference():
    """Plan with dependency on non-existent step fails validation"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p5', goal='test',
        steps=[
            {'step_id': 'step_1', 'tool': 'file_manager', 'description': 'A', 'dependencies': ['step_99']}
        ],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based'
    )
    result = planner.validate_plan(plan, ctx)
    assert not result.is_valid
    assert any('step_99' in e for e in result.errors), f'Expected invalid dep error, got: {result.errors}'
    print('PASS: validate_invalid_dependency_reference')


def test_validate_generic_tools_allowed():
    """Generic tools like 'llm' and 'generic_executor' are allowed even if not in available_tools"""
    planner = make_planner()
    ctx = make_context(tools=['file_manager'])
    plan = TaskPlan(
        plan_id='p6', goal='test',
        steps=[
            {'step_id': 'step_1', 'tool': 'file_manager', 'description': 'Read', 'dependencies': []},
            {'step_id': 'step_2', 'tool': 'llm', 'description': 'Summarize', 'dependencies': ['step_1']}
        ],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based'
    )
    result = planner.validate_plan(plan, ctx)
    assert result.is_valid, f'Expected valid (llm is generic), got: {result.errors}'
    print('PASS: validate_generic_tools_allowed')


# ============================================================
# Task 7.6: Plan Repair
# ============================================================

def test_repair_empty_plan():
    """Repair adds fallback step to empty plan"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p7', goal='test goal', steps=[],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based',
        status=PlanStatus.INVALID
    )
    error = PlanError(error_type='missing_steps', description='No steps')
    repaired = planner.repair_plan(plan, error, ctx)
    assert repaired.status == PlanStatus.REPAIRED
    assert len(repaired.steps) > 0
    assert repaired.steps[0]['tool'] in ctx.available_tools
    print('PASS: repair_empty_plan')


def test_repair_invalid_tool():
    """Repair replaces invalid tool references"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p8', goal='test',
        steps=[{'step_id': 'step_1', 'tool': 'bad_tool', 'description': 'Do something', 'dependencies': []}],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based',
        status=PlanStatus.INVALID
    )
    error = PlanError(error_type='invalid_tool', description='Tool not available')
    repaired = planner.repair_plan(plan, error, ctx)
    assert repaired.status == PlanStatus.REPAIRED
    assert repaired.steps[0]['tool'] in ctx.available_tools
    print('PASS: repair_invalid_tool')


def test_repair_missing_fields():
    """Repair adds missing required fields to steps"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p9', goal='test',
        steps=[{'tool': 'file_manager'}],  # Missing step_id, description, etc.
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based',
        status=PlanStatus.INVALID
    )
    error = PlanError(error_type='missing_fields', description='Missing required fields')
    repaired = planner.repair_plan(plan, error, ctx)
    assert repaired.status == PlanStatus.REPAIRED
    step = repaired.steps[0]
    assert step.get('step_id') or step.get('id'), 'step_id should be added'
    assert step.get('description'), 'description should be added'
    assert 'parameters' in step, 'parameters should be added'
    assert 'dependencies' in step, 'dependencies should be added'
    print('PASS: repair_missing_fields')


def test_repair_invalid_dependency():
    """Repair removes invalid dependency references"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p10', goal='test',
        steps=[
            {'step_id': 'step_1', 'tool': 'file_manager', 'description': 'A', 'dependencies': ['step_99']}
        ],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based',
        status=PlanStatus.INVALID
    )
    error = PlanError(error_type='invalid_dependency', description='Invalid dep')
    repaired = planner.repair_plan(plan, error, ctx)
    assert repaired.status == PlanStatus.REPAIRED
    assert 'step_99' not in repaired.steps[0].get('dependencies', [])
    print('PASS: repair_invalid_dependency')


def test_repair_circular_dependency():
    """Repair breaks circular dependencies"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p11', goal='test',
        steps=[
            {'step_id': 'step_1', 'tool': 'file_manager', 'description': 'A', 'dependencies': ['step_2']},
            {'step_id': 'step_2', 'tool': 'llm', 'description': 'B', 'dependencies': ['step_1']}
        ],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based',
        status=PlanStatus.INVALID
    )
    error = PlanError(error_type='circular_dependency', description='Cycle detected')
    repaired = planner.repair_plan(plan, error, ctx)
    assert repaired.status == PlanStatus.REPAIRED
    # Verify no cycle in repaired plan
    dep_graph = {s['step_id']: s.get('dependencies', []) for s in repaired.steps}
    cycle = planner._detect_cycle(dep_graph)
    assert cycle is None, f'Cycle still present after repair: {cycle}'
    print('PASS: repair_circular_dependency')


# ============================================================
# Task 7.7: LLM to Rule-Based Fallback
# ============================================================

def test_llm_fallback_to_rule_based():
    """When LLM fails, falls back to rule-based planning"""
    planner = HybridPlanner(
        enable_llm_planning=True,
        enable_rule_based_planning=True,
        llm_fallback_enabled=True
    )
    # Make LLM planning always fail
    planner._generate_llm_plan = Mock(return_value=None)
    
    ctx = make_context()
    # Use a goal that matches a rule-based template
    plan = planner.create_plan("read file example.txt", ctx)
    
    assert plan is not None
    assert plan.planning_approach == 'rule_based', f'Expected rule_based fallback, got {plan.planning_approach}'
    print('PASS: llm_fallback_to_rule_based')


def test_rule_based_fallback_to_llm():
    """When rule-based fails, falls back to LLM planning"""
    planner = HybridPlanner(
        enable_llm_planning=True,
        enable_rule_based_planning=True,
        llm_fallback_enabled=True
    )
    # Make rule-based planning always fail
    planner._generate_rule_based_plan = Mock(return_value=None)
    
    ctx = make_context()
    # Use a simple goal that would normally use rule-based
    plan = planner.create_plan("read file example.txt", ctx)
    
    assert plan is not None
    # Should have fallen back to LLM
    assert plan.planning_approach == 'llm_based', f'Expected llm_based fallback, got {plan.planning_approach}'
    print('PASS: rule_based_fallback_to_llm')


# ============================================================
# Task 7.8: Tool Selection with Confidence Scoring
# ============================================================

def test_select_tool_file_operation():
    """File operation step selects file_manager with high confidence"""
    planner = make_planner()
    step = {'description': 'read file contents', 'action': 'read', 'tool': 'file_manager'}
    sel = planner.select_tool(step, ['file_manager', 'browser_agent', 'llm'])
    assert sel.tool_name == 'file_manager', f'Expected file_manager, got {sel.tool_name}'
    assert sel.confidence > 0.5
    assert isinstance(sel, ToolSelection)
    print(f'PASS: select_tool_file_operation (confidence={sel.confidence:.2f})')


def test_select_tool_web_search():
    """Web search step selects browser_agent"""
    planner = make_planner()
    step = {'description': 'search the web for information', 'action': 'search'}
    sel = planner.select_tool(step, ['file_manager', 'browser_agent', 'llm'])
    assert sel.tool_name == 'browser_agent', f'Expected browser_agent, got {sel.tool_name}'
    print(f'PASS: select_tool_web_search (confidence={sel.confidence:.2f})')


def test_select_tool_summarize():
    """Summarize step selects llm"""
    planner = make_planner()
    step = {'description': 'summarize and analyze the content', 'action': 'summarize'}
    sel = planner.select_tool(step, ['file_manager', 'browser_agent', 'llm'])
    assert sel.tool_name == 'llm', f'Expected llm, got {sel.tool_name}'
    print(f'PASS: select_tool_summarize (confidence={sel.confidence:.2f})')


def test_select_tool_empty_tools():
    """Empty tools list returns unknown with 0 confidence"""
    planner = make_planner()
    sel = planner.select_tool({'description': 'do something'}, [])
    assert sel.tool_name == 'unknown'
    assert sel.confidence == 0.0
    print('PASS: select_tool_empty_tools')


def test_select_tool_has_alternatives():
    """Tool selection includes alternatives"""
    planner = make_planner()
    step = {'description': 'read file', 'action': 'read'}
    sel = planner.select_tool(step, ['file_manager', 'browser_agent', 'llm', 'document_reader'])
    assert isinstance(sel.alternatives, list)
    # Alternatives should not include the selected tool
    alt_names = [name for name, _ in sel.alternatives]
    assert sel.tool_name not in alt_names
    print(f'PASS: select_tool_has_alternatives (alternatives={alt_names})')


def test_select_tool_with_statistics():
    """Tool selection uses historical statistics when provided"""
    planner = make_planner()
    step = {'description': 'do something'}
    context = {
        'tool_statistics': {
            'file_manager': {'success_rate': 0.95, 'confidence': 0.9, 'avg_duration_seconds': 2.0},
            'browser_agent': {'success_rate': 0.6, 'confidence': 0.5, 'avg_duration_seconds': 10.0},
        }
    }
    sel = planner.select_tool(step, ['file_manager', 'browser_agent'], context=context)
    # file_manager has much better stats, should be selected
    assert sel.tool_name == 'file_manager', f'Expected file_manager (better stats), got {sel.tool_name}'
    print(f'PASS: select_tool_with_statistics (tool={sel.tool_name}, confidence={sel.confidence:.2f})')


# ============================================================
# Task 7.9: Plan Optimization and Dependency Resolution
# ============================================================

def test_optimize_parallel_detection():
    """Steps with no shared dependencies are identified as parallelizable"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p12', goal='test',
        steps=[
            {'step_id': 'step_1', 'tool': 'file_manager', 'description': 'A', 'dependencies': [], 'estimated_duration_seconds': 5},
            {'step_id': 'step_2', 'tool': 'browser_agent', 'description': 'B', 'dependencies': [], 'estimated_duration_seconds': 10},
            {'step_id': 'step_3', 'tool': 'llm', 'description': 'C', 'dependencies': ['step_1', 'step_2'], 'estimated_duration_seconds': 5}
        ],
        complexity=TaskComplexity.MODERATE, planning_approach='rule_based'
    )
    optimized = planner._optimize_plan(plan, ctx)
    assert optimized.metadata.get('optimized') is True
    assert optimized.metadata.get('parallel_groups') == 2
    # Duration = max(5,10) + 5 = 15, not 5+10+5=20
    assert optimized.estimated_duration_seconds == 15, f'Expected 15s, got {optimized.estimated_duration_seconds}'
    print(f'PASS: optimize_parallel_detection (groups={optimized.metadata["parallel_groups"]}, duration={optimized.estimated_duration_seconds}s)')


def test_optimize_deduplication():
    """Redundant steps with same tool+action+params are removed"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p13', goal='test',
        steps=[
            {'step_id': 'step_1', 'tool': 'file_manager', 'action': 'read', 'description': 'Read', 'parameters': {'path': 'a.txt'}, 'dependencies': [], 'estimated_duration_seconds': 5},
            {'step_id': 'step_2', 'tool': 'file_manager', 'action': 'read', 'description': 'Read again', 'parameters': {'path': 'a.txt'}, 'dependencies': [], 'estimated_duration_seconds': 5},
            {'step_id': 'step_3', 'tool': 'llm', 'action': 'summarize', 'description': 'Summarize', 'parameters': {}, 'dependencies': ['step_1'], 'estimated_duration_seconds': 5}
        ],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based'
    )
    optimized = planner._optimize_plan(plan, ctx)
    assert optimized.metadata.get('removed_redundant', 0) == 1, f'Expected 1 removed, got {optimized.metadata.get("removed_redundant")}'
    assert len(optimized.steps) == 2
    print(f'PASS: optimize_deduplication (removed={optimized.metadata["removed_redundant"]})')


def test_optimize_topological_ordering():
    """Steps are reordered to respect dependencies"""
    planner = make_planner()
    ctx = make_context()
    # Steps in reverse dependency order
    plan = TaskPlan(
        plan_id='p14', goal='test',
        steps=[
            {'step_id': 'step_3', 'tool': 'llm', 'description': 'C', 'dependencies': ['step_1', 'step_2'], 'estimated_duration_seconds': 5},
            {'step_id': 'step_1', 'tool': 'file_manager', 'description': 'A', 'dependencies': [], 'estimated_duration_seconds': 5},
            {'step_id': 'step_2', 'tool': 'browser_agent', 'description': 'B', 'dependencies': [], 'estimated_duration_seconds': 5},
        ],
        complexity=TaskComplexity.MODERATE, planning_approach='rule_based'
    )
    optimized = planner._optimize_plan(plan, ctx)
    # step_3 should come after step_1 and step_2
    step_ids = [s.get('step_id') for s in optimized.steps]
    assert step_ids.index('step_3') > step_ids.index('step_1'), 'step_3 should come after step_1'
    assert step_ids.index('step_3') > step_ids.index('step_2'), 'step_3 should come after step_2'
    print(f'PASS: optimize_topological_ordering (order={step_ids})')


def test_optimize_empty_plan():
    """Optimization handles empty plan gracefully"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p15', goal='test', steps=[],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based'
    )
    optimized = planner._optimize_plan(plan, ctx)
    assert optimized is not None
    assert len(optimized.steps) == 0
    print('PASS: optimize_empty_plan')


def test_optimize_single_step():
    """Single step plan is optimized correctly"""
    planner = make_planner()
    ctx = make_context()
    plan = TaskPlan(
        plan_id='p16', goal='test',
        steps=[{'step_id': 'step_1', 'tool': 'file_manager', 'description': 'Read', 'dependencies': [], 'estimated_duration_seconds': 5}],
        complexity=TaskComplexity.SIMPLE, planning_approach='rule_based'
    )
    optimized = planner._optimize_plan(plan, ctx)
    assert len(optimized.steps) == 1
    assert optimized.estimated_duration_seconds == 5
    print('PASS: optimize_single_step')


# ============================================================
# Run all tests
# ============================================================

def run_all():
    tests = [
        # 7.5 Validation
        test_validate_valid_plan,
        test_validate_unavailable_tool,
        test_validate_circular_dependency,
        test_validate_empty_plan,
        test_validate_invalid_dependency_reference,
        test_validate_generic_tools_allowed,
        # 7.6 Repair
        test_repair_empty_plan,
        test_repair_invalid_tool,
        test_repair_missing_fields,
        test_repair_invalid_dependency,
        test_repair_circular_dependency,
        # 7.7 Fallback
        test_llm_fallback_to_rule_based,
        test_rule_based_fallback_to_llm,
        # 7.8 Tool Selection
        test_select_tool_file_operation,
        test_select_tool_web_search,
        test_select_tool_summarize,
        test_select_tool_empty_tools,
        test_select_tool_has_alternatives,
        test_select_tool_with_statistics,
        # 7.9 Optimization
        test_optimize_parallel_detection,
        test_optimize_deduplication,
        test_optimize_topological_ordering,
        test_optimize_empty_plan,
        test_optimize_single_step,
    ]

    print("=" * 60)
    print("Tasks 7.4-7.9 Implementation Tests")
    print("=" * 60)

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f'FAIL: {test.__name__}: {e}')
            import traceback
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0


if __name__ == '__main__':
    success = run_all()
    sys.exit(0 if success else 1)
