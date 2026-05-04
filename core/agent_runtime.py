"""
Agent Runtime Controller

Top-level runtime controller with reasoning loop management for PCA.
Manages task execution lifecycle, iteration limits, budget tracking,
and state persistence.
"""

import signal
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, Callable
from uuid import uuid4

from database import get_db_connection
from observability import (
    get_logging_system,
    get_tracing_system,
    CorrelationContext,
    get_correlation_id
)
from events import get_event_bus, EventType, Event


class RuntimeState(str, Enum):
    """Agent runtime states"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    REASONING = "reasoning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReasoningBudget:
    """Manages resource consumption thresholds for a single reasoning task.

    Tracks iterations, tool calls, and LLM dispatches to prevent infinite loops 
    and maintain cost control.

    Attributes:
        max_iterations (int): Safety limit for reasoning loop turns.
        max_tool_calls (int): Ceiling for the number of external tool executions.
        max_llm_calls (int): Total budget for LLM API dispatches.
        max_execution_time_seconds (int): Hard timeout for the task logic.
        iterations_used (int): Current count of loop cycles completed.
        tool_calls_used (int): Current count of successfully initiated tool calls.
        llm_calls_used (int): Current count of primary reasoning calls to the model.
        execution_time_seconds (float): Wall-clock time elapsed since task start.
    """
    max_iterations: int = 20
    max_tool_calls: int = 50
    max_llm_calls: int = 100
    max_execution_time_seconds: int = 300
    
    # Current usage
    iterations_used: int = 0
    tool_calls_used: int = 0
    llm_calls_used: int = 0
    execution_time_seconds: float = 0.0
    
    def is_exhausted(self) -> bool:
        """Evaluates if any defined resource threshold has been breached."""
        return (
            self.iterations_used >= self.max_iterations or
            self.tool_calls_used >= self.max_tool_calls or
            self.llm_calls_used >= self.max_llm_calls or
            self.execution_time_seconds >= self.max_execution_time_seconds
        )
    
    def get_remaining(self) -> Dict[str, int]:
        """Calculates the available headroom for each resource type."""
        return {
            "iterations": self.max_iterations - self.iterations_used,
            "tool_calls": self.max_tool_calls - self.tool_calls_used,
            "llm_calls": self.max_llm_calls - self.llm_calls_used,
            "execution_time": int(self.max_execution_time_seconds - self.execution_time_seconds)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializes current budget state for monitoring or persistence."""
        return asdict(self)


@dataclass
class RuntimeContext:
    """Encapsulates the full execution state of a specific agent task.

    Attributes:
        task_id (str): Unique UUID for the task session.
        user_id (str): Reference to the owner of the task.
        command (str): The original natural language instruction.
        state (RuntimeState): The current position in the FSM (Reasoning, Executing, etc).
        budget (ReasoningBudget): Resource usage tracker for this context.
        start_time (Optional[datetime]): Time of initialization.
        end_time (Optional[datetime]): Time of completion/failure.
        result (Optional[Any]): Final output payload on success.
        error (Optional[str]): Error description on failure.
        metadata (Dict[str, Any]): Arbitrary key-value store for task extensions.
    """
    task_id: str
    user_id: str
    command: str
    state: RuntimeState = RuntimeState.IDLE
    budget: ReasoningBudget = field(default_factory=ReasoningBudget)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converts the runtime context to a portable JSON-serializable dictionary."""
        data = {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "command": self.command,
            "state": self.state.value,
            "budget": self.budget.to_dict(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata
        }
        return data


class AgentRuntime:
    """The master controller for the Stuart agent reasoning environment.

    Orchestrates the lifecycle of individual tasks, ensuring that the reasoning
    engine remains within safety budgets, persists state between iterations,
    and handles graceful interrupts (SIGINT/SIGTERM).

    Attributes:
        current_context (Optional[RuntimeContext]): The state of the active task.
        is_shutting_down (bool): Flag indicating the runtime is closing.
        cancel_requested (bool): Flag indicating the current task should abort.
        db (Optional[Connection]): Persistence handle for runtime state storage.
    """
    
    def __init__(
        self,
        max_iterations: int = 20,
        max_tool_calls: int = 50,
        max_llm_calls: int = 100,
        max_execution_time: int = 300,
        enable_reflection: bool = True,
        enable_state_persistence: bool = True
    ):
        """
        Initialize Agent Runtime
        
        Args:
            max_iterations: Maximum reasoning iterations per task
            max_tool_calls: Maximum tool calls per task
            max_llm_calls: Maximum LLM calls per task
            max_execution_time: Maximum execution time in seconds
            enable_reflection: Enable reflection steps
            enable_state_persistence: Enable state persistence
        """
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.max_llm_calls = max_llm_calls
        self.max_execution_time = max_execution_time
        self.enable_reflection = enable_reflection
        self.enable_state_persistence = enable_state_persistence
        
        # Components
        self.logger = get_logging_system()
        self.tracing = get_tracing_system()
        self.event_bus = get_event_bus()
        try:
            self.db = get_db_connection() if enable_state_persistence else None
        except RuntimeError as e:
            self.logger.warning(f"Database connection not available: {e}. Disabling state persistence.")
            self.db = None
            self.enable_state_persistence = False
        
        # Runtime state
        self.current_context: Optional[RuntimeContext] = None
        self.is_shutting_down = False
        self.cancel_requested = False
        
        # Register signal handlers
        self._register_signal_handlers()
        
        self.logger.info("AgentRuntime initialized", config={
            "max_iterations": max_iterations,
            "max_tool_calls": max_tool_calls,
            "max_llm_calls": max_llm_calls,
            "max_execution_time": max_execution_time,
            "enable_reflection": enable_reflection,
            "enable_state_persistence": enable_state_persistence
        })
    
    def _register_signal_handlers(self):
        """Register signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.warning("Shutdown signal received", signal=signum)
            self.shutdown()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def execute_task(
        self,
        task_id: str,
        user_id: str,
        command: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a task with full reasoning loop
        
        Args:
            task_id: Unique task identifier
            user_id: User identifier
            command: Command to execute
            metadata: Optional metadata
        
        Returns:
            Execution result dictionary
        """
        # Create correlation context
        with CorrelationContext(correlation_id=task_id, metadata={"user_id": user_id}):
            # Create trace
            with self.tracing.start_span("agent_runtime.execute_task") as span:
                span.tags["task_id"] = task_id
                span.tags["user_id"] = user_id
                
                try:
                    # Initialize context
                    context = self._initialize_context(task_id, user_id, command, metadata)
                    self.current_context = context
                    
                    # Publish task started event
                    self.event_bus.publish(Event.create(
                        event_type=EventType.TASK_STARTED,
                        payload={
                            "task_id": task_id,
                            "user_id": user_id,
                            "command": command
                        },
                        source_component="agent_runtime",
                        trace_id=self.tracing.get_current_trace_id() or "no-trace",
                        correlation_id=get_correlation_id() or "no-correlation",
                        workflow_id=task_id
                    ))
                    
                    # Execute reasoning loop
                    result = self._reasoning_loop(context)
                    
                    # Mark as completed
                    context.state = RuntimeState.COMPLETED
                    context.end_time = datetime.utcnow()
                    context.result = result
                    
                    # Persist final state
                    if self.enable_state_persistence:
                        self._persist_state(context)
                    
                    # Publish task completed event
                    self.event_bus.publish(Event.create(
                        event_type=EventType.TASK_COMPLETED,
                        payload={
                            "task_id": task_id,
                            "result": result,
                            "iterations": context.budget.iterations_used,
                            "duration_seconds": context.budget.execution_time_seconds
                        },
                        source_component="agent_runtime",
                        trace_id=self.tracing.get_current_trace_id() or "no-trace",
                        correlation_id=get_correlation_id() or "no-correlation",
                        workflow_id=task_id
                    ))
                    
                    self.logger.info(
                        "Task completed successfully",
                        task_id=task_id,
                        iterations=context.budget.iterations_used,
                        duration=context.budget.execution_time_seconds
                    )
                    
                    return {
                        "status": "completed",
                        "task_id": task_id,
                        "result": result,
                        "budget_used": context.budget.to_dict()
                    }
                    
                except Exception as e:
                    self.logger.error(
                        "Task execution failed",
                        task_id=task_id,
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    
                    if self.current_context:
                        self.current_context.state = RuntimeState.FAILED
                        self.current_context.error = str(e)
                        self.current_context.end_time = datetime.utcnow()
                        
                        if self.enable_state_persistence:
                            self._persist_state(self.current_context)
                    
                    # Publish task failed event
                    self.event_bus.publish(Event.create(
                        event_type=EventType.TASK_FAILED,
                        payload={
                            "task_id": task_id,
                            "error": str(e),
                            "error_type": type(e).__name__
                        },
                        source_component="agent_runtime",
                        trace_id=self.tracing.get_current_trace_id() or "no-trace",
                        correlation_id=get_correlation_id() or "no-correlation",
                        workflow_id=task_id
                    ))
                    
                    span.tags["error"] = True
                    span.tags["error_message"] = str(e)
                    
                    return {
                        "status": "failed",
                        "task_id": task_id,
                        "error": str(e)
                    }
                
                finally:
                    self.current_context = None
    
    def _initialize_context(
        self,
        task_id: str,
        user_id: str,
        command: str,
        metadata: Optional[Dict[str, Any]]
    ) -> RuntimeContext:
        """Initialize runtime context for task execution"""
        budget = ReasoningBudget(
            max_iterations=self.max_iterations,
            max_tool_calls=self.max_tool_calls,
            max_llm_calls=self.max_llm_calls,
            max_execution_time_seconds=self.max_execution_time
        )
        
        context = RuntimeContext(
            task_id=task_id,
            user_id=user_id,
            command=command,
            state=RuntimeState.INITIALIZING,
            budget=budget,
            start_time=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        self.logger.info(
            "Runtime context initialized",
            task_id=task_id,
            budget=budget.to_dict()
        )
        
        return context
    
    def _reasoning_loop(self, context: RuntimeContext) -> Any:
        """
        Main reasoning loop
        
        Executes iterative reasoning until completion or budget exhaustion.
        """
        self.logger.info("Starting reasoning loop", task_id=context.task_id)
        
        if not hasattr(self, "orchestrator") or not self.orchestrator:
            raise RuntimeError("Orchestrator not initialized in AgentRuntime")
            
        context.state = RuntimeState.REASONING
        start_time = time.time()
        
        # Prepare toolset for the task
        if self.orchestrator.toolset_distributor:
            schema_array = self.orchestrator.toolset_distributor.get_tools_for_task(context.command)
        else:
            schema_array = [t.get_metadata() for t in self.orchestrator.executor.registry.get_all_tools()]
            
        # Prepare plan injection
        known_plan_injection = ""
        if self.orchestrator.plan_library:
            plan = self.orchestrator.plan_library.lookup_plan(context.command)
            if plan:
                known_plan_injection = f"\n<PROVEN_PLAN>\n{plan}\n</PROVEN_PLAN>\n"
        
        last_tool_call_signature = None
        consecutive_errors = 0
        reflection_active = False
        
        while not context.budget.is_exhausted():
            # Check for cancellation
            if self.cancel_requested or self.is_shutting_down:
                self.logger.warning("Task cancelled", task_id=context.task_id)
                context.state = RuntimeState.CANCELLING
                raise RuntimeError("Task cancelled")
            
            # Update iteration count
            context.budget.iterations_used += 1
            iteration_num = context.budget.iterations_used
            
            self.logger.info(
                "Reasoning iteration",
                task_id=context.task_id,
                iteration=iteration_num,
                remaining_budget=context.budget.get_remaining()
            )
            
            with self.tracing.start_span(f"reasoning_iteration_{iteration_num}") as span:
                span.tags["iteration"] = iteration_num
                
                # EXECUTE ONE STEP
                result = self.orchestrator.run_reasoning_step(
                    text=context.command,
                    schema_array=schema_array,
                    known_plan_injection=known_plan_injection,
                    last_tool_call_signature=last_tool_call_signature,
                    consecutive_errors=consecutive_errors,
                    budget=context.budget.max_iterations
                )
                
                # Handle Model Results
                if result.is_final:
                    # Record successful plan if no errors
                    if consecutive_errors == 0 and self.orchestrator.plan_library:
                        # Accessing private attr for now as it's part of the same system
                        self.orchestrator.plan_library.record_successful_plan(
                            context.command, 
                            getattr(self.orchestrator, "_current_loop_tools", [])
                        )
                    return result.answer
                
                if result.error and not result.observation:
                    raise RuntimeError(result.error)
                
                # Handle tool call signatures for loop detection
                if result.tool_call:
                    import json
                    tool_name = result.tool_call.get("tool")
                    action = result.tool_call.get("action")
                    params = result.tool_call.get("parameters", {})
                    last_tool_call_signature = f"{tool_name}:{action}:{hash(json.dumps(params, sort_keys=True))}"
                    
                    # Update tool call count
                    context.budget.tool_calls_used += 1
                    
                    if "Execution Result from" in (result.observation or ""):
                        consecutive_errors = 0
                    else:
                        consecutive_errors += 1
                else:
                    consecutive_errors += 1
                
                # Update LLM call count
                context.budget.llm_calls_used += 1
                
                # --- Task 6.4: Reflection Step ---
                if self.enable_reflection and consecutive_errors >= 2 and not reflection_active:
                    self.logger.warning("Agent stuck. Triggering reflection step.", task_id=context.task_id)
                    reflection_active = True
                    context.state = RuntimeState.REFLECTING
                    
                    reflection_msg = (
                        "SYSTEM REFLECTION: You have encountered multiple consecutive errors or non-standard responses. "
                        "Stop and re-evaluate your current approach. Is there a simpler tool or a different way to achieve the goal? "
                        "Explain your new strategy in your next thought."
                    )
                    from memory.short_term import MemoryRole
                    self.orchestrator.memory.commit_interaction(MemoryRole.SYSTEM, reflection_msg)
                elif reflection_active and consecutive_errors == 0:
                    reflection_active = False
                    context.state = RuntimeState.REASONING
                
                # Update execution time
                context.budget.execution_time_seconds = time.time() - start_time
                
                # Persist state after each iteration
                if self.enable_state_persistence:
                    self._persist_state(context)
        
        # Budget exhausted
        self.logger.warning(
            "Budget exhausted",
            task_id=context.task_id,
            budget_used=context.budget.to_dict()
        )
        raise RuntimeError("Reasoning budget exhausted")

    
    def _persist_state(self, context: RuntimeContext) -> None:
        """Persist runtime state to database"""
        if not self.db:
            return
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO runtime_state (task_id, state_data, updated_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (task_id) DO UPDATE
                        SET state_data = %s, updated_at = %s
                        """,
                        (
                            context.task_id,
                            context.to_dict(),
                            datetime.utcnow(),
                            context.to_dict(),
                            datetime.utcnow()
                        )
                    )
                    conn.commit()
            
            self.logger.debug("State persisted", task_id=context.task_id)
            
        except Exception as e:
            self.logger.error(
                "Failed to persist state",
                task_id=context.task_id,
                error=str(e)
            )
    
    def resume_task(self, task_id: str) -> Dict[str, Any]:
        """
        Resume task from persisted state
        
        Args:
            task_id: Task ID to resume
        
        Returns:
            Execution result
        """
        self.logger.info("Resuming task", task_id=task_id)
        
        # Load persisted state
        # TODO: Implement state loading from database
        raise NotImplementedError("Task resumption not yet implemented")
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel running task
        
        Args:
            task_id: Task ID to cancel
        
        Returns:
            True if cancellation initiated
        """
        if self.current_context and self.current_context.task_id == task_id:
            self.logger.warning("Cancelling task", task_id=task_id)
            self.cancel_requested = True
            
            # Publish cancellation event
            self.event_bus.publish(
                EventType.TASK_CANCELLED,
                data={"task_id": task_id},
                workflow_id=task_id
            )
            
            return True
        
        return False
    
    def shutdown(self, wait_for_completion: bool = True) -> None:
        """
        Graceful shutdown
        
        Args:
            wait_for_completion: Wait for in-flight tasks to complete
        """
        self.logger.warning("Initiating shutdown", wait_for_completion=wait_for_completion)
        self.is_shutting_down = True
        
        if wait_for_completion and self.current_context:
            self.logger.info("Waiting for in-flight task to complete")
            # Task will check is_shutting_down flag and complete gracefully
        else:
            self.cancel_requested = True
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get runtime health status
        
        Returns:
            Health status dictionary
        """
        status = {
            "healthy": not self.is_shutting_down,
            "state": "running" if self.current_context else "idle",
            "current_task": self.current_context.task_id if self.current_context else None,
            "shutting_down": self.is_shutting_down,
            "config": {
                "max_iterations": self.max_iterations,
                "max_tool_calls": self.max_tool_calls,
                "max_llm_calls": self.max_llm_calls,
                "max_execution_time": self.max_execution_time
            }
        }
        
        if self.current_context:
            status["current_task_budget"] = self.current_context.budget.to_dict()
        
        return status
