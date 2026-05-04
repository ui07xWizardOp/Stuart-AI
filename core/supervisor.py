"""
Supervisor-Worker Multi-Agent (Feature #7: Advanced Orchestration)

A supervisor agent that:
1. Decomposes a complex goal into structured sub-tasks using the LLM
2. Delegates each sub-task to isolated worker agents via SubAgentPool
3. Monitors worker outputs and decides if re-delegation is needed
4. Synthesizes all worker outputs into a unified final answer
"""

import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from uuid import uuid4

from observability import get_logging_system
from core.model_router import ModelRouter, ModelTier
from core.sub_agent_pool import SubAgentPool, SubTaskResult


@dataclass
class DelegationPlan:
    """A structured decomposition of a complex goal into sub-tasks."""
    goal: str
    sub_tasks: List[str] = field(default_factory=list)
    reasoning: str = ""
    delegation_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "sub_tasks": self.sub_tasks,
            "reasoning": self.reasoning,
            "delegation_id": self.delegation_id,
        }


@dataclass
class DelegationResult:
    """Outcome of the full supervisor-worker cycle."""
    delegation_id: str
    goal: str
    sub_task_results: List[SubTaskResult] = field(default_factory=list)
    synthesized_output: str = ""
    total_duration_ms: float = 0.0
    success: bool = True


class SupervisorAgent:
    """
    Decomposes complex goals, delegates to worker agents, and synthesizes results.

    The supervisor uses an LLM call to break a goal into atomic sub-tasks,
    then dispatches each sub-task to an independent worker via the SubAgentPool.
    After all workers complete, it uses another LLM call to synthesize
    the combined outputs into a coherent final answer.

    Attributes:
        router (ModelRouter): For LLM calls (decomposition + synthesis).
        pool (SubAgentPool): For worker agent execution.
        max_delegation_depth (int): Prevents infinite delegation chains.
        event_bus: Optional EventBus for emitting delegation events.
    """

    DECOMPOSITION_PROMPT = """You are a Task Decomposition Engine.

Given a complex goal, break it into 2-5 independent, atomic sub-tasks that can
each be solved by a general-purpose AI agent with access to code execution,
web search, file operations, and knowledge retrieval tools.

Rules:
- Each sub-task must be self-contained and independently solvable.
- Order them logically (dependencies first).
- If the goal is already atomic, return it as a single sub-task.

Respond ONLY in this exact JSON format:
{
  "reasoning": "Brief explanation of your decomposition strategy",
  "sub_tasks": [
    "Sub-task 1 description",
    "Sub-task 2 description"
  ]
}"""

    SYNTHESIS_PROMPT = """You are a Result Synthesis Engine.

You received outputs from multiple worker agents, each solving a sub-task
of a larger goal. Your job is to merge their outputs into a single, coherent,
well-structured final answer that fully addresses the original goal.

Rules:
- Integrate all relevant information from worker outputs.
- Resolve any contradictions by favoring the most detailed/accurate output.
- Format the final answer clearly with headings if needed.
- Do NOT fabricate information not present in the worker outputs.
"""

    def __init__(
        self,
        router: ModelRouter,
        sub_agent_pool: SubAgentPool,
        event_bus=None,
        max_delegation_depth: int = 2,
    ):
        self.logger = get_logging_system()
        self.router = router
        self.pool = sub_agent_pool
        self.event_bus = event_bus
        self.max_delegation_depth = max_delegation_depth
        self.logger.info(f"SupervisorAgent initialized (max_depth={max_delegation_depth}).")

    def delegate(self, goal: str, depth: int = 0) -> DelegationResult:
        """
        Full supervisor cycle: decompose → delegate → synthesize.

        Args:
            goal: The complex goal to accomplish.
            depth: Current recursion depth (for preventing infinite chains).

        Returns:
            DelegationResult with synthesized output.
        """
        delegation_id = uuid4().hex[:12]
        start = time.time()
        self.logger.info(f"Delegation {delegation_id} started (depth={depth}): {goal[:80]}...")

        self._emit_event("delegation_started", {
            "delegation_id": delegation_id,
            "goal": goal[:200],
            "depth": depth,
        })

        # Guard against infinite delegation
        if depth >= self.max_delegation_depth:
            self.logger.warning(f"Max delegation depth ({self.max_delegation_depth}) reached. Executing directly.")
            results = self.pool.execute_parallel([goal], timeout=120.0)
            return DelegationResult(
                delegation_id=delegation_id,
                goal=goal,
                sub_task_results=results,
                synthesized_output=results[0].output if results else "Delegation depth limit reached.",
                total_duration_ms=(time.time() - start) * 1000,
                success=all(r.success for r in results),
            )

        # Phase 1: Decompose
        plan = self._decompose(goal, delegation_id)
        if not plan.sub_tasks:
            self.logger.warning("Decomposition produced no sub-tasks. Running goal directly.")
            plan.sub_tasks = [goal]

        self.logger.info(f"Delegation {delegation_id}: Decomposed into {len(plan.sub_tasks)} sub-tasks.")

        # Phase 2: Delegate to workers
        worker_results = self.pool.execute_parallel(plan.sub_tasks, timeout=180.0)

        # Phase 3: Check for failures and decide on re-delegation
        failed = [r for r in worker_results if not r.success]
        if failed and depth + 1 < self.max_delegation_depth:
            self.logger.info(f"{len(failed)} workers failed. Attempting re-delegation...")
            for fr in failed:
                retry_result = self.pool.execute_parallel([fr.task], timeout=60.0)
                if retry_result and retry_result[0].success:
                    # Replace the failed result
                    idx = worker_results.index(fr)
                    worker_results[idx] = retry_result[0]

        # Phase 4: Synthesize
        synthesized = self._synthesize(goal, plan.sub_tasks, worker_results)

        duration = (time.time() - start) * 1000
        result = DelegationResult(
            delegation_id=delegation_id,
            goal=goal,
            sub_task_results=worker_results,
            synthesized_output=synthesized,
            total_duration_ms=duration,
            success=all(r.success for r in worker_results),
        )

        self._emit_event("delegation_completed", {
            "delegation_id": delegation_id,
            "sub_tasks": len(plan.sub_tasks),
            "success": result.success,
            "duration_ms": duration,
        })

        self.logger.info(f"Delegation {delegation_id} completed in {duration:.0f}ms.")
        return result

    # ── Internal Methods ──────────────────────────────────────────────

    def _decompose(self, goal: str, delegation_id: str) -> DelegationPlan:
        """Use the LLM to decompose a goal into sub-tasks."""
        messages = [
            {"role": "system", "content": self.DECOMPOSITION_PROMPT},
            {"role": "user", "content": f"GOAL:\n{goal}"},
        ]

        try:
            response = self.router.execute_with_failover(messages, force_tier=ModelTier.FAST_CHEAP)
            # Parse JSON from response
            parsed = self._extract_json(response)
            return DelegationPlan(
                goal=goal,
                sub_tasks=parsed.get("sub_tasks", [goal]),
                reasoning=parsed.get("reasoning", ""),
                delegation_id=delegation_id,
            )
        except Exception as e:
            self.logger.error(f"Decomposition failed: {e}. Using goal as single task.")
            return DelegationPlan(
                goal=goal,
                sub_tasks=[goal],
                reasoning=f"Decomposition failed: {e}",
                delegation_id=delegation_id,
            )

    def _synthesize(
        self,
        goal: str,
        sub_tasks: List[str],
        results: List[SubTaskResult],
    ) -> str:
        """Use the LLM to merge worker outputs into a unified answer."""
        worker_report = ""
        for i, (task, result) in enumerate(zip(sub_tasks, results), 1):
            status = "✅ SUCCESS" if result.success else "❌ FAILED"
            worker_report += (
                f"\n### Worker {i}: {task[:100]}\n"
                f"**Status:** {status}\n"
                f"**Output:**\n{result.output[:2000]}\n"
                f"---\n"
            )

        messages = [
            {"role": "system", "content": self.SYNTHESIS_PROMPT},
            {"role": "user", "content": (
                f"ORIGINAL GOAL:\n{goal}\n\n"
                f"WORKER REPORTS:\n{worker_report}\n\n"
                f"Synthesize a complete, unified answer addressing the original goal."
            )},
        ]

        try:
            return self.router.execute_with_failover(messages)
        except Exception as e:
            self.logger.error(f"Synthesis failed: {e}")
            # Fallback: concatenate worker outputs
            return self.pool.merge_results(results)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract a JSON object from LLM response text."""
        # Try direct parse first
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            # Try to find JSON within the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            return {"sub_tasks": [], "reasoning": "Failed to parse decomposition."}

    def _emit_event(self, event_type: str, payload: Dict[str, Any]):
        """Emit a delegation event on the EventBus."""
        if not self.event_bus:
            return
        try:
            from events.event_types import Event, EventType
            event = Event.create(
                event_type=EventType(event_type),
                source_component="SupervisorAgent",
                payload=payload,
                trace_id=uuid4().hex[:16],
                correlation_id=uuid4().hex[:16],
            )
            self.event_bus.publish(event)
        except Exception as e:
            self.logger.debug(f"Event emit failed (non-fatal): {e}")
