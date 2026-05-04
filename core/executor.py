"""
Executor and Observer

Implements task plan execution (Executor) and result collection (Observer).
The Executor takes a TaskPlan and executes it step by step, managing execution
state, dependency ordering, retry coordination, and execution context.
The Observer subscribes to execution events and provides a clean interface
for querying results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
from uuid import uuid4
import time

from observability import get_logging_system, get_tracing_system, get_correlation_id
from events import get_event_bus, EventType, Event
from core.hybrid_planner import TaskPlan, PlanStatus
from core.llm_retry_manager import LLMRetryManager, RetryConfig, RetryStrategy


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StepStatus(str, Enum):
    """Execution status for a single plan step"""
    PENDING = "pending"
    READY = "ready"       # dependencies satisfied, can run
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionStatus(str, Enum):
    """Overall execution status for a plan"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Result of executing a single plan step"""
    step_id: str
    step_index: int
    tool: str
    action: str
    status: StepStatus
    output: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_index": self.step_index,
            "tool": self.tool,
            "action": self.action,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "retry_count": self.retry_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class ExecutionContext:
    """
    Maintains accumulated state as steps complete.

    Passed to each step so dependent steps can access prior outputs.
    Supports serialization for persistence.
    """
    plan_id: str
    task_id: str
    step_outputs: Dict[str, Any] = field(default_factory=dict)   # step_id -> output
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def set_step_output(self, step_id: str, output: Any) -> None:
        self.step_outputs[step_id] = output

    def get_step_output(self, step_id: str) -> Optional[Any]:
        return self.step_outputs.get(step_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "step_outputs": self.step_outputs,
            "metadata": self.metadata,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class ExecutionResult:
    """Overall result of executing a TaskPlan"""
    plan_id: str
    task_id: str
    status: ExecutionStatus
    step_results: List[StepResult] = field(default_factory=list)
    context: Optional[ExecutionContext] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    failure_reason: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "step_results": [s.to_dict() for s in self.step_results],
            "context": self.context.to_dict() if self.context else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "failure_reason": self.failure_reason,
        }


# ---------------------------------------------------------------------------
# Tool Executor placeholder (Task 12)
# ---------------------------------------------------------------------------

class ToolExecutorInterface:
    """
    Placeholder interface for the Tool Executor (Task 12).

    Provides a simple execute_tool() method that the Executor calls.
    Real implementation will be injected once Task 12 is complete.
    """

    def execute_tool(
        self,
        tool_name: str,
        action: str,
        parameters: Dict[str, Any],
        context: ExecutionContext,
    ) -> Any:
        """
        Execute a tool action with the given parameters.

        Args:
            tool_name: Name of the tool to invoke
            action: Action to perform within the tool
            parameters: Tool-specific parameters
            context: Current execution context

        Returns:
            Tool output (any serialisable value)

        Raises:
            RuntimeError: If tool execution fails
        """
        raise NotImplementedError(
            f"ToolExecutor not yet implemented (Task 12). "
            f"Cannot execute tool='{tool_name}' action='{action}'."
        )


class MockToolExecutor(ToolExecutorInterface):
    """
    Mock Tool Executor for testing and development.

    Returns configurable outputs or raises configurable errors.
    """

    def __init__(self) -> None:
        self._outputs: Dict[str, Any] = {}   # key: "tool:action" -> output
        self._errors: Dict[str, str] = {}    # key: "tool:action" -> error message

    def register_output(self, tool: str, action: str, output: Any) -> None:
        self._outputs[f"{tool}:{action}"] = output

    def register_error(self, tool: str, action: str, error: str) -> None:
        self._errors[f"{tool}:{action}"] = error

    def execute_tool(
        self,
        tool_name: str,
        action: str,
        parameters: Dict[str, Any],
        context: ExecutionContext,
    ) -> Any:
        key = f"{tool_name}:{action}"
        if key in self._errors:
            raise RuntimeError(self._errors[key])
        if key in self._outputs:
            return self._outputs[key]
        # Default: return a simple success marker
        return {"status": "ok", "tool": tool_name, "action": action}


# ---------------------------------------------------------------------------
# In-memory result store (placeholder for Task 16 Memory System)
# ---------------------------------------------------------------------------

class InMemoryResultStore:
    """
    Simple in-memory store for intermediate step results.

    Results are keyed by (plan_id, step_id) and support optional TTL-based
    expiration.  This is a placeholder until the full Memory System (Task 16)
    is available.
    """

    def __init__(self, default_ttl_seconds: Optional[float] = None) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}   # plan_id -> {step_id: entry}
        self._default_ttl = default_ttl_seconds

    def store(
        self,
        plan_id: str,
        step_id: str,
        result: Any,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        entry = {
            "result": result,
            "stored_at": time.time(),
            "ttl_seconds": ttl,
        }
        self._store.setdefault(plan_id, {})[step_id] = entry

    def retrieve(self, plan_id: str, step_id: str) -> Optional[Any]:
        plan_store = self._store.get(plan_id, {})
        entry = plan_store.get(step_id)
        if entry is None:
            return None
        # Check TTL
        if entry["ttl_seconds"] is not None:
            age = time.time() - entry["stored_at"]
            if age > entry["ttl_seconds"]:
                del plan_store[step_id]
                return None
        return entry["result"]

    def cleanup_plan(self, plan_id: str) -> None:
        """Remove all results for a plan."""
        self._store.pop(plan_id, None)

    def cleanup_expired(self) -> int:
        """Remove all expired entries; returns count removed."""
        removed = 0
        now = time.time()
        for plan_id, plan_store in list(self._store.items()):
            for step_id, entry in list(plan_store.items()):
                if entry["ttl_seconds"] is not None:
                    if now - entry["stored_at"] > entry["ttl_seconds"]:
                        del plan_store[step_id]
                        removed += 1
            if not plan_store:
                del self._store[plan_id]
        return removed


# Module-level singleton
_result_store = InMemoryResultStore()


def get_result_store() -> InMemoryResultStore:
    return _result_store


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class Executor:
    """
    Executes a TaskPlan step by step.

    Responsibilities:
    - Execute steps in topological order respecting dependencies
    - Maintain ExecutionContext that accumulates results
    - Coordinate retries via LLMRetryManager pattern
    - Emit events for step and plan lifecycle
    - Determine overall success/failure

    Sub-tasks covered: 8.1, 8.2, 8.3, 8.4, 8.8
    """

    def __init__(
        self,
        tool_executor: Optional[ToolExecutorInterface] = None,
        retry_config: Optional[RetryConfig] = None,
        result_store: Optional[InMemoryResultStore] = None,
        max_step_retries: int = 3,
    ) -> None:
        self.logger = get_logging_system()
        self.tracer = get_tracing_system()
        self.event_bus = get_event_bus()

        self.tool_executor: ToolExecutorInterface = tool_executor or ToolExecutorInterface()
        self.retry_manager = LLMRetryManager(
            retry_config or RetryConfig(
                max_retries=max_step_retries,
                initial_delay_seconds=0.5,
                max_delay_seconds=5.0,
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            )
        )
        self.result_store = result_store or get_result_store()

        self.logger.info(
            "Executor initialized",
            extra={"max_step_retries": max_step_retries},
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_plan(
        self, plan: TaskPlan, context: Optional[ExecutionContext] = None
    ) -> ExecutionResult:
        """
        Execute all steps in a TaskPlan.

        Steps are executed in topological order.  A step becomes eligible
        once all steps it depends on have completed successfully.

        Args:
            plan: The TaskPlan to execute
            context: Optional pre-existing ExecutionContext

        Returns:
            ExecutionResult with status and per-step results
        """
        task_id = str(uuid4())
        if context is None:
            context = ExecutionContext(
                plan_id=plan.plan_id,
                task_id=task_id,
                started_at=datetime.utcnow(),
            )

        result = ExecutionResult(
            plan_id=plan.plan_id,
            task_id=task_id,
            status=ExecutionStatus.RUNNING,
            context=context,
            started_at=datetime.utcnow(),
        )

        self.logger.info(
            "Starting plan execution",
            extra={"plan_id": plan.plan_id, "steps": len(plan.steps)},
        )
        self._emit_event(EventType.EXECUTION_STARTED, plan.plan_id, task_id, {
            "plan_id": plan.plan_id,
            "steps_count": len(plan.steps),
        })

        # Build step state tracking
        step_statuses: Dict[int, StepStatus] = {
            i: StepStatus.PENDING for i in range(len(plan.steps))
        }

        try:
            while True:
                # Find steps that are ready to execute
                ready = self._get_ready_steps(plan.steps, step_statuses)
                if not ready:
                    # Check if we're done or stuck
                    if all(
                        s in (StepStatus.COMPLETED, StepStatus.SKIPPED)
                        for s in step_statuses.values()
                    ):
                        break  # All done
                    # Some steps are still pending but none are ready ? failure
                    pending = [
                        i for i, s in step_statuses.items()
                        if s == StepStatus.PENDING
                    ]
                    result.failure_reason = (
                        f"Steps {pending} are pending but have no satisfied dependencies"
                    )
                    result.status = ExecutionStatus.FAILED
                    break

                # Execute each ready step (sequentially for now)
                for idx in ready:
                    step = plan.steps[idx]
                    step_statuses[idx] = StepStatus.RUNNING

                    step_result = self._execute_step_with_retry(
                        step_index=idx,
                        step=step,
                        context=context,
                    )
                    result.step_results.append(step_result)

                    if step_result.status == StepStatus.COMPLETED:
                        step_statuses[idx] = StepStatus.COMPLETED
                        context.set_step_output(step_result.step_id, step_result.output)
                        # Persist to result store
                        self.result_store.store(
                            plan.plan_id, step_result.step_id, step_result.output
                        )
                    else:
                        step_statuses[idx] = StepStatus.FAILED
                        result.failure_reason = (
                            f"Step {idx} ('{step.get('description', step.get('tool', ''))}') "
                            f"failed: {step_result.error}"
                        )
                        result.status = ExecutionStatus.FAILED
                        # Mark remaining pending steps as skipped
                        for j, s in step_statuses.items():
                            if s == StepStatus.PENDING:
                                step_statuses[j] = StepStatus.SKIPPED
                        break  # Stop processing further steps

                if result.status == ExecutionStatus.FAILED:
                    break

        except Exception as exc:
            result.status = ExecutionStatus.FAILED
            result.failure_reason = f"Unexpected error during plan execution: {exc}"
            self.logger.error(
                "Plan execution error",
                extra={"plan_id": plan.plan_id, "error": str(exc)},
            )

        # Finalise
        if result.status == ExecutionStatus.RUNNING:
            result.status = ExecutionStatus.COMPLETED

        now = datetime.utcnow()
        result.completed_at = now
        context.completed_at = now
        if result.started_at:
            result.duration_seconds = (now - result.started_at).total_seconds()

        event_type = (
            EventType.TASK_COMPLETED
            if result.status == ExecutionStatus.COMPLETED
            else EventType.TASK_FAILED
        )
        self._emit_event(event_type, plan.plan_id, task_id, result.to_dict())

        self.logger.info(
            "Plan execution finished",
            extra={
                "plan_id": plan.plan_id,
                "status": result.status.value,
                "duration_seconds": result.duration_seconds,
            },
        )
        return result

    def execute_step(
        self, step: Dict[str, Any], context: ExecutionContext
    ) -> StepResult:
        """
        Execute a single plan step without retry.

        Args:
            step: Step dict from TaskPlan.steps
            context: Current execution context

        Returns:
            StepResult
        """
        step_id = str(uuid4())
        step_index = step.get("_index", 0)
        tool = step.get("tool", "unknown")
        action = step.get("action", "execute")
        description = step.get("description", f"{tool}.{action}")

        started_at = datetime.utcnow()
        self._emit_event(EventType.TOOL_EXECUTION_STARTED, context.plan_id, context.task_id, {
            "step_id": step_id,
            "tool": tool,
            "action": action,
        })

        try:
            # Build parameters: merge step params + prior step outputs for dependencies
            parameters = self._build_step_parameters(step, context)
            output = self.tool_executor.execute_tool(tool, action, parameters, context)
            completed_at = datetime.utcnow()

            self._emit_event(EventType.TOOL_EXECUTION_COMPLETED, context.plan_id, context.task_id, {
                "step_id": step_id,
                "tool": tool,
                "action": action,
            })

            return StepResult(
                step_id=step_id,
                step_index=step_index,
                tool=tool,
                action=action,
                status=StepStatus.COMPLETED,
                output=output,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
            )

        except Exception as exc:
            completed_at = datetime.utcnow()
            self._emit_event(EventType.TOOL_EXECUTION_FAILED, context.plan_id, context.task_id, {
                "step_id": step_id,
                "tool": tool,
                "action": action,
                "error": str(exc),
            })
            return StepResult(
                step_id=step_id,
                step_index=step_index,
                tool=tool,
                action=action,
                status=StepStatus.FAILED,
                error=str(exc),
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
            )

    def handle_step_failure(
        self, step: Dict[str, Any], error: Exception
    ) -> Dict[str, Any]:
        """
        Determine retry decision for a failed step.

        Returns a dict with keys: should_retry (bool), reason (str).
        """
        error_msg = str(error)
        # Non-retryable errors
        non_retryable = ["permission denied", "access denied", "not found", "invalid parameter"]
        for phrase in non_retryable:
            if phrase in error_msg.lower():
                return {"should_retry": False, "reason": f"Non-retryable error: {error_msg}"}
        return {"should_retry": True, "reason": f"Retryable error: {error_msg}"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_step_with_retry(
        self,
        step_index: int,
        step: Dict[str, Any],
        context: ExecutionContext,
    ) -> StepResult:
        """Execute a step, retrying on failure up to max_retries."""
        step["_index"] = step_index
        retry_count = 0
        last_result: Optional[StepResult] = None

        max_retries = self.retry_manager.config.max_retries

        for attempt in range(1, max_retries + 1):
            result = self.execute_step(step, context)
            last_result = result

            if result.status == StepStatus.COMPLETED:
                result.retry_count = attempt - 1
                return result

            # Check if retryable
            decision = self.handle_step_failure(
                step, Exception(result.error or "unknown error")
            )
            if not decision["should_retry"] or attempt >= max_retries:
                result.retry_count = attempt - 1
                self.logger.warning(
                    "Step failed after retries",
                    extra={
                        "step_index": step_index,
                        "attempts": attempt,
                        "error": result.error,
                    },
                )
                return result

            # Wait before retry
            delay = self.retry_manager._calculate_delay(attempt)
            self.logger.info(
                "Retrying step",
                extra={
                    "step_index": step_index,
                    "attempt": attempt,
                    "delay_seconds": delay,
                },
            )
            time.sleep(delay)
            retry_count = attempt

        if last_result is not None:
            last_result.retry_count = retry_count
        return last_result  # type: ignore

    def _get_ready_steps(
        self,
        steps: List[Dict[str, Any]],
        statuses: Dict[int, StepStatus],
    ) -> List[int]:
        """
        Return indices of steps whose dependencies are all completed.

        A step's dependencies are specified via a 'depends_on' list of
        step indices in the step dict.  Steps with no 'depends_on' are
        immediately ready once they are PENDING.
        """
        ready = []
        for idx, step in enumerate(steps):
            if statuses[idx] != StepStatus.PENDING:
                continue
            deps: List[int] = step.get("depends_on", [])
            if all(statuses.get(d) == StepStatus.COMPLETED for d in deps):
                ready.append(idx)
        return ready

    def _build_step_parameters(
        self, step: Dict[str, Any], context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Build parameters for a step, injecting prior step outputs.

        If a step has 'input_from' mapping (step_id -> param_name), the
        corresponding prior output is injected into the parameters dict.
        """
        params: Dict[str, Any] = dict(step.get("parameters", {}))
        input_from: Dict[str, str] = step.get("input_from", {})
        for step_id, param_name in input_from.items():
            prior_output = context.get_step_output(step_id)
            if prior_output is not None:
                params[param_name] = prior_output
        return params

    def _emit_event(
        self,
        event_type: EventType,
        plan_id: str,
        task_id: str,
        payload: Dict[str, Any],
    ) -> None:
        try:
            event = Event(
                event_id=str(uuid4()),
                event_type=event_type.value,
                event_timestamp=datetime.utcnow(),
                source_component="executor",
                trace_id=str(uuid4()),
                correlation_id=get_correlation_id() or str(uuid4()),
                workflow_id=plan_id,
                payload={**payload, "task_id": task_id},
            )
            self.event_bus.publish(event)
        except Exception:
            pass  # Never let event emission crash execution


# ---------------------------------------------------------------------------
# Observer
# ---------------------------------------------------------------------------

@dataclass
class ObservationResult:
    """Wrapper for observed results collected by the Observer."""
    plan_id: str
    step_id: str
    tool: str
    action: str
    output: Any
    error: Optional[str] = None
    observed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "tool": self.tool,
            "action": self.action,
            "output": self.output,
            "error": self.error,
            "observed_at": self.observed_at.isoformat()
        }


class Observer:
    """
    Observes execution results and collects them.

    Responsibilities:
    - Subscribes to TOOL_EXECUTION_COMPLETED and TOOL_EXECUTION_FAILED events
    - Collects intermediate step results via InMemoryResultStore
    - Formats retrieved results for reasoning context (Agent Orchestrator)

    Sub-tasks covered: 8.5, 8.6, 8.7
    """

    def __init__(self, result_store: Optional[InMemoryResultStore] = None) -> None:
        self.logger = get_logging_system()
        self.event_bus = get_event_bus()
        self.result_store = result_store or get_result_store()
        
        self.logger.info("Observer initialized")
        self._subscribe()

    def _subscribe(self) -> None:
        """Subscribe to execution completion events."""
        self.event_bus.subscribe(
            EventType.TOOL_EXECUTION_COMPLETED,
            self._handle_execution_event
        )
        self.event_bus.subscribe(
            EventType.TOOL_EXECUTION_FAILED,
            self._handle_execution_event
        )

    def _handle_execution_event(self, event: Event) -> None:
        """Handle execution events and potentially store additional metadata or logs."""
        payload = event.payload
        plan_id = event.workflow_id
        step_id = payload.get("step_id")
        
        if not plan_id or not step_id:
            return

        self.logger.debug(
            "Observer recorded execution event",
            extra={
                "event_type": event.event_type,
                "plan_id": plan_id,
                "step_id": step_id,
                "tool": payload.get("tool"),
                "action": payload.get("action")
            }
        )
        # Note: The Executor stores the actual output directly into the
        # result_store. The Observer is an interface for querying and formatting.

    def get_observation(self, plan_id: str, step_id: str) -> Optional[ObservationResult]:
        """Retrieve an observation from the result store."""
        raw_result = self.result_store.retrieve(plan_id, step_id)
        if raw_result is None:
            return None
        
        # In a real database implementation, tool/action data would be retrieved from the DB.
        # For now, we return it loosely bound to provide the context interface.
        return ObservationResult(
            plan_id=plan_id,
            step_id=step_id,
            tool="retrieved", 
            action="retrieved",
            output=raw_result
        )

    def format_for_context(self, plan_id: str, step_ids: List[str]) -> str:
        """
        Format retrieved results as context for reasoning steps.
        
        Args:
            plan_id: The ID of the executing plan
            step_ids: The step IDs we want observations for
            
        Returns:
            A formatted string ready to be injected into an LLM prompt.
        """
        lines = ["## Execution Observations"]
        found_any = False
        
        for idx, step_id in enumerate(step_ids):
            result = self.result_store.retrieve(plan_id, step_id)
            if result is not None:
                found_any = True
                lines.append(f"### Observation from Step {step_id}")
                lines.append(f"Output: {result}")
                lines.append("---")
            else:
                lines.append(f"### Observation from Step {step_id}")
                lines.append("*No result found or result expired.*")
                lines.append("---")
                
        if not found_any:
            return "No prior observations available."
            
        return "\n".join(lines)
