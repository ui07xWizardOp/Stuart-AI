"""
Model Router (Phase 9A ? Hardened Dual-LLM Dispatcher)

Manages multiple LLM provider backends and intelligently routes requests
based on task complexity, cost constraints, and available latency quotas.

Phase 9A additions:
  - Circuit Breaker: per-provider fault tolerance
  - Token Quota: per-session & per-day budget enforcement
  - Smart Failover: Ollama trips ? controlled Cloud failover (budget permitting)
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from observability import get_logging_system
from core.llm_clients import OllamaClient, OpenAIClient
from core.circuit_breaker import CircuitBreaker, CircuitOpenError
from core.token_quota import TokenQuota, QuotaExceededError

class ModelTier(str, Enum):
    FAST_CHEAP = "fast_cheap"     
    BALANCED = "balanced"         
    REASONING = "reasoning"

class ModelRouter:
    """
    Hardened Dual-LLM Dispatcher (Phase 9A).
    Routes prompts based on complexity/token heuristics to either:
    - Ollama (Local, FAST_CHEAP) ? protected by circuit breaker
    - OpenAI (Cloud, REASONING) ? protected by circuit breaker + token quota
    
    New in Phase 9A:
    - Circuit breakers prevent cascade failures when a provider is down
    - Token quota enforces per-session and per-day cost limits
    - Smart failover: if Ollama is down AND Cloud budget allows, auto-route to Cloud
    """

    def __init__(
        self,
        token_quota: Optional[TokenQuota] = None,
        ollama_breaker_threshold: int = 3,
        cloud_breaker_threshold: int = 2,
        recovery_timeout: float = 60.0,
    ):
        self.logger = get_logging_system()
        
        # Instantiate physical clients
        self.local_client = OllamaClient()
        self.cloud_client = OpenAIClient()
        
        # Circuit breakers ? one per provider
        self.ollama_breaker = CircuitBreaker(
            name="ollama",
            failure_threshold=ollama_breaker_threshold,
            recovery_timeout=recovery_timeout,
        )
        self.cloud_breaker = CircuitBreaker(
            name="cloud_api",
            failure_threshold=cloud_breaker_threshold,
            recovery_timeout=recovery_timeout,
        )
        
        # Token budget manager (shared instance, injected from main.py)
        self.quota = token_quota or TokenQuota()
        
        self.logger.info(
            "?? Hardened Dual-LLM Dispatcher initialized. "
            "(Local: Ollama [CB:3], Cloud: OpenAI [CB:2], Quota: active)"
        )

    def evaluate_prompt_complexity(self, messages: List[Dict[str, str]]) -> ModelTier:
        """
        Determines the required tier based on task heuristics.
        """
        raw_text = " ".join([m["content"] for m in messages]).lower()
        
        # Heuristic 1: Token estimation (assume 4 chars per token)
        estimated_tokens = len(raw_text) / 4
        
        # Heuristic 2: Heavy-lift intent keywords
        complex_keywords = ["code", "write", "debug", "python", "fastapi", "script", "refactor", "algorithm", "build", "frontend", "backend"]
        requires_coding = any(kw in raw_text for kw in complex_keywords)
        
        if estimated_tokens > 2000 or requires_coding:
            self.logger.info(f"Dispatch logic: High complexity detected ({int(estimated_tokens)} tokens / coding intent). Routing HIGH_COMPUTE.")
            return ModelTier.REASONING
            
        self.logger.info(f"Dispatch logic: Low complexity task ({int(estimated_tokens)} tokens). Routing FAST_CHEAP.")
        return ModelTier.FAST_CHEAP

    def _estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Rough token count for quota pre-flight checks."""
        return sum(len(m.get("content", "")) for m in messages) // 4

    def execute_with_failover(self, messages: List[Dict[str, str]], force_tier: Optional[ModelTier] = None) -> str:
        """
        Executes the prompt array with circuit breaker + quota protection.
        
        Failover logic:
        1. If target is FAST_CHEAP (Ollama):
           a. Try Ollama through its circuit breaker
           b. If Ollama circuit is OPEN, check Cloud budget ? failover to Cloud
           c. If Cloud budget exhausted, raise hard error
        2. If target is REASONING (Cloud):
           a. Check token quota ? reject if budget exhausted
           b. Try Cloud through its circuit breaker
           c. Record actual token usage
        """
        target_tier = force_tier if force_tier else self.evaluate_prompt_complexity(messages)
        estimated_tokens = self._estimate_tokens(messages)
        
        # === FAST_CHEAP (Ollama) path ===
        if target_tier == ModelTier.FAST_CHEAP:
            try:
                result = self.ollama_breaker.call(self.local_client.generate_chat, messages)
                self.quota.record_usage("local", prompt_tokens=estimated_tokens, completion_tokens=estimated_tokens)
                return result
            except CircuitOpenError as e:
                # Ollama is down ? try controlled Cloud failover
                self.logger.warning(
                    f"? Ollama circuit OPEN. Attempting controlled Cloud failover..."
                )
                return self._cloud_failover(messages, estimated_tokens)
            except RuntimeError as e:
                if str(e) == "OLLAMA_CONNECTION_FAILED":
                    # Record failure in circuit breaker (it's already recorded by .call())
                    self.logger.warning("Ollama connection failed. Attempting Cloud failover...")
                    return self._cloud_failover(messages, estimated_tokens)
                raise
                    
        # === REASONING (Cloud) path ===
        elif target_tier == ModelTier.REASONING:
            return self._call_cloud(messages, estimated_tokens)
            
        raise ValueError(f"Unsupported Tier dispatch context: {target_tier}")

    def _call_cloud(self, messages: List[Dict[str, str]], estimated_tokens: int) -> str:
        """Call Cloud API with quota check + circuit breaker."""
        # Pre-flight budget check
        try:
            self.quota.check_budget("cloud", estimated_tokens * 2)  # *2 for prompt+completion
        except QuotaExceededError as e:
            self.logger.error(f"? {e}")
            raise

        # Execute through circuit breaker
        result = self.cloud_breaker.call(self.cloud_client.generate_chat, messages)
        
        # Record actual usage (we estimate completion as roughly equal to prompt)
        self.quota.record_usage("cloud", prompt_tokens=estimated_tokens, completion_tokens=estimated_tokens)
        return result

    def _cloud_failover(self, messages: List[Dict[str, str]], estimated_tokens: int) -> str:
        """
        Controlled failover from Ollama to Cloud.
        Only proceeds if Cloud budget allows AND Cloud circuit is healthy.
        """
        try:
            self.quota.check_budget("cloud", estimated_tokens * 2)
        except QuotaExceededError:
            self.logger.error(
                "? Cannot failover to Cloud ? daily budget exhausted. "
                "Both Ollama (offline) and Cloud (budget exceeded) are unavailable."
            )
            raise RuntimeError(
                "All LLM providers unavailable. "
                "Ollama is offline and Cloud API budget is exhausted."
            )

        self.logger.info("?? Failover: Routing local task to Cloud API (within budget).")
        return self._call_cloud(messages, estimated_tokens)

    def get_status(self) -> dict:
        """Return full router health status for API exposure."""
        return {
            "ollama": self.ollama_breaker.get_status(),
            "cloud": self.cloud_breaker.get_status(),
            "quota": self.quota.get_status(),
        }

    def reset_breakers(self):
        """Manual reset of all circuit breakers."""
        self.ollama_breaker.force_reset()
        self.cloud_breaker.force_reset()
