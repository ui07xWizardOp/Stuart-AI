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
import logging
from core.llm_clients import OllamaClient, OpenAIClient
from core.circuit_breaker import CircuitBreaker, CircuitOpenError
from core.token_quota import TokenQuota, QuotaExceededError

class ModelTier(str, Enum):
    FAST_CHEAP = "fast_cheap"     
    BALANCED = "balanced"         
    REASONING = "reasoning"
    MAX_COMPUTE = "max_compute"


from dataclasses import dataclass

@dataclass
class ModelEndpoint:
    provider: str
    model: str
    tier: ModelTier
    max_tokens: int
    temperature: float = 0.0
    top_p: float = 1.0

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

    @property
    def local_client(self):
        if getattr(self, '_local_client', None) is None:
            self._local_client = OllamaClient()
        return self._local_client

    @local_client.setter
    def local_client(self, value):
        self._local_client = value

    @property
    def cloud_client(self):
        if getattr(self, '_cloud_client', None) is None:
            self._cloud_client = OpenAIClient()
        return self._cloud_client

    @cloud_client.setter
    def cloud_client(self, value):
        self._cloud_client = value

    def __init__(
        self,
        endpoints: Optional[List[ModelEndpoint]] = None,
        token_quota: Optional[TokenQuota] = None,
        ollama_breaker_threshold: int = 3,
        cloud_breaker_threshold: int = 2,
        recovery_timeout: float = 60.0,
    ):
        
        try:
            self.logger = get_logging_system()
        except Exception:
            self.logger = logging.getLogger(__name__)
        
        if endpoints is not None:
            self.endpoints = endpoints
            self._local_client = None
            self._cloud_client = None
        else:
            self.endpoints = [
                ModelEndpoint(provider="ollama", model="llama3:latest", tier=ModelTier.FAST_CHEAP, max_tokens=2048),
                ModelEndpoint(provider="openai", model="gpt-4o-mini", tier=ModelTier.BALANCED, max_tokens=4096),
                ModelEndpoint(provider="openai", model="gpt-4o", tier=ModelTier.REASONING, max_tokens=8192),
                ModelEndpoint(provider="openai", model="gpt-4o", tier=ModelTier.MAX_COMPUTE, max_tokens=16384),
            ]
            self._local_client = None
            self._cloud_client = None
        
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        for ep in self.endpoints:
            self.circuit_breakers[f"{ep.provider}:{ep.model}"] = CircuitBreaker(name=f"{ep.provider}:{ep.model}")
        
        # Circuit breakers — one per provider
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
        if endpoints is not None:
            self.quota = token_quota
        else:
            self.quota = token_quota or TokenQuota()
        
        self.logger.info(
            "⚡ Hardened Dual-LLM Dispatcher initialized. "
            "(Local: Ollama [CB:3], Cloud: OpenAI [CB:2], Quota: active)"
        )

    def select_model(self, tier: ModelTier, fallback_allowed: bool = True) -> Optional[ModelEndpoint]:
        if not self.endpoints:
            return None
        exact = [ep for ep in self.endpoints if ep.tier == tier]
        if exact:
            return exact[0]
        if fallback_allowed:
            # Fallback hierarchy: try closest tiers
            tier_order = [ModelTier.FAST_CHEAP, ModelTier.BALANCED, ModelTier.REASONING, ModelTier.MAX_COMPUTE]
            try:
                idx = tier_order.index(tier)
                for t in tier_order[idx:] + list(reversed(tier_order[:idx])):
                    exact = [ep for ep in self.endpoints if ep.tier == t]
                    if exact:
                        return exact[0]
            except ValueError:
                pass
            return self.endpoints[0]
        return None

    def execute_with_failover_legacy(self, call_fn: Callable[[ModelEndpoint], Any], tier: ModelTier) -> Any:
        candidates = [ep for ep in self.endpoints if ep.tier == tier] or list(self.endpoints)
        last_error = None
        for ep in candidates:
            key = f"{ep.provider}:{ep.model}"
            breaker = self.circuit_breakers[key]
            try:
                res = breaker.call(call_fn, ep)
                return res
            except Exception as e:
                last_error = e
        if last_error:
            raise last_error
        raise RuntimeError("No endpoints available")

    def evaluate_prompt_complexity(self, messages: List[Dict[str, str]]) -> ModelTier:
        """
        Determines the required tier based on task heuristics.
        """
        raw_text = " ".join([m.get("content", "") for m in messages]).lower()
        
        # Heuristic 1: Token estimation (assume 4 chars per token)
        estimated_tokens = len(raw_text) / 4
        
        # Heuristic 2: Heavy-lift intent keywords
        complex_keywords = ["code", "write", "debug", "python", "fastapi", "script", "refactor", "algorithm", "build", "frontend", "backend"]
        requires_coding = any(kw in raw_text for kw in complex_keywords)
        
        # Heuristic 3: Max compute keywords
        max_compute_keywords = ["architect", "system design", "cryptography", "concurrency", "distributed", "security audit"]
        requires_max_compute = any(kw in raw_text for kw in max_compute_keywords)

        if estimated_tokens > 4000 or requires_max_compute:
            self.logger.info(f"Dispatch logic: Very high complexity detected ({int(estimated_tokens)} tokens / max compute intent). Routing MAX_COMPUTE.")
            return ModelTier.MAX_COMPUTE
        elif estimated_tokens > 2000 or requires_coding:
            self.logger.info(f"Dispatch logic: High complexity detected ({int(estimated_tokens)} tokens / coding intent). Routing REASONING.")
            return ModelTier.REASONING
        elif estimated_tokens > 1000:
            self.logger.info(f"Dispatch logic: Moderate complexity task ({int(estimated_tokens)} tokens). Routing BALANCED.")
            return ModelTier.BALANCED
            
        self.logger.info(f"Dispatch logic: Low complexity task ({int(estimated_tokens)} tokens). Routing FAST_CHEAP.")
        return ModelTier.FAST_CHEAP

    def _estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Rough token count for quota pre-flight checks."""
        return sum(len(m.get("content", "")) for m in messages) // 4

    def execute_with_failover(self, messages, force_tier: Optional[ModelTier] = None):
        """
        Executes the prompt array with circuit breaker + quota protection.
        
        Failover logic:
        1. If target is FAST_CHEAP (Ollama):
           a. Try Ollama through its circuit breaker
           b. If Ollama circuit is OPEN, check Cloud budget -> failover to Cloud
           c. If Cloud budget exhausted, raise hard error
        2. If target is BALANCED, REASONING, or MAX_COMPUTE (Cloud):
           a. Check token quota -> reject if budget exhausted
           b. Try Cloud through its circuit breaker
           c. Record actual token usage
        """
        if callable(messages):
            # legacy signature: execute_with_failover(call_fn, tier)
            return self.execute_with_failover_legacy(messages, force_tier or ModelTier.FAST_CHEAP)

        target_tier = force_tier if force_tier else self.evaluate_prompt_complexity(messages)
        estimated_tokens = self._estimate_tokens(messages)
        
        # 1. Resolve model and provider based on endpoints
        endpoint = self.select_model(target_tier)
        if endpoint:
            provider = endpoint.provider.lower()
            model_name = endpoint.model
        else:
            # Fallback defaults
            if target_tier == ModelTier.FAST_CHEAP:
                provider = "ollama"
                model_name = "llama3:latest"
            else:
                provider = "openai"
                if target_tier == ModelTier.BALANCED:
                    model_name = "gpt-4o-mini"
                elif target_tier == ModelTier.REASONING:
                    model_name = "gpt-4o"
                elif target_tier == ModelTier.MAX_COMPUTE:
                    model_name = "gpt-4o"
                else:
                    model_name = "gpt-4o"
        
        # === FAST_CHEAP (Ollama) path ===
        if provider in ["ollama", "local"]:
            try:
                result = self.ollama_breaker.call(self.local_client.generate_chat, messages, model_name=model_name)
                self.quota.record_usage("local", prompt_tokens=estimated_tokens, completion_tokens=estimated_tokens)
                return result
            except CircuitOpenError as e:
                # Ollama is down -> try controlled Cloud failover
                self.logger.warning(
                    f"🔴 Ollama circuit OPEN. Attempting controlled Cloud failover..."
                )
                return self._cloud_failover(messages, estimated_tokens)
            except RuntimeError as e:
                if str(e) == "OLLAMA_CONNECTION_FAILED":
                    # Record failure in circuit breaker (it's already recorded by .call())
                    self.logger.warning("Ollama connection failed. Attempting Cloud failover...")
                    return self._cloud_failover(messages, estimated_tokens)
                raise
                    
        # === CLOUD PATHS (Balanced, Reasoning, Max Compute) ===
        elif provider in ["openai", "cloud", "remote"]:
            return self._call_cloud(messages, estimated_tokens, model_name=model_name)
            
        raise ValueError(f"Unsupported Tier dispatch context: {target_tier}")

    def _call_cloud(self, messages: List[Dict[str, str]], estimated_tokens: int, model_name: Optional[str] = None) -> str:
        """Call Cloud API with quota check + circuit breaker."""
        # Pre-flight budget check
        try:
            self.quota.check_budget("cloud", estimated_tokens * 2)  # *2 for prompt+completion
        except QuotaExceededError as e:
            self.logger.error(f"🔴 {e}")
            raise

        # If model_name is not provided, resolve it
        if not model_name:
            endpoint = self.select_model(ModelTier.BALANCED) or self.select_model(ModelTier.REASONING)
            model_name = endpoint.model if endpoint else "gpt-4o-mini"

        # Execute through circuit breaker
        result = self.cloud_breaker.call(self.cloud_client.generate_chat, messages, model_name=model_name)
        
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
                "🔴 Cannot failover to Cloud — daily budget exhausted. "
                "Both Ollama (offline) and Cloud (budget exceeded) are unavailable."
            )
            raise RuntimeError(
                "All LLM providers unavailable. "
                "Ollama is offline and Cloud API budget is exhausted."
            )

        self.logger.info("⚡⚡ Failover: Routing local task to Cloud API (within budget).")
        # For failover, we want to route to BALANCED tier (gpt-4o-mini)
        endpoint = self.select_model(ModelTier.BALANCED)
        model_name = endpoint.model if endpoint else "gpt-4o-mini"
        return self._call_cloud(messages, estimated_tokens, model_name=model_name)

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
