"""
Automation Scheduler (Task 21)

The underlying clock algorithm that wakes the Agent up on defined intervals.
Leverages the robust 'schedule' module.
"""

import schedule
import time
import threading
import uuid
from typing import Dict, Any, Callable

from observability import get_logging_system
import logging

class AutomationScheduler:
    
    def __init__(self, task_queue_push: Callable[[str], str]):

        try:
            self.logger = get_logging_system()
        except Exception:
            self.logger = logging.getLogger(__name__)
        # Direct callback to TaskQueue.push_background_task
        self.execute_callback = task_queue_push
        
        self.jobs: Dict[str, schedule.Job] = {}
        self.running = False
        self._thread = None
        
        self.logger.info("Automation Scheduler initialized.")

    def _tick_loop(self):
        """Infinite background loop strictly calculating time deltas."""
        while self.running:
            schedule.run_pending()
            time.sleep(1) # Exact resolution sleep

    def start(self):
        """Spins up the isolated clock thread."""
        if self.running:
            return
            
        self.running = True
        self._thread = threading.Thread(target=self._tick_loop, daemon=True, name="Stuart-Clock")
        self._thread.start()
        self.logger.info("Clock thread active.")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join()
            
    def _fire_job(self, prompt: str):
        self.logger.debug(f"Clock interval hit! Dispatched automation: '{prompt}'")
        self.execute_callback(prompt)

    def add_daily_job(self, time_str: str, prompt: str) -> str:
        """
        Expects a strictly formatted 24hr string like '10:30'
        """
        job_id = f"auto_{str(uuid.uuid4())[:8]}"
        job = schedule.every().day.at(time_str).do(self._fire_job, prompt)
        
        self.jobs[job_id] = job
        self.logger.info(f"Scheduled Daily Job '{job_id}' at {time_str}")
        return job_id

    def add_interval_job(self, minutes: int, prompt: str) -> str:
        """Runs something roughly every X minutes forever."""
        job_id = f"auto_{str(uuid.uuid4())[:8]}"
        job = schedule.every(minutes).minutes.do(self._fire_job, prompt)
        
        self.jobs[job_id] = job
        self.logger.info(f"Scheduled Interval Job '{job_id}' every {minutes}min")
        return job_id

    def list_jobs(self) -> str:
        if not self.jobs:
            return "No scheduled automations."
            
        output = "Active Automations:\n"
        for j_id, j_ref in self.jobs.items():
            output += f"- [{j_id}]: {j_ref}\n"
        return output
        
    def cancel_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job:
            schedule.cancel_job(job)
            del self.jobs[job_id]
            self.logger.info(f"Cancelled job {job_id}")
            return True
        return False
