"""
Circuit Breaker Pattern (Phase 9A ? Hardening Sprint)

Inspired by CheetahClaws / Netflix Hystrix.
Wraps LLM provider calls with fault-tolerance states:
  CLOSED (healthy) ? OPEN (tripped, fast-fail) ? HALF_OPEN (testing recovery)

Prevents cascade failures when Ollama goes offline or Cloud API rate-limits.
"""

import time
import threading
from enum import Enum
from typing import Callable, Any, Optional
from observability import get_logging_system


class CircuitState(str, Enum):
    CLOSED = "closed"       # Healthy ? requests flow through
    OPEN = "open"           # Tripped ? fast-fail all requests
    HALF_OPEN = "half_open" # Testing ? allow one probe request


class CircuitBreaker:
    """
    Thread-safe circuit breaker for LLM provider calls.
    
    Usage:
        breaker = CircuitBreaker(name="ollama", failure_threshold=3, recovery_timeout=30)
        result = breaker.call(lambda: ollama_client.generate(...))
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()
        self.logger = get_logging_system()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if self._last_failure_time and (time.time() - self._last_failure_time) >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self.logger.info(f"? CircuitBreaker[{self.name}]: OPEN ? HALF_OPEN (recovery window)")
            return self._state

    def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Execute `func` through the circuit breaker.
        Raises CircuitOpenError if the circuit is tripped.
        """
        current_state = self.state  # triggers timeout check

        if current_state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"CircuitBreaker[{self.name}] is OPEN. "
                f"Provider offline ? {self.failure_threshold} consecutive failures. "
                f"Will retry in {self._time_until_recovery():.0f}s."
            )

        if current_state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(
                        f"CircuitBreaker[{self.name}] is HALF_OPEN ? probe already in-flight."
                    )
                self._half_open_calls += 1

        # Execute the call
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        """Record a successful call ? reset the breaker."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self.logger.info(f"? CircuitBreaker[{self.name}]: HALF_OPEN ? CLOSED (provider recovered)")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None

    def _on_failure(self, error: Exception):
        """Record a failed call ? potentially trip the breaker."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Probe failed ? back to OPEN
                self._state = CircuitState.OPEN
                self.logger.warning(
                    f"? CircuitBreaker[{self.name}]: HALF_OPEN ? OPEN "
                    f"(probe failed: {error})"
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self.logger.error(
                    f"? CircuitBreaker[{self.name}]: CLOSED ? OPEN "
                    f"({self._failure_count} consecutive failures). "
                    f"Provider quarantined for {self.recovery_timeout}s."
                )

    def _time_until_recovery(self) -> float:
        if self._last_failure_time is None:
            return 0.0
        elapsed = time.time() - self._last_failure_time
        return max(0.0, self.recovery_timeout - elapsed)

    def force_reset(self):
        """Manual reset ? for operator override."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self.logger.info(f"? CircuitBreaker[{self.name}]: Force reset to CLOSED")

    def get_status(self) -> dict:
        """Return breaker status for health monitoring / API exposure."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "seconds_until_retry": round(self._time_until_recovery(), 1),
        }


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is in OPEN state."""
    pass
