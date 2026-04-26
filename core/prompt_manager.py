"""
Prompt Manager (Task 10)

Provides a central mechanism for loading, managing, and rendering prompt
templates. Supports basic versioning and dynamic parameter injection.
Integrates with the configuration manager's hot-reload system via event bus.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import time

from observability import get_logging_system
from events import get_event_bus, EventType


class PromptManager:
    """
    Manages prompt templates, supporting versioning and rendering.
    Expects prompts to be stored in an accessible directory (e.g. core/prompts_dir/).
    """

    def __init__(self, prompts_directory: Optional[str] = None):
        self.logger = get_logging_system()
        self.event_bus = get_event_bus()
        
        # Default to a "prompts" directory within "core"
        if prompts_directory:
            self.prompts_dir = Path(prompts_directory)
        else:
            self.prompts_dir = Path(__file__).parent / "prompts_dir"
            
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        
        # Simple cache: (template_name, version) -> struct { last_modified, text }
        self._cache: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("Prompt Manager initialized", extra={"prompts_dir": str(self.prompts_dir)})
        self._subscribe_hot_reload()

    def _subscribe_hot_reload(self) -> None:
        """Subscribe to config hot-reload events to flush the cache."""
        self.event_bus.subscribe(
            EventType.CONFIG_HOT_RELOADED,
            lambda event: self.clear_cache()
        )

    def clear_cache(self) -> None:
        """Clear all cached prompts."""
        self._cache.clear()
        self.logger.debug("Prompt cache cleared")

    def get_prompt_text(self, template_name: str, version: str = "v1") -> str:
        """
        Retrieve raw prompt text from disk or cache.
        Looks for files like '{template_name}_{version}.txt'
        """
        filename = f"{template_name}_{version}.txt"
        filepath = self.prompts_dir / filename
        
        cache_key = f"{template_name}_{version}"
        
        try:
            stat = filepath.stat()
            modified_time = stat.st_mtime
            
            # Use cache if fresh
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                if cached["last_modified"] >= modified_time:
                    return cached["text"]
                    
            # Load from disk
            text = filepath.read_text(encoding="utf-8")
            self._cache[cache_key] = {
                "last_modified": modified_time,
                "text": text
            }
            return text
            
        except FileNotFoundError:
            # Fallback inline defaults if file doesn't exist
            self.logger.warning(
                f"Prompt file {filename} not found in {self.prompts_dir}, using inline fallback if available."
            )
            return self._get_inline_fallback(template_name)
        except Exception as e:
            self.logger.error(f"Error loading prompt {filename}: {e}")
            raise

    def render_prompt(self, template_name: str, version: str = "v1", **kwargs: Any) -> str:
        """
        Render a prompt using Python string format keys.
        Ignores missing keys by just leaving the `{key}` if not using robust templating.
        """
        template_text = self.get_prompt_text(template_name, version)
        
        try:
            # Note: We use .format(**kwargs). If a key is missing, it will raise KeyError.
            # Real implementations might use a safe formatter or Jinja2.
            # We'll handle KeyError to make it slightly robust.
            
            # Using simple string.format()
            return template_text.format(**kwargs)
            
        except KeyError as e:
            missing_key = str(e)
            self.logger.error(f"Missing parameter {missing_key} when rendering {template_name}_{version}")
            raise ValueError(f"Template rendering failed: missing parameter {missing_key}")

    def _get_inline_fallback(self, template_name: str) -> str:
        """Provide emergency fallback templates if files are missing."""
        fallbacks = {
            "intent_classification": (
                "Classify the following user command into one of "
                "these intents: TASK, WORKFLOW, REMEMBER, SEARCH, RUN, STATUS.\n\n"
                "User Command: {command}\n\n"
                "Output ONLY the intent name."
            ),
            "planner": (
                "You are an AI planner. Create a step-by-step plan for the following goal: {goal}.\n"
                "Available tools: {tools}\n"
                "Output as JSON steps."
            )
        }
        
        if template_name in fallbacks:
            return fallbacks[template_name]
        
        raise FileNotFoundError(f"No prompt file or inline fallback found for {template_name}")
