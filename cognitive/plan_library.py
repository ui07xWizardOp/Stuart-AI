"""
Plan Library Engine (Phase 9B — Persistent)

Learns successful behavior. When the Agent completes a ReAct loop flawlessly
(no tool errors, straight to FINAL_ANSWER), it saves the sequence of executed tools
both to Long-Term memory AND to disk for cross-session persistence.

Phase 9B additions:
  - Disk persistence: plans survive restarts via data/plans/*.json
  - list_all_plans(): for the /plan slash command
  - load_all_from_disk(): bootstrap restoration
"""

from typing import List, Dict, Any, Optional
import hashlib
import json
import os
from datetime import datetime

from observability import get_logging_system
import logging
from memory.memory_system import MemorySystem


class PlanLibrary:
    
    PLANS_DIR = os.path.join("data", "plans")

    def __init__(self, memory_system: MemorySystem):

        try:
            self.logger = get_logging_system()
        except Exception:
            self.logger = logging.getLogger(__name__)
        self.memory = memory_system
        
        # In-memory cache for fast lookups
        self._disk_cache: Dict[str, Dict[str, Any]] = {}
        
        # Ensure plans directory exists
        os.makedirs(self.PLANS_DIR, exist_ok=True)
        
        # Load persisted plans at init
        self.load_all_from_disk()

    def _hash_intent(self, user_prompt: str) -> str:
        """Creates a stable hash of the user's intent. In a more advanced build, this would use semantic vectors."""
        # Clean the string heavily so variations in whitespace don't break the hash
        cleaned = "".join(user_prompt.lower().split())
        return hashlib.md5(cleaned.encode()).hexdigest()

    def record_successful_plan(self, user_prompt: str, tool_sequence: List[Dict[str, Any]]):
        """
        Saves a flawless tool sequence to Long-Term Memory AND to disk.
        Expected tool_sequence format: [{"tool": "api_caller", "action": "get", ...}, ...]
        """
        if not tool_sequence:
            return # Trivial conversation, no plan to record.
            
        intent_hash = self._hash_intent(user_prompt)
        
        # Save to memory system
        self.memory.remember_fact(
            category="proven_plans",
            key=f"plan_{intent_hash}",
            facts={
                "original_prompt": user_prompt,
                "sequence": json.dumps(tool_sequence)
            }
        )
        
        # Phase 9B: Also persist to disk
        plan_data = {
            "intent_hash": intent_hash,
            "original_prompt": user_prompt,
            "tool_sequence": tool_sequence,
            "created_at": datetime.now().isoformat(),
            "execution_count": 1,
        }
        
        # Check if plan already exists on disk
        file_path = os.path.join(self.PLANS_DIR, f"{intent_hash}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    existing = json.load(f)
                plan_data["execution_count"] = existing.get("execution_count", 0) + 1
            except Exception:
                pass
        
        try:
            with open(file_path, "w") as f:
                json.dump(plan_data, f, indent=2)
            self._disk_cache[intent_hash] = plan_data
        except Exception as e:
            self.logger.warning(f"Failed to persist plan to disk: {e}")
            
        self.logger.info(f"Learned and cached Proven Plan for intent: '{user_prompt[:30]}...'")

    def lookup_plan(self, user_prompt: str) -> Optional[str]:
        """
        Retrieves a known plan if the user asks exactly the same question again.
        Checks memory first, then disk cache.
        Returns a formatted markdown string of the sequence to inject into the LLM prompt.
        """
        intent_hash = self._hash_intent(user_prompt)
        
        # Try memory system first
        res = self.memory.extract_context("proven_plans", exact_key=f"plan_{intent_hash}")
        if res:
            try:
                facts = res[0]
                seq_str = facts.get("sequence", "[]")
                sequence = json.loads(seq_str)
                return self._format_plan(sequence)
            except Exception as e:
                self.logger.error(f"Failed to parse proven plan from memory: {e}")
        
        # Phase 9B: Fallback to disk cache
        cached = self._disk_cache.get(intent_hash)
        if cached:
            try:
                sequence = cached.get("tool_sequence", [])
                return self._format_plan(sequence)
            except Exception as e:
                self.logger.error(f"Failed to parse plan from disk cache: {e}")
        
        return None

    def list_all_plans(self) -> List[Dict[str, Any]]:
        """
        Phase 9B: List all cached plans (for /plan slash command).
        Returns a list of dicts with intent_hash, prompt, execution_count.
        """
        plans = []
        for intent_hash, data in self._disk_cache.items():
            plans.append({
                "intent_hash": intent_hash,
                "prompt": data.get("original_prompt", "Unknown"),
                "execution_count": data.get("execution_count", 0),
                "created_at": data.get("created_at", "Unknown"),
            })
        return plans

    def load_all_from_disk(self):
        """
        Phase 9B: Load all persisted plans from disk into memory cache.
        Called once during bootstrap.
        """
        if not os.path.exists(self.PLANS_DIR):
            return

        loaded = 0
        try:
            for filename in os.listdir(self.PLANS_DIR):
                if not filename.endswith(".json"):
                    continue
                filepath = os.path.join(self.PLANS_DIR, filename)
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                    intent_hash = data.get("intent_hash", filename.replace(".json", ""))
                    self._disk_cache[intent_hash] = data
                    loaded += 1
                except Exception as e:
                    self.logger.warning(f"Failed to load plan file {filename}: {e}")
        except Exception as e:
            self.logger.error(f"Failed to scan plans directory: {e}")

        if loaded > 0:
            self.logger.info(f"Restored {loaded} proven plans from disk.")

    def _format_plan(self, sequence: List[Dict[str, Any]]) -> str:
        """Format a tool sequence into an injection-ready string."""
        plan_text = "I have a proven plan from past experience to solve this exact intent. Try executing these tools in order:\n"
        for step, tool_cfg in enumerate(sequence):
            plan_text += f"{step+1}. {tool_cfg.get('tool')}.{tool_cfg.get('action')}\n"
        return plan_text
