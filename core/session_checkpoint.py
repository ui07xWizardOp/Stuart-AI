"""
Session Checkpointing (Phase 9A ? Hardening Sprint)

Inspired by CheetahClaws' checkpoint/ system.

Serializes the full agent state (conversation history, memory, tool results,
plan progress) to disk after each orchestrator cycle. If the system crashes
mid-task, it can resume from the last checkpoint.

Storage: JSON files in <project_root>/.stuart_checkpoints/
"""

import json
import os
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from observability import get_logging_system


class SessionCheckpoint:
    """
    Persistent session state manager.
    
    Saves agent state to disk after each cycle.
    Loads the most recent checkpoint on startup.
    """

    CHECKPOINT_DIR = ".stuart_checkpoints"
    MAX_CHECKPOINTS = 10  # Keep last N checkpoints, prune older ones

    def __init__(self, base_path: Optional[str] = None):
        self.logger = get_logging_system()
        
        if base_path:
            self.checkpoint_dir = Path(base_path) / self.CHECKPOINT_DIR
        else:
            # Default: project root
            self.checkpoint_dir = Path(__file__).parent.parent / self.CHECKPOINT_DIR
        
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._session_id: Optional[str] = None

    def save(self, state: Dict[str, Any], session_id: Optional[str] = None):
        """
        Save a checkpoint of the current agent state.
        
        Args:
            state: Dictionary containing the serializable agent state.
            session_id: Optional session identifier for grouping checkpoints.
        """
        with self._lock:
            sid = session_id or self._session_id or "default"
            self._session_id = sid

            checkpoint = {
                "version": 1,
                "session_id": sid,
                "timestamp": datetime.utcnow().isoformat(),
                "epoch": time.time(),
                "state": self._make_serializable(state),
            }

            filename = f"checkpoint_{sid}_{int(time.time())}.json"
            filepath = self.checkpoint_dir / filename

            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(checkpoint, f, indent=2, ensure_ascii=False, default=str)
                
                self.logger.info(f"? Checkpoint saved: {filename}")
                self._prune_old_checkpoints(sid)
            except Exception as e:
                self.logger.error(f"? Checkpoint save failed: {e}")

    def load_latest(self, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load the most recent checkpoint for a given session.
        
        Returns None if no checkpoint exists.
        """
        sid = session_id or self._session_id or "default"
        checkpoints = self._list_checkpoints(sid)

        if not checkpoints:
            self.logger.info(f"? No checkpoints found for session '{sid}'")
            return None

        latest = checkpoints[-1]  # Sorted by time, last is newest
        try:
            with open(latest, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            age = time.time() - data.get("epoch", 0)
            self.logger.info(
                f"? Loaded checkpoint: {latest.name} "
                f"(age: {age:.0f}s, session: {sid})"
            )
            return data.get("state", {})
        except Exception as e:
            self.logger.error(f"? Checkpoint load failed: {e}")
            return None

    def has_checkpoint(self, session_id: Optional[str] = None) -> bool:
        """Check if any checkpoint exists for the given session."""
        sid = session_id or self._session_id or "default"
        return len(self._list_checkpoints(sid)) > 0

    def clear(self, session_id: Optional[str] = None):
        """Clear all checkpoints for a session."""
        sid = session_id or self._session_id or "default"
        checkpoints = self._list_checkpoints(sid)
        for cp in checkpoints:
            cp.unlink(missing_ok=True)
        self.logger.info(f"?? Cleared {len(checkpoints)} checkpoints for session '{sid}'")

    def _list_checkpoints(self, session_id: str) -> List[Path]:
        """List checkpoint files for a session, sorted by modification time."""
        pattern = f"checkpoint_{session_id}_*.json"
        files = sorted(self.checkpoint_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
        return files

    def _prune_old_checkpoints(self, session_id: str):
        """Keep only the last N checkpoints per session."""
        checkpoints = self._list_checkpoints(session_id)
        if len(checkpoints) > self.MAX_CHECKPOINTS:
            to_remove = checkpoints[:-self.MAX_CHECKPOINTS]
            for old in to_remove:
                old.unlink(missing_ok=True)
                self.logger.info(f"?? Pruned old checkpoint: {old.name}")

    def _make_serializable(self, obj: Any) -> Any:
        """Recursively convert non-serializable objects to strings."""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            return str(obj)

    def get_status(self) -> dict:
        """Return checkpoint status for health monitoring."""
        sid = self._session_id or "default"
        checkpoints = self._list_checkpoints(sid)
        return {
            "session_id": sid,
            "checkpoint_count": len(checkpoints),
            "latest": checkpoints[-1].name if checkpoints else None,
            "checkpoint_dir": str(self.checkpoint_dir),
        }
