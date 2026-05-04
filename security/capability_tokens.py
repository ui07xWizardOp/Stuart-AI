"""
Capability Token System (Task 13)

Provides a time-bounded, verifiable permissions token architecture.
Allows the orchestrator to grant explicit capabilities to an executor environment.
"""

import time
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from observability import get_logging_system
import logging


@dataclass
class CapabilityToken:
    """A time-bounded, verifiable permission token for tool execution.

    Represents a specific authorization jump granted by the orchestrator.
    Tokens are stateless and validated against their expiration and revocation status.

    Attributes:
        token_id (str): Unique UUID v4 identifier for tracking.
        capability_name (str): The specific tool capability authorized (e.g., 'file_write').
        target_resource (str): Resource pinning (e.g., a specific file path or '*').
        issued_at (float): Epoch timestamp of token creation.
        expires_at (float): Epoch timestamp of token expiration.
        is_revoked (bool): Flag indicating if the token was manually invalidated.
    """
    token_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    capability_name: str = ""
    target_resource: str = "*" # Resource wildcard by default
    issued_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    is_revoked: bool = False

    def is_valid(self) -> bool:
        """Checks if the token is currently active and within its TTL."""
        if self.is_revoked:
            return False
        if time.time() > self.expires_at:
            return False
        return True


class CapabilityTokenSystem:
    """Manages the granular lifecycle of security capability tokens.

    Responsible for minting new tokens with custom TTLs, performing resource-pinned 
    validation, and maintaining the revocation list.

    Attributes:
        _tokens (Dict[str, CapabilityToken]): Active token registry (in-memory).
        default_ttl (float): Default time-to-live in seconds for new tokens.
    """
    
    def __init__(self, default_ttl_sec: float = 300.0):
        
        try:
            self.logger = get_logging_system()
        except Exception:
            self.logger = logging.getLogger(__name__)
        self.default_ttl_sec = default_ttl_sec
        # Internal store: UUID -> CapabilityToken
        self._tokens: Dict[str, CapabilityToken] = {}
        
    def mint_token(self, capability_name: str, target_resource: str = "*", ttl_sec: Optional[float] = None) -> CapabilityToken:
        """
        Generate a new capability token permitting specific actions.
        """
        ttl = ttl_sec if ttl_sec is not None else self.default_ttl_sec
        
        token = CapabilityToken(
            capability_name=capability_name,
            target_resource=target_resource,
            expires_at=time.time() + ttl
        )
        
        self._tokens[token.token_id] = token
        self.logger.debug(f"Minted token {token.token_id} for capability '{capability_name}' (TTL: {ttl}s)")
        return token
        
    def validate_capability(self, token_id: str, requested_capability: str, requested_resource: str = "*") -> bool:
        """
        Validates if the submitted token ID successfully permits the requested operation.
        """
        token = self._tokens.get(token_id)
        if not token:
            self.logger.warning(f"Capability validation failed: Token {token_id} does not exist.")
            return False
            
        if not token.is_valid():
            self.logger.warning(f"Capability validation failed: Token {token_id} is expired or revoked.")
            return False
            
        if token.capability_name != requested_capability:
            self.logger.warning(
                f"Capability mismatch: Token {token_id} granted '{token.capability_name}', "
                f"but '{requested_capability}' was requested."
            )
            return False
            
        if token.target_resource != "*" and token.target_resource != requested_resource:
            self.logger.warning(f"Resource boundary violation attempted by token {token_id}.")
            return False
            
        return True
        
    def revoke_token(self, token_id: str) -> None:
        """Immediately revoke a token."""
        token = self._tokens.get(token_id)
        if token:
            token.is_revoked = True
            self.logger.info(f"Token {token_id} explicitly revoked.")
            
    def prune_expired_tokens(self) -> int:
        """Clean up internal store of old tokens to prevent memory leaks."""
        current_time = time.time()
        expired_ids = [tid for tid, t in self._tokens.items() if t.expires_at < current_time or t.is_revoked]
        
        for tid in expired_ids:
            del self._tokens[tid]
            
        if expired_ids:
            self.logger.debug(f"Pruned {len(expired_ids)} expired/revoked capability tokens.")
            
        return len(expired_ids)
