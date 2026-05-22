"""
Periodic Health Checks (Feature #60)

A background health monitor that periodically evaluates critical subsystems
(Router, Compactor, Checkpoint, Cron, File Guard) and system resources,
publishing HEALTH_CHECK_FAILED events on failure.
"""

import os
import shutil
import time
import uuid
import threading
from typing import Dict, Any, Optional

from observability import get_logging_system
from events.event_bus import EventBus
from events.event_types import Event, EventType, EventSeverity
from core.config import settings

class StuartHealthMonitor:
    def __init__(self, event_bus: EventBus, orchestrator, cron_manager=None, file_access_guard=None, check_interval: int = 300):
        self.logger = get_logging_system()
        self.event_bus = event_bus
        self.orchestrator = orchestrator
        self.cron_manager = cron_manager
        self.file_access_guard = file_access_guard
        self.check_interval = check_interval
        self.running = False
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        """Starts the periodic health check loop in a daemon background thread."""
        with self._lock:
            if self.running:
                return
            self.running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="Stuart-HealthMonitor")
            self._thread.start()
            self.logger.info("StuartHealthMonitor background thread started.")

    def stop(self):
        """Stops the health monitor loop."""
        with self._lock:
            self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self.logger.info("StuartHealthMonitor background thread stopped.")

    def _run_loop(self):
        # Initial wait to let boot sequence settle
        time.sleep(5)
        while True:
            with self._lock:
                if not self.running:
                    break
            
            try:
                self.perform_checks()
            except Exception as e:
                self.logger.error(f"Error in health monitor perform_checks: {e}")

            # Sleep in small steps to react quickly to shutdown signals
            for _ in range(self.check_interval):
                with self._lock:
                    if not self.running:
                        break
                time.sleep(1)

    def perform_checks(self):
        """Runs checks on system resources and subsystem availability/health."""
        self.logger.debug("StuartHealthMonitor running health checks...")
        
        # 1. System Resources Checks
        # A. Disk Usage
        try:
            total, used, free = shutil.disk_usage(os.getcwd())
            percent_free = (free / total) * 100.0
            if percent_free < 10.0:
                self._publish_failure(
                    message=f"Low disk space warning: Only {percent_free:.1f}% free ({free // (1024**3)} GB left).",
                    metrics={"percent_free": percent_free, "free_bytes": free, "total_bytes": total},
                    severity=EventSeverity.PRIORITY
                )
        except Exception as e:
            self.logger.error(f"Failed to check disk usage: {e}")

        # B. Memory Usage
        try:
            import psutil
            memory = psutil.virtual_memory()
            if memory.percent > 90.0:
                self._publish_failure(
                    message=f"High memory usage warning: Memory usage is at {memory.percent:.1f}%.",
                    metrics={"memory_percent": memory.percent, "memory_used": memory.used},
                    severity=EventSeverity.PRIORITY
                )
        except ImportError:
            # psutil not available, skip memory check gracefully
            pass
        except Exception as e:
            self.logger.error(f"Failed to check memory usage: {e}")

        # 2. Subsystem Health Checks
        # A. Router Health
        if not self.orchestrator or not hasattr(self.orchestrator, "router") or not self.orchestrator.router:
            self._publish_failure(
                message="Subsystem Error: ModelRouter is unavailable.",
                metrics={"subsystem": "router", "status": "unavailable"},
                severity=EventSeverity.FLASH
            )
        else:
            try:
                router_status = self.orchestrator.router.get_status()
                # Check if Ollama circuit is tripped (open)
                if router_status.get("ollama", {}).get("state") == "open":
                    self._publish_failure(
                        message="Router Alert: Ollama circuit breaker is OPEN (tripped).",
                        metrics={"subsystem": "router", "detail": router_status},
                        severity=EventSeverity.FLASH
                    )
                # Check if Cloud API circuit is tripped (open)
                if router_status.get("cloud", {}).get("state") == "open":
                    self._publish_failure(
                        message="Router Alert: Cloud API circuit breaker is OPEN (tripped).",
                        metrics={"subsystem": "router", "detail": router_status},
                        severity=EventSeverity.FLASH
                    )
            except Exception as e:
                self._publish_failure(
                    message=f"Subsystem Error: Failed to check ModelRouter status: {e}",
                    metrics={"subsystem": "router", "error": str(e)},
                    severity=EventSeverity.FLASH
                )

        # B. Compactor Health
        if not self.orchestrator or not hasattr(self.orchestrator, "compactor") or not self.orchestrator.compactor:
            self._publish_failure(
                message="Subsystem Error: ContextCompactor is unavailable.",
                metrics={"subsystem": "compactor", "status": "unavailable"},
                severity=EventSeverity.FLASH
            )
        else:
            try:
                compactor_status = self.orchestrator.compactor.get_status()
            except Exception as e:
                self._publish_failure(
                    message=f"Subsystem Error: Failed to check ContextCompactor status: {e}",
                    metrics={"subsystem": "compactor", "error": str(e)},
                    severity=EventSeverity.FLASH
                )

        # C. Checkpoint Health
        if not self.orchestrator or not hasattr(self.orchestrator, "checkpoint") or not self.orchestrator.checkpoint:
            self._publish_failure(
                message="Subsystem Error: SessionCheckpoint is unavailable.",
                metrics={"subsystem": "checkpoint", "status": "unavailable"},
                severity=EventSeverity.FLASH
            )
        else:
            try:
                checkpoint_status = self.orchestrator.checkpoint.get_status()
            except Exception as e:
                self._publish_failure(
                    message=f"Subsystem Error: Failed to check SessionCheckpoint status: {e}",
                    metrics={"subsystem": "checkpoint", "error": str(e)},
                    severity=EventSeverity.FLASH
                )

        # D. Cron Manager Health
        if not self.cron_manager:
            self._publish_failure(
                message="Subsystem Error: CronManager is unavailable.",
                metrics={"subsystem": "cron", "status": "unavailable"},
                severity=EventSeverity.FLASH
            )
        else:
            try:
                cron_status = self.cron_manager.get_status()
                if not cron_status.get("scheduler_running", False):
                    self._publish_failure(
                        message="Cron Alert: AutomationScheduler clock thread is not running.",
                        metrics={"subsystem": "cron", "detail": cron_status},
                        severity=EventSeverity.FLASH
                    )
            except Exception as e:
                self._publish_failure(
                    message=f"Subsystem Error: Failed to check CronManager status: {e}",
                    metrics={"subsystem": "cron", "error": str(e)},
                    severity=EventSeverity.FLASH
                )

        # E. File Access Guard Health
        if not self.file_access_guard:
            self._publish_failure(
                message="Subsystem Error: FileAccessGuard is unavailable.",
                metrics={"subsystem": "file_guard", "status": "unavailable"},
                severity=EventSeverity.FLASH
            )
        else:
            try:
                guard_status = self.file_access_guard.get_status()
            except Exception as e:
                self._publish_failure(
                    message=f"Subsystem Error: Failed to check FileAccessGuard status: {e}",
                    metrics={"subsystem": "file_guard", "error": str(e)},
                    severity=EventSeverity.FLASH
                )

    def _publish_failure(self, message: str, metrics: Dict[str, Any], severity: EventSeverity):
        """Helper to construct and publish a HEALTH_CHECK_FAILED event."""
        self.logger.warning(f"Health Monitor Alert [{severity.value}]: {message}")
        try:
            event = Event.create(
                event_type=EventType.HEALTH_CHECK_FAILED,
                source_component="health_monitor",
                payload={
                    "message": message,
                    "metrics": metrics
                },
                trace_id=f"health-{uuid.uuid4().hex[:8]}",
                correlation_id=f"health-{uuid.uuid4().hex[:8]}",
                severity=severity
            )
            self.event_bus.publish(event)
        except Exception as e:
            self.logger.error(f"Failed to publish health check failure event: {e}")
