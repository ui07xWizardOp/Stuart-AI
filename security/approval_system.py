"""
Dynamic Human-In-The-Loop (Task 30)

Interception layer binding overall agent autonomy logic to specific tool risk levels.
Provides CLI prompt rendering and thread-safe fallback mechanics.
"""

from enum import Enum
import threading
from typing import Callable, Dict, Optional

from tools.base import ToolRiskLevel
from observability import get_logging_system

class AutonomyLevel(str, Enum):
    """Defines the agent's degree of independent action.

    Tiers:
        RESTRICTED: Requires explicit human approval for every tool execution.
        MODERATE: Auto-allows LOW/MEDIUM risk tools; prompts for HIGH/CRITICAL.
        FULL: Operates with total trust; no human approval required for any tool.
    """
    RESTRICTED = "restricted"
    MODERATE = "moderate"
    FULL = "full"

# Risk tier ordering for comparison
_RISK_ORDER = {
    ToolRiskLevel.LOW: 0,
    ToolRiskLevel.MEDIUM: 1,
    ToolRiskLevel.HIGH: 2,
    ToolRiskLevel.CRITICAL: 3,
}


class ApprovalSystem:
    """Interception layer determining human-in-the-loop (HIL) requirements.

    Binds the agent's autonomy configuration to the specific risk levels of tools.
    Provides thread-safe signaling for background agent pausing.

    Attributes:
        autonomy_level (AutonomyLevel): The global operational mode.
        _thresholds (Dict[str, str]): Granular overrides per risk tier ('auto', 'prompt', 'block').
    """
    
    def __init__(self, autonomy_level: AutonomyLevel = AutonomyLevel.MODERATE):
        self.logger = get_logging_system()
        self.autonomy_level = autonomy_level
        self._main_thread_id = threading.main_thread().ident
        self.logger.info(f"HIL Approval System booted at {autonomy_level.upper()} autonomy.")
        
        # Per-tier thresholds: 'auto'|'prompt'|'block'
        # These override autonomy-level defaults when set from the GUI panel.
        self._thresholds: Dict[str, str] = {
            ToolRiskLevel.LOW.value:      "auto",
            ToolRiskLevel.MEDIUM.value:   "auto",
            ToolRiskLevel.HIGH.value:     "prompt",
            ToolRiskLevel.CRITICAL.value: "prompt",
        }
        # GUI queue helper (injected after API boot)
        self._gui_queue_fn: Optional[Callable] = None
        self._gui_wait_fn: Optional[Callable] = None

    def set_thresholds(self, thresholds: Dict[str, str]):
        """Called from the FastAPI HIL endpoint to push GUI panel state."""
        for k, v in thresholds.items():
            normalized_key = k.upper()
            if v in ("auto", "prompt", "block"):
                self._thresholds[normalized_key] = v
        self.logger.info(f"HIL thresholds updated: {self._thresholds}")

    def set_gui_queue_hooks(self, queue_fn: Callable, wait_fn: Callable):
        """Inject the GUI queue functions from api.agent_api."""
        self._gui_queue_fn = queue_fn
        self._gui_wait_fn = wait_fn

    def set_autonomy(self, level: AutonomyLevel):
        self.autonomy_level = level
        self.logger.warning(f"Agent Autonomy shifted to: {level.upper()}")

    def _tier_action(self, risk_level: ToolRiskLevel) -> str:
        """Return the configured action ('auto'|'prompt'|'block') for this risk tier."""
        return self._thresholds.get(risk_level.value.upper(), "prompt")

    def _requires_approval(self, risk_level: ToolRiskLevel) -> bool:
        if self.autonomy_level == AutonomyLevel.FULL:
            return False
            
        if self.autonomy_level == AutonomyLevel.RESTRICTED:
            return True
        
        # Check per-tier threshold
        action = self._tier_action(risk_level)
        if action == "auto":
            return False
        if action == "block":
            return True  # will be rejected immediately
            
        # MODERATE default logic (prompt for HIGH/CRITICAL)
        if risk_level in [ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL]:
            return True
            
        return False

    def eval_risk(self, tool_name: str, action: str, risk_level: ToolRiskLevel) -> bool:
        """
        Evaluates the tool call. Returns True if authorized, raises Exception if denied.
        """
        # Hard-block tier
        tier_action = self._tier_action(risk_level)
        if tier_action == "block" and self.autonomy_level != AutonomyLevel.FULL:
            self.logger.warning(f"HIL Blocked (tier-block): {tool_name}.{action} [{risk_level}]")
            raise PermissionError(f"HIL Blocked: {risk_level} risk tier is set to BLOCK for {tool_name}.")

        if not self._requires_approval(risk_level):
            self.logger.info(f"Auto-approved: {tool_name}.{action} [{risk_level}]")
            return True

        # Try routing to GUI queue first
        if self._gui_queue_fn and self._gui_wait_fn:
            is_background = threading.current_thread().ident != self._main_thread_id
            if is_background:
                self.logger.warning(f"HIL queuing GUI approval for background thread: {tool_name}.{action}")
            request_id = self._gui_queue_fn(tool_name, action, risk_level.value.upper())
            self.logger.info(f"HIL awaiting GUI approval [{request_id}]: {tool_name}.{action}")
            approved = self._gui_wait_fn(request_id, timeout_secs=60)
            if approved:
                self.logger.info(f"GUI approved {tool_name}.{action} [{request_id}]")
                return True
            else:
                self.logger.warning(f"GUI denied {tool_name}.{action} [{request_id}]")
                raise PermissionError(f"HIL Blocked: GUI panel denied {tool_name}.{action}.")
            
        # Check if we are running in a background cron/task_queue worker thread
        is_background = threading.current_thread().ident != self._main_thread_id
        
        if is_background:
            self.logger.warning(f"Job {tool_name}.{action} requires approval but is running in a detached Background Thread. Auto-denying to prevent deadlock.")
            raise PermissionError(f"HIL Blocked: Background thread attempted a {risk_level.upper()} risk execution.")

        # We are in the main CLI thread. Prompt the user directly.
        prompt_txt = f"\n\n[HIL APPROVAL REQUIRED] The Agent is attempting to execute:\n" \
                     f"  Tool: {tool_name}\n" \
                     f"  Action: {action}\n" \
                     f"  Risk: {risk_level.upper()}\n" \
                     f"Allow execution? (y/n): "
                     
        try:
            choice = input(prompt_txt).strip().lower()
            if choice == 'y':
                self.logger.info(f"User visually approved {tool_name} execution.")
                return True
            else:
                self.logger.warning(f"User visually rejected {tool_name} execution.")
                raise PermissionError(f"HIL Blocked: User explicitly rejected the execution of {tool_name}.{action}.")
        except EOFError: # Catch headless aborts
            raise PermissionError("HIL Blocked: EOF received during input approval.")
