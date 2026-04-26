"""
Tests for Executor and Observer (Task 8)

Covers:
- 8.1 Executor class with plan execution logic
- 8.2 Step-by-step execution with dependency handling
- 8.3 Retry coordination with Retry Manager
- 8.4 Execution context maintenance
- 8.5 Observer class for result collection
- 8.6 Intermediate result storage in Memory System
- 8.7 Result formatting for reasoning context
- 8.8 Success/failure determination logic
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
from datetime import datetime
from uuid import uuid4

# ---------------------------------------------------------------------------
# Mock all external dependencies before importing executor
# ---------------------------------------------------------------------------

mock_span = MagicMock()
mock_span.__enter__ = Mock(return_value=mock_span)
mock_span.__exit__ = Mock(return_value=False)
mock_span.set_attribute = Mock()

mock_tracer = Mock()
mock_tracer.start_span = Mock(return_value=mock_span)

mock_logger = Mock()
mock_logger.info = Mock()
mock_logger.debug = Mock()
mock_logger.warning = Mock()
mock_logger.error = Mock()

mock_event_bus = Mock()
mock_event_bus.publish = Mock()

sys.modules['observability'] = MagicMock()
sys.modules['observability'].get_logging_system = Mock(return_value=mock_logger)
sys.modules['observability'].get_tracing_system = Mock(return_value=mock_tracer)
sys.modules['observability'].get_correlation_id = Mock(return_value="test-correlation-id")

sys.modules['events'] = MagicMock()
sys.modules['events'].get_event_bus = Mock(return_value=mock_event_bus)
sys.modules['events'].EventType = MagicMock()
sys.modules['events'].Event = MagicMock()

# Mock hybrid_planner module (only the classes we need)
import importlib.util

_hp_spec = importlib.util.spec_from_file_location(
    "hybrid_planner",
    Path(__file__).parent / "hybrid_planner.py",
)
_hp_mod = importlib.util.module_from_spec(_hp_spec)
_hp_spec.loader.exec_module(_hp_mod)
sys.modules['hybrid_planner'] = _hp_mod

# Mock llm_retry_manager
_rm_spec = importlib.util.spec_from_file_location(
    "llm_retry_manager",
    Path(__file__).parent / "llm_retry_manager.py",
)
_rm_mod = importlib.util.module_from_spec(_rm_spec)
_rm_spec.loader.exec_module(_rm_mod)
sys.modules['llm_retry_manager'] = _rm_mod

# Now load executor directly
_ex_spec = importlib.util.spec_from_file_location(
    "executor",
    Path(__file__).parent / "executor.py",
)
_ex_mod = importlib.util.module_from_spec(_ex_spec)
_ex_spec.loader.exec_module(_ex_mod)

# Extract symbols
Executor = _ex_mod.Executor
Observer = _ex_mod.Observer
ExecutionContext = _ex_mod.ExecutionContext
ExecutionResult = _ex_mod.ExecutionResult
ExecutionStatus = _ex_mod.ExecutionStatus
StepResult = _ex_mod.StepResult
StepStatus = _ex_mod.StepStatus
ObservationResult = _ex_mod.ObservationResult
MockToolExecutor = _ex_mod.MockToolExecutor
InMemoryResultStore = _ex_mod.InMemoryResultStore

TaskPlan = _hp_mod.TaskPlan
TaskComplexity = _hp_mod.TaskComplexity
PlanStatus = _hp_mod.PlanStatus

RetryConfig = _rm_mod.RetryConfig
RetryStrategy = _rm_mod.RetryStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_plan(steps, plan_id=None):
    return TaskPlan(
        plan_id=plan_id or str(uuid4()),
        goal="test goal",
        steps=steps,
        complexity=TaskComplexity.SIMPLE,
        planning_approach="rule_based",
        status=PlanStatus.VALID,
    )


def make_executor(outputs=None, errors=None, max_retries=1):
    mock = MockToolExecutor()
    if outputs:
        for (tool, action), output in outputs.items():
            mock.register_output(tool, action, output)
    if errors:
        for (tool, action), error in errors.items():
            mock.register_error(tool, action, error)
    store = InMemoryResultStore()
    cfg = RetryConfig(
        max_retries=max_retries,
        initial_delay_seconds=0.0,
        strategy=RetryStrategy.FIXED_DELAY,
    )
    return Executor(tool_executor=mock, retry_config=cfg, result_store=store), store
