"""
System Mode Manager (Task 32 / 44)

Manages global operational modes for Stuart-AI, providing governance
over tool usage, LLM routing, and autonomous behavior levels.
"""

from enum import Enum
from typing import Set, Dict, Any, Optional
import threading

from events import get_event_bus, Event, EventType
from observability import get_logging_system
from tools.base import ToolRiskLevel


class SystemMode(str, Enum):
    """
    Global operational modes for Stuart-AI.
    
    - NORMAL: Full functionality, all tools and models available.
    - SAFE_MODE: Restricted autonomy, high-risk tools blocked.
    - DEGRADED: Resource conservation mode (uses cheapest models, low frequency).
    - EMERGENCY: Only core monitoring and security tools active.
    """
    NORMAL = "normal"
    SAFE_MODE = "safe_mode"
    DEGRADED = "degraded"
    EMERGENCY = "emergency"


class SystemModeManager:
    """
    Singleton manager for system-wide operational governance.
    """

    def __init__(self, initial_mode: SystemMode = SystemMode.NORMAL):
        self.logger = get_logging_system()
        self.event_bus = get_event_bus()
        self._current_mode = initial_mode
        self._lock = threading.Lock()  # RISK-01 fix: Thread-safe mode transitions
        
        # Risk levels allowed per mode
        self._mode_permissions: Dict[SystemMode, Set[ToolRiskLevel]] = {
            SystemMode.NORMAL: {ToolRiskLevel.LOW, ToolRiskLevel.MEDIUM, ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL},
            SystemMode.SAFE_MODE: {ToolRiskLevel.LOW, ToolRiskLevel.MEDIUM},
            SystemMode.DEGRADED: {ToolRiskLevel.LOW, ToolRiskLevel.MEDIUM, ToolRiskLevel.HIGH},
            SystemMode.EMERGENCY: {ToolRiskLevel.LOW}
        }

        self.logger.info(f"SystemModeManager initialized in {initial_mode.value} mode")

    @property
    def current_mode(self) -> SystemMode:
        with self._lock:
            return self._current_mode

    def set_mode(self, mode: SystemMode, reason: Optional[str] = None) -> None:
        """
        Transitions the system to a new operational mode.
        Logs the transition and emits a CONFIG_HOT_RELOADED event.
        """
        with self._lock:
            if mode == self._current_mode:
                return

            old_mode = self._current_mode
            self._current_mode = mode
        
        self.logger.warning(
            f"SYSTEM MODE CHANGED: {old_mode.value} -> {mode.value}",
            extra={"reason": reason}
        )
        
        # BUG-11 fix: Use a proper Event object with a valid EventType
        try:
            from uuid import uuid4
            event = Event.create(
                event_type=EventType.CONFIG_HOT_RELOADED,
                source_component="SystemModeManager",
                payload={
                    "change_type": "system_mode",
                    "old_mode": old_mode.value,
                    "new_mode": mode.value,
                    "reason": reason
                },
                trace_id=str(uuid4()),
                correlation_id=str(uuid4()),
            )
            self.event_bus.publish(event)
        except Exception as e:
            self.logger.warning(f"Failed to publish mode change event: {e}")

    def is_tool_allowed(self, risk_level: ToolRiskLevel) -> bool:
        """
        Checks if a tool of a certain risk level is allowed in the current mode.
        """
        with self._lock:
            allowed_levels = self._mode_permissions.get(self._current_mode, set())
            return risk_level in allowed_levels

    def get_routing_override(self) -> Optional[str]:
        """
        Returns a model tier override based on the current mode.
        In DEGRADED mode, we typically want to force FAST_CHEAP.
        """
        with self._lock:
            if self._current_mode == SystemMode.DEGRADED:
                return "fast_cheap"
            return None

    def get_status(self) -> Dict[str, Any]:
        """Return status for health checks and API."""
        with self._lock:
            return {
                "mode": self._current_mode.value,
                "permissions": [r.value for r in self._mode_permissions.get(self._current_mode, set())]
            }
