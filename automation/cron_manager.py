"""
Cron Manager (Phase 9B)

Proactive scheduling engine inspired by Hermes Agent and Khoj.
Wraps the existing AutomationScheduler with:
  - Disk persistence: jobs survive agent restarts via data/cron_jobs.json
  - Natural-language job definitions dispatched through the Orchestrator
  - Full CRUD: add, remove, list, load from disk

Usage:
    cron = CronManager(scheduler, orchestrator_callback)
    cron.load_persisted()  # restore jobs from last session
    cron.add("08:00", "Summarize my emails from last night")
"""

import json
import os
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from observability import get_logging_system
from automation.scheduler import AutomationScheduler


class CronJob:
    """Represents a single persisted cron job definition with scheduling metadata.

    Attributes:
        job_id (str): Unique UUID-like identifier prefixed with 'cron_'.
        time_str (str): 24-hour time format ('HH:MM') for 'daily' jobs.
        prompt (str): The natural language instruction to be injected into the agent.
        job_type (str): The scheduling strategy ('daily' or 'interval').
        interval_minutes (int): Recursion frequency for 'interval' jobs.
        created_at (str): ISO timestamp of the job's creation.
    """

    def __init__(self, job_id: str, time_str: str, prompt: str, 
                 job_type: str = "daily", interval_minutes: int = 0,
                 created_at: str = None):
        self.job_id = job_id
        self.time_str = time_str
        self.prompt = prompt
        self.job_type = job_type  # "daily" or "interval"
        self.interval_minutes = interval_minutes
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "time_str": self.time_str,
            "prompt": self.prompt,
            "job_type": self.job_type,
            "interval_minutes": self.interval_minutes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CronJob":
        return cls(
            job_id=data["job_id"],
            time_str=data.get("time_str", ""),
            prompt=data["prompt"],
            job_type=data.get("job_type", "daily"),
            interval_minutes=data.get("interval_minutes", 0),
            created_at=data.get("created_at"),
        )


class CronManager:
    """
    High-level cron management layer.
    
    Provides disk-persisted scheduled jobs that fire prompts through
    the PCA Orchestrator's ReAct loop automatically.
    """

    PERSIST_PATH = os.path.join("data", "cron_jobs.json")

    def __init__(self, scheduler: AutomationScheduler):
        self.logger = get_logging_system()
        self.scheduler = scheduler
        self.jobs: Dict[str, CronJob] = {}

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.PERSIST_PATH), exist_ok=True)

        self.logger.info("CronManager initialized (Phase 9B).")

    def add(self, time_str: str, prompt: str, 
            job_type: str = "daily", interval_minutes: int = 0) -> str:
        """
        Add a new cron job.
        
        Args:
            time_str: For daily jobs, a 24hr time like "08:00". Ignored for interval jobs.
            prompt: The natural-language instruction to send through the Orchestrator.
            job_type: "daily" or "interval"
            interval_minutes: For interval jobs, how often to run (in minutes).
            
        Returns:
            The unique job_id.
        """
        job_id = f"cron_{str(uuid.uuid4())[:8]}"

        # Register with the underlying scheduler
        if job_type == "daily":
            scheduler_id = self.scheduler.add_daily_job(time_str, prompt)
        elif job_type == "interval":
            scheduler_id = self.scheduler.add_interval_job(interval_minutes, prompt)
        else:
            raise ValueError(f"Unknown job_type: {job_type}. Use 'daily' or 'interval'.")

        # Create our persistent record
        cron_job = CronJob(
            job_id=job_id,
            time_str=time_str,
            prompt=prompt,
            job_type=job_type,
            interval_minutes=interval_minutes,
        )
        # Store reference to the scheduler's internal job ID for cancellation
        cron_job._scheduler_id = scheduler_id
        self.jobs[job_id] = cron_job

        # Persist to disk
        self._save_to_disk()

        self.logger.info(f"Cron job added: [{job_id}] {job_type} @ {time_str or f'every {interval_minutes}min'} ? '{prompt[:40]}...'")
        return job_id

    def remove(self, job_id: str) -> bool:
        """Remove a cron job by its ID."""
        cron_job = self.jobs.get(job_id)
        if not cron_job:
            return False

        # Cancel in the underlying scheduler
        scheduler_id = getattr(cron_job, '_scheduler_id', None)
        if scheduler_id:
            self.scheduler.cancel_job(scheduler_id)

        del self.jobs[job_id]
        self._save_to_disk()

        self.logger.info(f"Cron job removed: [{job_id}]")
        return True

    def list_all(self) -> str:
        """Return a formatted string listing all active cron jobs."""
        if not self.jobs:
            return "? No scheduled cron jobs."

        lines = ["? **Active Cron Jobs:**\n"]
        for job_id, job in self.jobs.items():
            if job.job_type == "daily":
                schedule_str = f"Daily @ {job.time_str}"
            else:
                schedule_str = f"Every {job.interval_minutes} min"
            
            lines.append(f"  ? `{job_id}` | {schedule_str} | \"{job.prompt[:50]}...\"")

        return "\n".join(lines)

    def get_jobs_data(self) -> List[Dict[str, Any]]:
        """Return all jobs as a list of dicts (for API responses)."""
        return [job.to_dict() for job in self.jobs.values()]

    def load_persisted(self):
        """Load cron jobs from disk and re-register them with the scheduler."""
        if not os.path.exists(self.PERSIST_PATH):
            self.logger.debug("No persisted cron jobs found.")
            return

        try:
            with open(self.PERSIST_PATH, "r") as f:
                data = json.load(f)

            loaded_count = 0
            for job_data in data:
                cron_job = CronJob.from_dict(job_data)

                # Re-register with scheduler
                if cron_job.job_type == "daily":
                    scheduler_id = self.scheduler.add_daily_job(cron_job.time_str, cron_job.prompt)
                elif cron_job.job_type == "interval":
                    scheduler_id = self.scheduler.add_interval_job(cron_job.interval_minutes, cron_job.prompt)
                else:
                    continue

                cron_job._scheduler_id = scheduler_id
                self.jobs[cron_job.job_id] = cron_job
                loaded_count += 1

            self.logger.info(f"Restored {loaded_count} cron jobs from disk.")

        except Exception as e:
            self.logger.error(f"Failed to load persisted cron jobs: {e}")

    def _save_to_disk(self):
        """Persist all current jobs to data/cron_jobs.json."""
        try:
            data = [job.to_dict() for job in self.jobs.values()]
            with open(self.PERSIST_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to persist cron jobs: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Return status dict for the health endpoint."""
        return {
            "active_jobs": len(self.jobs),
            "scheduler_running": self.scheduler.running,
            "persistence_path": self.PERSIST_PATH,
        }
