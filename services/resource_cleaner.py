"""
Resource Cleaner (Phase 11 ? Production Hardening)

Automated background service to clean up stale files, orphaned sessions,
and temporary sandbox artifacts to maintain system performance and security.
"""

import os
import time
import shutil
from pathlib import Path
from typing import List, Optional

from observability import get_logging_system


class ResourceCleaner:
    """
    Cleans up orphaned resources across the system.
    """

    def __init__(
        self,
        checkpoint_dir: str = ".stuart_checkpoints",
        sandbox_dir: str = "Stuart-AI/data/sandbox/",
        max_age_days: int = 7
    ):
        self.logger = get_logging_system()
        self.checkpoint_dir = Path(checkpoint_dir)
        self.sandbox_dir = Path(sandbox_dir)
        self.max_age_seconds = max_age_days * 24 * 60 * 60

    def run_cleanup(self):
        """Executes a full cleanup cycle."""
        self.logger.info("? Starting automated resource cleanup cycle...")
        
        self._clean_checkpoints()
        self._clean_sandbox()
        
        self.logger.info("? Resource cleanup cycle complete.")

    def _clean_checkpoints(self):
        """Removes checkpoints older than max_age."""
        if not self.checkpoint_dir.exists():
            return

        count = 0
        now = time.time()
        for item in self.checkpoint_dir.glob("*.json"):
            if item.is_file():
                age = now - item.stat().st_mtime
                if age > self.max_age_seconds:
                    try:
                        item.unlink()
                        count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to delete stale checkpoint {item}: {e}")
        
        if count > 0:
            self.logger.info(f"?? Deleted {count} stale checkpoints.")

    def _clean_sandbox(self):
        """Cleans temporary files from the sandbox."""
        if not self.sandbox_dir.exists():
            return

        count = 0
        now = time.time()
        # We delete everything in the sandbox that isn't a permanent directory/file
        # or anything older than 24 hours (sandbox should be ephemeral)
        sandbox_age_seconds = 24 * 60 * 60 

        for item in self.sandbox_dir.iterdir():
            # Skip hidden files or structural files
            if item.name.startswith(".") or item.name == "__init__.py":
                continue
                
            age = now - item.stat().st_mtime
            if age > sandbox_age_seconds:
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to delete sandbox item {item}: {e}")

        if count > 0:
            self.logger.info(f"?? Cleared {count} temporary items from sandbox.")

if __name__ == "__main__":
    # Manual run
    cleaner = ResourceCleaner()
    cleaner.run_cleanup()
