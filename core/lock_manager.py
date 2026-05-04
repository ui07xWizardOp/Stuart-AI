"""
Distributed Lock Manager (Phase 11 ? Production Hardening)

Prevents race conditions when multiple agent instances or tools access
shared resources (e.g. the same file, database row, or external API).
"""

import os
import time
import threading
from typing import Optional
from pathlib import Path

# Platform-specific locking
if os.name == 'nt':
    import msvcrt
else:
    import fcntl

from observability import get_logging_system


class LockManager:
    """
    Manages resource locks to ensure exclusive access.
    Implements platform-aware file-based locking.
    """

    def __init__(self, lock_dir: str = ".stuart_locks"):
        self.logger = get_logging_system()
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._local_locks: dict = {}
        self._local_lock_mutex = threading.Lock()

    def acquire(self, resource_id: str, timeout: float = 10.0) -> bool:
        """
        Acquire an exclusive lock on a resource.
        """
        lock_file = self.lock_dir / f"{resource_id}.lock"
        start_time = time.time()

        while time.time() - start_time < timeout:
            f = None
            try:
                # Open/create the lock file
                f = open(lock_file, 'w')
                
                # Attempt to get an exclusive lock (non-blocking)
                if os.name == 'nt':
                    # Windows: Lock first byte
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    # Unix
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                with self._local_lock_mutex:
                    self._local_locks[resource_id] = f
                
                self.logger.debug(f"? Lock acquired: {resource_id}")
                return True
            except (IOError, BlockingIOError, PermissionError):
                # BUG-05 fix: Close the file handle on failed lock attempts
                if f is not None:
                    try:
                        f.close()
                    except Exception:
                        pass
                time.sleep(0.1)
                continue
        
        self.logger.warning(f"? Timeout acquiring lock for {resource_id}")
        return False

    def release(self, resource_id: str):
        """
        Release a previously acquired lock.
        """
        with self._local_lock_mutex:
            f = self._local_locks.pop(resource_id, None)
            if f:
                try:
                    if os.name == 'nt':
                        f.seek(0)
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(f, fcntl.LOCK_UN)
                    f.close()
                except Exception as e:
                    self.logger.error(f"Failed to release lock {resource_id}: {e}")
                
                self.logger.debug(f"? Lock released: {resource_id}")

    def is_locked(self, resource_id: str) -> bool:
        """Check if a resource is currently locked."""
        lock_file = self.lock_dir / f"{resource_id}.lock"
        if not lock_file.exists():
            return False
            
        f = None
        try:
            f = open(lock_file, 'r+')
            if os.name == 'nt':
                # BUG-06 fix: Actually probe the lock on Windows
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                # If we got here, lock succeeded ? resource is NOT locked
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f, fcntl.LOCK_UN)
            f.close()
            return False
        except (IOError, BlockingIOError, PermissionError):
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass
            return True
