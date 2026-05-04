"""
TELOS Framework (Phase 12: Cognitive Alignment)

TELOS (from Greek 'purpose' or 'end') acts as the constitutional AI layer.
It reads the user's core goals, values, and operating principles from `data/TELOS.md`
and makes them accessible to the Orchestrator for prompt injection.
"""

import os
from typing import Dict, Any

from observability import get_logging_system

DEFAULT_TELOS = """# ? TELOS: Core Purpose & Alignment

## 1. Primary Mission
Assist the user in their software engineering career and personal productivity.
Act as a force multiplier for their capabilities, not a replacement.

## 2. Core Values
- **Privacy First:** Never leak sensitive data. Default to local execution.
- **Accuracy Over Speed:** Take the time to reason thoroughly. Never hallucinate code or facts.
- **Radical Transparency:** Always explain what you are doing and why.

## 3. Operational Guidelines
- Before writing a script, ensure it does not destructively modify system files without explicit permission.
- Keep responses concise but mathematically and methodologically rigorous.
- If a user requests an action that violates these values, firmly but politely refuse and explain the alignment conflict.
"""


class TelosFramework:
    """Manages the user's constitutional alignment document."""
    
    FILE_PATH = os.path.join("data", "TELOS.md")
    
    def __init__(self):
        self.logger = get_logging_system()
        self.current_telos = ""
        self._ensure_file_exists()
        self.load()

    def _ensure_file_exists(self):
        """Creates the default TELOS.md if it doesn't exist."""
        os.makedirs(os.path.dirname(self.FILE_PATH), exist_ok=True)
        if not os.path.exists(self.FILE_PATH):
            try:
                with open(self.FILE_PATH, "w", encoding="utf-8") as f:
                    f.write(DEFAULT_TELOS)
                self.logger.info(f"Created default TELOS alignment at {self.FILE_PATH}")
            except Exception as e:
                self.logger.error(f"Failed to create TELOS.md: {e}")

    def load(self):
        """Loads the TELOS alignment into memory."""
        try:
            with open(self.FILE_PATH, "r", encoding="utf-8") as f:
                self.current_telos = f.read().strip()
            self.logger.info("TELOS Constitutional Alignment loaded successfully.")
        except Exception as e:
            self.logger.error(f"Failed to load TELOS.md: {e}")
            self.current_telos = "No TELOS alignment found."

    def get_alignment_prompt(self) -> str:
        """Returns the prompt string to inject into the LLM system prompt."""
        if not self.current_telos:
            return ""
            
        return (
            "--- CONSTITUTIONAL ALIGNMENT (TELOS) ---\n"
            "You MUST align your reasoning and actions with the following core purpose:\n"
            f"{self.current_telos}\n"
            "----------------------------------------"
        )

    def update_telos(self, new_content: str):
        """Updates the TELOS document."""
        try:
            with open(self.FILE_PATH, "w", encoding="utf-8") as f:
                f.write(new_content)
            self.current_telos = new_content.strip()
            self.logger.info("TELOS Constitutional Alignment updated.")
        except Exception as e:
            self.logger.error(f"Failed to update TELOS.md: {e}")
            raise e
