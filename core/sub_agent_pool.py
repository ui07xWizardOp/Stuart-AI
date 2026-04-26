"""
Sub-Agent Pool (Phase 13: Parallel Sub-Agent Spawning)

Provides a pool of lightweight worker threads that can execute
sub-tasks concurrently. Each sub-agent gets its own isolated memory
but shares the tool registry and model router for efficiency.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from observability import get_logging_system


@dataclass
class SubTaskResult:
    """Result from a sub-agent execution."""
    task: str
    success: bool
    output: str
    duration_ms: float = 0.0


class SubAgentPool:
    """
    Manages a pool of worker threads for parallel sub-task execution.
    Each worker runs a simplified version of the Orchestrator's ReAct loop
    with its own isolated short-term memory.
    """

    def __init__(self, orchestrator_factory, max_workers: int = 3):
        """
        Args:
            orchestrator_factory: A callable that returns a configured Orchestrator instance.
                                  Each sub-agent gets its own orchestrator.
            max_workers: Maximum number of concurrent sub-agents.
        """
        self.logger = get_logging_system()
        self.orchestrator_factory = orchestrator_factory
        self.max_workers = max_workers
        self.logger.info(f"SubAgentPool initialized with {max_workers} worker slots.")

    def execute_parallel(self, tasks: List[str], timeout: float = 120.0) -> List[SubTaskResult]:
        """
        Execute multiple tasks in parallel using sub-agents.

        Args:
            tasks: List of natural-language task descriptions.
            timeout: Maximum seconds to wait for all tasks.

        Returns:
            List of SubTaskResult objects.
        """
        self.logger.info(f"Spawning {len(tasks)} parallel sub-agents...")

        results: List[SubTaskResult] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_to_task = {}
            for task_text in tasks:
                future = pool.submit(self._run_sub_agent, task_text)
                future_to_task[future] = task_text

            for future in as_completed(future_to_task, timeout=timeout):
                task_text = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Sub-agent failed for task '{task_text[:50]}...': {e}")
                    results.append(SubTaskResult(
                        task=task_text,
                        success=False,
                        output=f"Sub-agent error: {e}"
                    ))

        self.logger.info(f"All {len(tasks)} sub-agents completed. "
                         f"Success: {sum(1 for r in results if r.success)}/{len(results)}")
        return results

    def _run_sub_agent(self, task: str) -> SubTaskResult:
        """
        Runs a single sub-agent for one task.
        Uses a fresh orchestrator from the factory to ensure memory isolation.
        """
        import time
        start = time.time()

        try:
            # Get a fresh orchestrator (with isolated memory)
            orchestrator = self.orchestrator_factory()
            output = orchestrator.run(task)
            elapsed = (time.time() - start) * 1000

            return SubTaskResult(
                task=task,
                success=True,
                output=output,
                duration_ms=elapsed
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return SubTaskResult(
                task=task,
                success=False,
                output=str(e),
                duration_ms=elapsed
            )

    def merge_results(self, results: List[SubTaskResult]) -> str:
        """
        Merge multiple sub-agent results into a single formatted output.
        """
        lines = [f"## Parallel Execution Report ({len(results)} sub-tasks)\n"]
        for i, r in enumerate(results, 1):
            status = "✅" if r.success else "❌"
            lines.append(f"### {status} Sub-task {i}: {r.task[:80]}")
            lines.append(f"*Duration: {r.duration_ms:.0f}ms*\n")
            lines.append(r.output)
            lines.append("---")
        return "\n".join(lines)
