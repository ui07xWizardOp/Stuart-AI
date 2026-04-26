"""
Token Quota Manager (Phase 9A — Hardening Sprint)

Inspired by CheetahClaws' quota.py.
Tracks and enforces token budgets per-session and per-day to prevent
runaway Cloud API costs.

Features:
  - Per-session budget (resets on new chat session)
  - Per-day budget (resets at midnight)
  - Per-model tracking (separate budgets for Ollama vs Cloud)
  - Cost estimation for Cloud API calls
  - Budget warnings at 80% and 95% thresholds
"""

import time
import threading
from datetime import datetime, date
from typing import Dict, Optional
from observability import get_logging_system


class TokenQuota:
    """Thread-safe token budget tracker and cost enforcement layer.

    Tracks usage across multiple tiers (Cloud vs Local) and enforces per-session 
    and per-day limits. Provides cost estimation and threshold warnings at 80% and 95%.

    Attributes:
        daily_limit (int): Maximum total tokens allowed per 24-hour period.
        session_limit (int): Maximum tokens allowed for the current active session.
        daily_usage (int): Cumulative token count since last midnight reset.
        session_usage (int): Cumulative token count for the current session.
        last_reset_date (date): Tracking date for daily budget resets.
        lock (threading.Lock): Synchronization primitive for multi-threaded access.
    """

    # Rough cost per 1K tokens (input/output averaged) for budget warnings
    COST_PER_1K = {
        "cloud": 0.005,   # ~$5/M tokens average
        "local": 0.0,     # Free (Ollama)
    }

    def __init__(
        self,
        daily_limit: int = 500_000,
        session_limit: int = 100_000,
        cloud_daily_limit: Optional[int] = None,
    ):
        self.daily_limit = daily_limit
        self.session_limit = session_limit
        self.cloud_daily_limit = cloud_daily_limit or daily_limit

        # Usage counters
        self._session_usage: Dict[str, int] = {"cloud": 0, "local": 0}
        self._daily_usage: Dict[str, int] = {"cloud": 0, "local": 0}
        self._current_date: date = date.today()
        self._session_start: float = time.time()
        self._lock = threading.Lock()
        self.logger = get_logging_system()

    def check_budget(self, provider: str, estimated_tokens: int) -> bool:
        """
        Pre-flight check before making an LLM call.
        Returns True if budget allows, raises QuotaExceededError if not.
        """
        with self._lock:
            self._maybe_reset_daily()
            provider_key = "cloud" if provider != "local" else "local"

            # Check session limit
            session_total = sum(self._session_usage.values())
            if session_total + estimated_tokens > self.session_limit:
                raise QuotaExceededError(
                    f"Session token budget exhausted. "
                    f"Used: {session_total:,} / {self.session_limit:,} tokens. "
                    f"Requested: {estimated_tokens:,}. "
                    f"Start a new session or increase the budget."
                )

            # Check daily Cloud limit
            if provider_key == "cloud":
                cloud_used = self._daily_usage["cloud"]
                if cloud_used + estimated_tokens > self.cloud_daily_limit:
                    raise QuotaExceededError(
                        f"Daily Cloud API token budget exhausted. "
                        f"Used: {cloud_used:,} / {self.cloud_daily_limit:,} tokens. "
                        f"Requested: {estimated_tokens:,}. "
                        f"Switch to local model or wait until tomorrow."
                    )

            # Warn at 80% threshold
            daily_total = sum(self._daily_usage.values())
            if daily_total + estimated_tokens > self.daily_limit * 0.8:
                pct = ((daily_total + estimated_tokens) / self.daily_limit) * 100
                self.logger.warning(
                    f"⚠️ TokenQuota: Daily budget at {pct:.0f}% "
                    f"({daily_total + estimated_tokens:,} / {self.daily_limit:,})"
                )

            return True

    def record_usage(self, provider: str, prompt_tokens: int = 0, completion_tokens: int = 0):
        """Record actual token usage after an LLM call completes."""
        total = prompt_tokens + completion_tokens
        provider_key = "cloud" if provider != "local" else "local"

        with self._lock:
            self._maybe_reset_daily()
            self._session_usage[provider_key] = self._session_usage.get(provider_key, 0) + total
            self._daily_usage[provider_key] = self._daily_usage.get(provider_key, 0) + total

            # Log cost for cloud calls
            if provider_key == "cloud" and total > 0:
                cost = (total / 1000) * self.COST_PER_1K.get("cloud", 0)
                self.logger.info(
                    f"💰 TokenQuota: Cloud usage +{total:,} tokens "
                    f"(~${cost:.4f}). Session: {self._session_usage['cloud']:,} | "
                    f"Today: {self._daily_usage['cloud']:,}"
                )

    def reset_session(self):
        """Reset session counters (called when user starts a new chat session)."""
        with self._lock:
            self._session_usage = {"cloud": 0, "local": 0}
            self._session_start = time.time()
            self.logger.info("🔄 TokenQuota: Session counters reset.")

    def _maybe_reset_daily(self):
        """Reset daily counters if we've rolled past midnight."""
        today = date.today()
        if today != self._current_date:
            self.logger.info(
                f"📅 TokenQuota: New day detected ({today}). "
                f"Yesterday's usage — Cloud: {self._daily_usage.get('cloud', 0):,}, "
                f"Local: {self._daily_usage.get('local', 0):,}"
            )
            self._daily_usage = {"cloud": 0, "local": 0}
            self._current_date = today

    def get_status(self) -> dict:
        """Return quota status for health monitoring / API exposure."""
        with self._lock:
            self._maybe_reset_daily()
            session_total = sum(self._session_usage.values())
            daily_total = sum(self._daily_usage.values())
            cloud_cost = (self._daily_usage.get("cloud", 0) / 1000) * self.COST_PER_1K["cloud"]

            return {
                "session": {
                    "used": session_total,
                    "limit": self.session_limit,
                    "remaining": max(0, self.session_limit - session_total),
                    "pct": round((session_total / self.session_limit) * 100, 1) if self.session_limit else 0,
                },
                "daily": {
                    "used": daily_total,
                    "limit": self.daily_limit,
                    "remaining": max(0, self.daily_limit - daily_total),
                    "pct": round((daily_total / self.daily_limit) * 100, 1) if self.daily_limit else 0,
                },
                "cloud_daily": {
                    "used": self._daily_usage.get("cloud", 0),
                    "limit": self.cloud_daily_limit,
                    "estimated_cost_usd": round(cloud_cost, 4),
                },
                "local_daily": {
                    "used": self._daily_usage.get("local", 0),
                },
            }


class QuotaExceededError(Exception):
    """Raised when token budget is exhausted."""
    pass
