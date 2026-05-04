"""
Test suite for Stuart-AI Bug Audit Fixes (BUG-01 through BUG-20)

Verifies the specific fixes applied during the hardening sprint.
"""
import sys
import os
import types
import threading
import time

# --- Mock heavy dependencies before any project imports ---
for mod_name in [
    'psycopg2', 'psycopg2.extras', 'psycopg2.pool',
    'qdrant_client', 'qdrant_client.models',
    'openai',
    'schedule',
    'watchdog', 'watchdog.observers', 'watchdog.events',
    'observability', 'observability.logging_system', 'observability.tracing_system',
    'observability.trace_propagation', 'observability.correlation_tracker',
    'observability.opentelemetry_exporter',
    'events', 'events.event_bus', 'events.event_types',
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

# Stub observability functions
obs = sys.modules['observability']

class _StubLogger:
    def info(self, *a, **kw): pass
    def debug(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass

obs.get_logging_system = lambda: _StubLogger()
obs.LogLevel = type('LogLevel', (), {'INFO': 'info', 'DEBUG': 'debug', 'WARNING': 'warning', 'ERROR': 'error'})
obs.LogEntry = type('LogEntry', (), {})
obs.initialize_logging = lambda: None
obs.get_tracing_system = lambda: None
obs.initialize_tracing = lambda: None
obs.TracingSystem = type('TracingSystem', (), {})
obs.Span = type('Span', (), {})
obs.SpanContext = type('SpanContext', (), {})
obs.SpanStatus = type('SpanStatus', (), {})
obs.TracePropagator = type('TracePropagator', (), {})
obs.TraceContext = type('TraceContext', (), {})
obs.get_trace_propagator = lambda: None
obs.CorrelationTracker = type('CorrelationTracker', (), {})
obs.CorrelationContext = type('CorrelationContext', (), {})
obs.get_correlation_tracker = lambda: None
obs.get_correlation_id = lambda: "test"
obs.set_correlation_id = lambda x: None
obs.get_or_create_correlation_id = lambda: "test"
obs.with_correlation = lambda: None
obs.OpenTelemetryExporter = type('OpenTelemetryExporter', (), {})
obs.create_opentelemetry_exporter = lambda: None
obs.OPENTELEMETRY_AVAILABLE = False

for sub_name in ['logging_system', 'tracing_system', 'trace_propagation', 
                  'correlation_tracker', 'opentelemetry_exporter']:
    sub = sys.modules[f'observability.{sub_name}']
    for attr in dir(obs):
        if not attr.startswith('_'):
            setattr(sub, attr, getattr(obs, attr))

# Stub events
events_mod = sys.modules['events']
events_mod.get_event_bus = lambda: type('MockBus', (), {'publish': lambda self, e: None, 'subscribe': lambda self, *a, **kw: None})()

class _MockEventType:
    TASK_STARTED = "task_started"
    CONFIG_HOT_RELOADED = "config_hot_reloaded"
events_mod.EventType = _MockEventType

class _MockEvent:
    def __init__(self, **kw): pass
    @classmethod
    def create(cls, **kw): return cls()
    def validate(self): return True
events_mod.Event = _MockEvent

sys.modules['events.event_bus'].EventBus = type('EventBus', (), {})
sys.modules['events.event_types'].EventType = _MockEventType
sys.modules['events.event_types'].Event = _MockEvent

import pytest


# ============================================================
# BUG-01: Orchestrator should use get_all_tools() not list_tools()
# ============================================================
def test_bug01_orchestrator_uses_get_all_tools():
    """Verify Orchestrator calls get_all_tools() + get_metadata() instead of list_tools()."""
    from core.orchestrator import Orchestrator
    import inspect
    source = inspect.getsource(Orchestrator)
    
    assert "list_tools()" not in source, \
        "BUG-01: Orchestrator still calls list_tools() which doesn't exist on ToolRegistry"
    assert "get_all_tools()" in source, \
        "BUG-01: Orchestrator should use get_all_tools()"
    assert "get_metadata()" in source, \
        "BUG-01: Orchestrator should call get_metadata() on each tool"


# ============================================================
# BUG-02: orchestrator_ref must be declared before the lambda
# ============================================================
def test_bug02_forward_reference_ordering():
    """Verify orchestrator_ref is declared before the lambda that captures it."""
    with open(os.path.join(os.path.dirname(__file__), '..', 'main.py'), 'r', encoding='utf-8') as f:
        source = f.read()
    
    ref_pos = source.find("orchestrator_ref = [None]")
    lambda_pos = source.find("lambda prompt: orchestrator_ref[0]")
    
    assert ref_pos != -1, "BUG-02: orchestrator_ref declaration not found"
    assert lambda_pos != -1, "BUG-02: lambda using orchestrator_ref not found"
    assert ref_pos < lambda_pos, \
        f"BUG-02: orchestrator_ref (pos {ref_pos}) must be declared before the lambda (pos {lambda_pos})"


# ============================================================
# BUG-04: ToolExecutor should return failed ToolResult, not raise
# ============================================================
def test_bug04_tool_executor_returns_failed_result():
    """Verify ToolExecutor returns ToolResult(success=False) instead of raising RuntimeError."""
    from tools.tool_executor import ToolSandboxExecutor
    import inspect
    source = inspect.getsource(ToolSandboxExecutor.execute_tool)
    
    assert 'raise RuntimeError(f"Tool execution failed internally' not in source, \
        "BUG-04: ToolExecutor still raises RuntimeError for failed tools"
    assert "return result" in source, \
        "BUG-04: ToolExecutor should return the failed ToolResult"


# ============================================================
# BUG-05: Lock manager must close file handles on failed lock
# ============================================================
def test_bug05_lock_manager_closes_handles():
    """Verify LockManager closes file handles on failed lock acquisition."""
    from core.lock_manager import LockManager
    import inspect
    source = inspect.getsource(LockManager.acquire)
    
    assert "f.close()" in source, \
        "BUG-05: LockManager.acquire must close file handle in except block"
    assert "f = None" in source, \
        "BUG-05: LockManager should init f=None before try block"


# ============================================================
# BUG-06: is_locked() must work on Windows
# ============================================================
def test_bug06_is_locked_works_on_windows():
    """Verify is_locked() has a Windows implementation."""
    from core.lock_manager import LockManager
    import inspect
    source = inspect.getsource(LockManager.is_locked)
    
    assert "msvcrt.locking" in source, \
        "BUG-06: is_locked() must use msvcrt.locking for Windows support"
    assert "os.name == 'nt'" in source, \
        "BUG-06: is_locked() should check os.name == 'nt'"


# ============================================================
# BUG-08: Budget inflation must be capped
# ============================================================
def test_bug08_budget_inflation_capped():
    """Verify budget inflation is capped at initial_budget + 3."""
    from core.orchestrator import Orchestrator
    import inspect
    source = inspect.getsource(Orchestrator)
    
    assert "_initial_budget" in source, \
        "BUG-08: Orchestrator should track _initial_budget"
    assert "max_allowed" in source, \
        "BUG-08: Budget cap should use max_allowed variable"


# ============================================================
# BUG-09: BrowserAgentTool must close httpx.Client
# ============================================================
def test_bug09_browser_tool_closes_client():
    """Verify BrowserAgentTool has a __del__ or close method."""
    from tools.core.browser_agent_tool import BrowserAgentTool
    
    assert hasattr(BrowserAgentTool, '__del__'), \
        "BUG-09: BrowserAgentTool must have __del__ for cleanup"


# ============================================================
# BUG-10: Robots.txt fallback must create permissive parser
# ============================================================
def test_bug10_robots_txt_fallback_permissive():
    """Verify robots.txt failure creates a permissive parser."""
    from tools.core.browser_agent_tool import BrowserAgentTool
    import inspect
    source = inspect.getsource(BrowserAgentTool._get_robot_parser)
    
    assert 'parse([' in source, \
        "BUG-10: Fallback should create a permissive parser with explicit Allow rules"
    assert "Allow: /" in source, \
        "BUG-10: Permissive parser must allow all paths"


# ============================================================
# BUG-11: SystemModeManager must use Event object
# ============================================================
def test_bug11_system_mode_event_type():
    """Verify SystemModeManager creates proper Event objects."""
    from core.system_mode_manager import SystemModeManager
    import inspect
    source = inspect.getsource(SystemModeManager.set_mode)
    
    assert "Event.create" in source, \
        "BUG-11: set_mode must use Event.create() for proper event publishing"
    assert '"SYSTEM_MODE_CHANGED"' not in source, \
        "BUG-11: Should not pass raw string as event type"


# ============================================================
# BUG-12: Approval system threshold must not uppercase
# ============================================================
def test_bug12_approval_threshold_case():
    """Verify _tier_action doesn't uppercase the risk level value."""
    from security.approval_system import ApprovalSystem
    import inspect
    source = inspect.getsource(ApprovalSystem._tier_action)
    
    assert ".upper()" not in source, \
        "BUG-12: _tier_action must not uppercase the key (threshold keys are lowercase)"


# ============================================================
# BUG-16: /budget command must use nested dict keys
# ============================================================
def test_bug16_budget_command_uses_nested_keys():
    """Verify _cmd_budget reads from nested status dict."""
    from core.slash_commands import SlashCommandRouter
    import inspect
    source = inspect.getsource(SlashCommandRouter._cmd_budget)
    
    assert 'status.get("daily_used"' not in source, \
        "BUG-16: Should not use flat key 'daily_used'"
    assert 'status.get("daily"' in source, \
        "BUG-16: Should use nested key 'daily'"
    assert 'daily.get("used"' in source, \
        "BUG-16: Should read 'used' from nested daily dict"


# ============================================================
# BUG-17: TaskQueue must accept no-arg construction
# ============================================================
def test_bug17_task_queue_no_arg():
    """Verify TaskQueue can be constructed without arguments."""
    from automation.task_queue import TaskQueue
    
    # This should not raise TypeError
    queue = TaskQueue()
    assert queue.orchestrator_factory is None
    queue.shutdown()


# ============================================================
# RISK-01: SystemModeManager must be thread-safe
# ============================================================
def test_risk01_system_mode_thread_safe():
    """Verify SystemModeManager uses threading.Lock."""
    from core.system_mode_manager import SystemModeManager
    
    mgr = SystemModeManager()
    assert hasattr(mgr, '_lock'), \
        "RISK-01: SystemModeManager must have a _lock attribute"
    assert isinstance(mgr._lock, type(threading.Lock())), \
        "RISK-01: _lock must be a threading.Lock"


# ============================================================
# RISK-03: Orchestrator should use platform.system()
# ============================================================
def test_risk03_no_hardcoded_windows():
    """Verify Orchestrator doesn't hardcode 'Windows' as OS."""
    from core.orchestrator import Orchestrator
    import inspect
    source = inspect.getsource(Orchestrator)
    
    assert '"Windows"' not in source or 'platform.system()' in source, \
        "RISK-03: Orchestrator should use platform.system() not hardcoded 'Windows'"
    assert "platform.system()" in source, \
        "RISK-03: Orchestrator must call platform.system() for cross-platform Docker support"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
