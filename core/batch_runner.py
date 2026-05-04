"""
Batch Runner (Feature #6: Advanced Orchestration)

Accepts a list of tasks and dispatches them via the SubAgentPool with full
progress tracking, retry logic, and a consolidated markdown report.

Modes:
  - parallel:   Fan-out all tasks concurrently via SubAgentPool
  - sequential: Execute tasks one-by-one in order
  - pipeline:   Output of task N is prepended as context for task N+1
"""

import os
import json
import time
import threading
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from uuid import uuid4

from observability import get_logging_system
from core.sub_agent_pool import SubAgentPool, SubTaskResult


class BatchMode(str, Enum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    PIPELINE = "pipeline"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class BatchTask:
    """A single task within a batch."""
    task_id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0
    retries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "status": self.status.value,
            "output": self.output[:500],  # Truncate for persistence
            "error": self.error,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
        }


@dataclass
class BatchManifest:
    """Full batch execution manifest with metadata."""
    batch_id: str
    mode: BatchMode
    tasks: List[BatchTask] = field(default_factory=list)
    created_at: str = ""
    completed_at: str = ""
    total_duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "mode": self.mode.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "total_duration_ms": self.total_duration_ms,
        }


class BatchRunner:
    """
    Multi-task execution engine with progress tracking and persistence.

    Dispatches tasks through the SubAgentPool in one of three modes:
    parallel, sequential, or pipeline. Results are persisted to
    data/batches/{batch_id}.json for resume and auditing.
    """

    BATCHES_DIR = os.path.join("data", "batches")

    def __init__(
        self,
        sub_agent_pool: SubAgentPool,
        event_bus=None,
        max_retries: int = 1,
    ):
        self.logger = get_logging_system()
        self.pool = sub_agent_pool
        self.event_bus = event_bus
        self.max_retries = max_retries

        os.makedirs(self.BATCHES_DIR, exist_ok=True)
        self._active_manifest: Optional[BatchManifest] = None
        self.logger.info("BatchRunner initialized (Feature #6).")

    def run_batch(
        self,
        tasks: List[str],
        mode: BatchMode = BatchMode.PARALLEL,
        timeout: float = 300.0,
    ) -> BatchManifest:
        """
        Execute a batch of tasks in the specified mode.

        Args:
            tasks: List of natural-language task descriptions.
            mode: Execution mode (parallel, sequential, pipeline).
            timeout: Max seconds for parallel mode.

        Returns:
            BatchManifest with per-task results.
        """
        batch_id = uuid4().hex[:12]
        manifest = BatchManifest(
            batch_id=batch_id,
            mode=mode,
            tasks=[
                BatchTask(task_id=f"{batch_id}_{i}", description=t)
                for i, t in enumerate(tasks)
            ],
            created_at=datetime.now().isoformat(),
        )
        self._active_manifest = manifest
        self._emit_event("batch_started", {"batch_id": batch_id, "count": len(tasks), "mode": mode.value})
        self.logger.info(f"Batch {batch_id} started: {len(tasks)} tasks in {mode.value} mode.")

        start = time.time()

        if mode == BatchMode.PARALLEL:
            self._run_parallel(manifest, timeout)
        elif mode == BatchMode.SEQUENTIAL:
            self._run_sequential(manifest)
        elif mode == BatchMode.PIPELINE:
            self._run_pipeline(manifest)

        manifest.total_duration_ms = (time.time() - start) * 1000
        manifest.completed_at = datetime.now().isoformat()

        # Persist
        self._save_manifest(manifest)
        self._emit_event("batch_completed", {
            "batch_id": batch_id,
            "success": sum(1 for t in manifest.tasks if t.status == TaskStatus.DONE),
            "failed": sum(1 for t in manifest.tasks if t.status == TaskStatus.FAILED),
            "duration_ms": manifest.total_duration_ms,
        })
        self.logger.info(f"Batch {batch_id} completed in {manifest.total_duration_ms:.0f}ms.")
        self._active_manifest = None
        return manifest

    # ── Execution Modes ──────────────────────────────────────────────

    def _run_parallel(self, manifest: BatchManifest, timeout: float):
        """Fan-out all tasks concurrently via SubAgentPool."""
        descriptions = [t.description for t in manifest.tasks]
        for t in manifest.tasks:
            t.status = TaskStatus.RUNNING

        results = self.pool.execute_parallel(descriptions, timeout=timeout)

        for task, result in zip(manifest.tasks, results):
            task.output = result.output
            task.duration_ms = result.duration_ms
            task.status = TaskStatus.DONE if result.success else TaskStatus.FAILED
            if not result.success:
                task.error = result.output
                self._maybe_retry(task, manifest)
            self._emit_task_event(task, manifest.batch_id)

    def _run_sequential(self, manifest: BatchManifest):
        """Execute tasks one-by-one in order."""
        for task in manifest.tasks:
            task.status = TaskStatus.RUNNING
            result = self._execute_single(task.description)
            task.output = result.output
            task.duration_ms = result.duration_ms
            task.status = TaskStatus.DONE if result.success else TaskStatus.FAILED
            if not result.success:
                task.error = result.output
                self._maybe_retry(task, manifest)
            self._emit_task_event(task, manifest.batch_id)

    def _run_pipeline(self, manifest: BatchManifest):
        """Pipeline mode: output of task N feeds into task N+1 as context."""
        previous_output = ""
        for task in manifest.tasks:
            task.status = TaskStatus.RUNNING
            augmented_description = task.description
            if previous_output:
                augmented_description = (
                    f"CONTEXT FROM PREVIOUS STEP:\n{previous_output[:2000]}\n\n"
                    f"CURRENT TASK:\n{task.description}"
                )

            result = self._execute_single(augmented_description)
            task.output = result.output
            task.duration_ms = result.duration_ms
            task.status = TaskStatus.DONE if result.success else TaskStatus.FAILED

            if result.success:
                previous_output = result.output
            else:
                task.error = result.output
                self._maybe_retry(task, manifest)
                # On pipeline failure, carry forward the error context
                previous_output = f"[PREVIOUS STEP FAILED]: {result.output}"

            self._emit_task_event(task, manifest.batch_id)

    # ── Helpers ───────────────────────────────────────────────────────

    def _execute_single(self, description: str) -> SubTaskResult:
        """Execute a single task via the sub-agent pool (1-task parallel)."""
        results = self.pool.execute_parallel([description], timeout=120.0)
        return results[0] if results else SubTaskResult(
            task=description, success=False, output="No result returned."
        )

    def _maybe_retry(self, task: BatchTask, manifest: BatchManifest):
        """Retry a failed task if under the retry limit."""
        if task.retries < self.max_retries:
            task.retries += 1
            self.logger.info(f"Retrying task {task.task_id} (attempt {task.retries})...")
            result = self._execute_single(task.description)
            task.output = result.output
            task.duration_ms += result.duration_ms
            task.status = TaskStatus.DONE if result.success else TaskStatus.FAILED
            if not result.success:
                task.error = result.output

    def _emit_event(self, event_type: str, payload: Dict[str, Any]):
        """Emit a batch event on the EventBus."""
        if not self.event_bus:
            return
        try:
            from events.event_types import Event, EventType
            event = Event.create(
                event_type=EventType(event_type),
                source_component="BatchRunner",
                payload=payload,
                trace_id=uuid4().hex[:16],
                correlation_id=uuid4().hex[:16],
            )
            self.event_bus.publish(event)
        except Exception as e:
            self.logger.debug(f"Event emit failed (non-fatal): {e}")

    def _emit_task_event(self, task: BatchTask, batch_id: str):
        """Emit a per-task completion event."""
        self._emit_event("batch_task_completed", {
            "batch_id": batch_id,
            "task_id": task.task_id,
            "status": task.status.value,
            "duration_ms": task.duration_ms,
        })

    def _save_manifest(self, manifest: BatchManifest):
        """Persist batch manifest to disk."""
        path = os.path.join(self.BATCHES_DIR, f"{manifest.batch_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(manifest.to_dict(), f, indent=2)
            self.logger.debug(f"Batch manifest saved to {path}")
        except Exception as e:
            self.logger.error(f"Failed to save batch manifest: {e}")

    # ── Reporting ─────────────────────────────────────────────────────

    def generate_report(self, manifest: BatchManifest) -> str:
        """Generate a markdown execution report from a batch manifest."""
        done = sum(1 for t in manifest.tasks if t.status == TaskStatus.DONE)
        failed = sum(1 for t in manifest.tasks if t.status == TaskStatus.FAILED)
        total = len(manifest.tasks)

        lines = [
            f"## 📦 Batch Report `{manifest.batch_id}`\n",
            f"**Mode:** {manifest.mode.value} | **Tasks:** {total} | "
            f"**✅ Done:** {done} | **❌ Failed:** {failed} | "
            f"**Duration:** {manifest.total_duration_ms:.0f}ms\n",
            "---",
        ]

        for i, task in enumerate(manifest.tasks, 1):
            icon = "✅" if task.status == TaskStatus.DONE else "❌"
            lines.append(f"### {icon} Task {i}: {task.description[:80]}")
            lines.append(f"*Status:* {task.status.value} | *Duration:* {task.duration_ms:.0f}ms")
            if task.retries > 0:
                lines.append(f"*Retries:* {task.retries}")
            lines.append(f"\n{task.output[:1000]}\n")
            if task.error:
                lines.append(f"> ⚠️ Error: {task.error[:300]}\n")
            lines.append("---")

        return "\n".join(lines)

    def list_batches(self) -> List[Dict[str, Any]]:
        """List all persisted batch manifests."""
        batches = []
        if not os.path.exists(self.BATCHES_DIR):
            return batches
        for filename in sorted(os.listdir(self.BATCHES_DIR), reverse=True):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.BATCHES_DIR, filename), "r") as f:
                        data = json.load(f)
                    batches.append({
                        "batch_id": data.get("batch_id"),
                        "mode": data.get("mode"),
                        "tasks": len(data.get("tasks", [])),
                        "created_at": data.get("created_at"),
                    })
                except Exception:
                    pass
        return batches
