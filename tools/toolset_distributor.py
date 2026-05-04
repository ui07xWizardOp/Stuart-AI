"""
Toolset Distributor (Phase 9B)

Inspired by Hermes Agent's toolset_distributions.py.

Instead of dumping ALL tool schemas into every LLM prompt (wasting tokens),
this module classifies the task and surfaces only the relevant tools.

Example:
  - A coding prompt gets: [python_executor, file_manager]
  - A research prompt gets: [api_caller]
  - A general prompt gets: all tools (fallback)

This typically saves 30-50% of tool-schema tokens per request.
"""

from typing import Dict, List, Any, Optional
import re

from observability import get_logging_system
from tools.registry import ToolRegistry


# Task type ? list of tool names that are relevant
DEFAULT_DISTRIBUTIONS: Dict[str, List[str]] = {
    "coding": ["python_executor", "file_manager"],
    "file_ops": ["file_manager"],
    "research": ["api_caller"],
    "api": ["api_caller"],
    "general": [],  # Empty means "all tools" ? acts as fallback
}

# Keyword patterns for classification
TASK_PATTERNS: Dict[str, List[str]] = {
    "coding": [
        r"\bcode\b", r"\bscript\b", r"\bpython\b", r"\bfunction\b",
        r"\bclass\b", r"\bdebug\b", r"\bfix\b.*\bbug\b", r"\bprogram\b",
        r"\bimplement\b", r"\balgorithm\b", r"\bcompile\b", r"\bsyntax\b",
        r"\brefactor\b", r"\btest\b.*\bcode\b", r"\bunit test\b",
        r"\bwrite.*code\b", r"\bcreate.*script\b", r"\bexecute.*python\b",
    ],
    "file_ops": [
        r"\bread\b.*\bfile\b", r"\bwrite\b.*\bfile\b", r"\bdelete\b.*\bfile\b",
        r"\bcreate\b.*\bfile\b", r"\bsave\b.*\bfile\b", r"\bopen\b.*\bfile\b",
        r"\bdir\b", r"\bdirectory\b", r"\bfolder\b", r"\bpath\b",
        r"\brename\b", r"\bcopy\b.*\bfile\b", r"\bmove\b.*\bfile\b",
    ],
    "research": [
        r"\bsearch\b", r"\blookup\b", r"\bfind\b.*\bonline\b",
        r"\bresearch\b", r"\bweb\b", r"\bgoogle\b", r"\bfetch\b",
        r"\bretrieve\b", r"\bAPI\b", r"\brequest\b", r"\burl\b",
        r"\bhttp\b", r"\brendpoint\b",
    ],
    "api": [
        r"\bAPI\b", r"\brest\b", r"\bendpoint\b", r"\bhttp\b",
        r"\bget request\b", r"\bpost request\b", r"\bjson\b.*\bapi\b",
    ],
}


class ToolsetDistributor:
    """
    Classifies incoming prompts by task type and returns only
    the tool schemas relevant to that task.
    """

    def __init__(self, registry: ToolRegistry, 
                 distributions: Dict[str, List[str]] = None):
        self.logger = get_logging_system()
        self.registry = registry
        self.distributions = distributions or DEFAULT_DISTRIBUTIONS

        # Pre-compile regex patterns for performance
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        for task_type, patterns in TASK_PATTERNS.items():
            self._compiled_patterns[task_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

        self.logger.info(f"ToolsetDistributor initialized with {len(self.distributions)} task distributions (Phase 9B).")

    def classify_task(self, prompt: str) -> str:
        """
        Classify a user prompt into a task type using keyword matching.
        Returns the task type string (e.g., "coding", "research", "general").
        """
        scores: Dict[str, int] = {}

        for task_type, patterns in self._compiled_patterns.items():
            score = 0
            for pattern in patterns:
                if pattern.search(prompt):
                    score += 1
            if score > 0:
                scores[task_type] = score

        if not scores:
            return "general"

        # Return the task type with the highest score
        best = max(scores, key=scores.get)
        self.logger.debug(f"Task classified as '{best}' (score: {scores[best]}) for prompt: '{prompt[:40]}...'")
        return best

    def get_tools_for_task(self, prompt: str) -> List[Dict[str, Any]]:
        """
        Classify the task and return only the relevant tool schemas.
        Falls back to all tools for "general" tasks.
        """
        task_type = self.classify_task(prompt)
        tool_names = self.distributions.get(task_type, [])

        if not tool_names:
            # Fallback: return all tools
            all_tools = self.registry.get_all_tools()
            schemas = [t.get_metadata() for t in all_tools]
            self.logger.debug(f"Task type '{task_type}' ? returning ALL {len(schemas)} tools.")
            return schemas

        # Filter to only the tools in the distribution
        schemas = []
        for name in tool_names:
            tool = self.registry.get_tool(name)
            if tool:
                schemas.append(tool.get_metadata())
            else:
                self.logger.warning(f"Tool '{name}' in distribution '{task_type}' not found in registry.")

        self.logger.info(f"Task type '{task_type}' ? surfacing {len(schemas)}/{len(self.registry.get_all_tools())} tools (token savings!).")
        return schemas

    def get_distribution_summary(self) -> str:
        """Return a human-readable summary of tool distributions."""
        lines = ["? **Toolset Distributions:**\n"]
        for task_type, tool_names in self.distributions.items():
            if tool_names:
                tools_str = ", ".join(f"`{n}`" for n in tool_names)
            else:
                tools_str = "*(all tools)*"
            lines.append(f"  ? {task_type}: {tools_str}")
        return "\n".join(lines)
