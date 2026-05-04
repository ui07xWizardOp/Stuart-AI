"""
Task Queue System (Task 22)

An asynchronous execution pool designed to handle long-running agent workflows silently.
Protects the main chat loop from freezing during 5-minute RAG indexing or web scraping.
"""

from typing import Callable, Any, Dict
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor

from observability import get_logging_system
import logging

class TaskQueue:
    
    def __init__(self, orchestrator_factory: Callable[[], Any], max_workers: int = 2):
        
        try:
            self.logger = get_logging_system()
        except Exception:
            self.logger = logging.getLogger(__name__)
        # Pass a factory so children threads can instantiate fresh un-corrupted ReAct loops
        self.orchestrator_factory = orchestrator_factory
        
        # Hardcap concurrent workers to prevent API budget explosion
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="Stuart-Worker")
        self.jobs: Dict[str, str] = {} # Tracks job status
        
        self.logger.info(f"Task Queue initialized natively with {max_workers} thread slots.")

    def _worker_wrapper(self, job_id: str, prompt: str):
        self.jobs[job_id] = "RUNNING"
        self.logger.info(f"Worker {job_id} picked up task: '{prompt[:30]}...'")
        
        try:
            # Boot a fresh agent instance for this thread
            thread_agent = self.orchestrator_factory()
            
            # Start the ReAct reasoning loop
            result = thread_agent.process_user_message(prompt)
            
            self.jobs[job_id] = "COMPLETED"
            self.logger.info(f"Worker {job_id} natively completed. Result saved to Long Term Memory.")
            
        except Exception as e:
            self.jobs[job_id] = f"FAILED: {str(e)}"
            self.logger.error(f"Worker {job_id} crashed entirely: {str(e)}")

    def push_background_task(self, prompt: str) -> str:
        """
        Pushes a natural language command into the background thread pool.
        """
        job_id = str(uuid.uuid4())[:8]
        self.jobs[job_id] = "QUEUED"
        
        # Fire and forget natively
        self.executor.submit(self._worker_wrapper, job_id, prompt)
        
        self.logger.debug(f"Submitted background task {job_id}")
        return job_id

    def check_status(self, job_id: str) -> str:
        return self.jobs.get(job_id, "UNKNOWN JOB ID")

    def shutdown(self):
        self.executor.shutdown(wait=False)
        self.logger.info("Task Queue shutdown.")
