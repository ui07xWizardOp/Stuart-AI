"""
Trust Levels (Feature #48)

Defines granular trust boundaries that dictate what tools, files, or actions
an agent or user is allowed to perform. This extends beyond simple AutonomyLevel
and ToolRiskLevel by assigning identities to execution contexts.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional

class TrustLevel(str, Enum):
    """
    Categorizes the identity or origin of a request/agent.
    
    Tiers:
        UNTRUSTED: External web requests, unverified users, generic MCP plugins.
                   Blocked from dangerous commands and sensitive file access.
        VERIFIED: Authenticated users, trusted sub-agents. Normal operating mode.
        OWNER: The primary user of the machine. Full access to system resources.
    """
    UNTRUSTED = "untrusted"
    VERIFIED = "verified"
    OWNER = "owner"

# Internal mapping of numeric clearance levels for comparisons
_TRUST_CLEARANCE = {
    TrustLevel.UNTRUSTED: 0,
    TrustLevel.VERIFIED: 1,
    TrustLevel.OWNER: 2,
}

def has_sufficient_trust(current: TrustLevel, required: TrustLevel) -> bool:
    """Check if current trust level meets or exceeds the required level."""
    return _TRUST_CLEARANCE[current] >= _TRUST_CLEARANCE[required]

@dataclass
class TrustContext:
    """Holds the identity and trust boundaries for an active session or thread."""
    level: TrustLevel = TrustLevel.VERIFIED
    source: str = "local_cli"
    
    def escalate(self, target: TrustLevel, reason: str) -> bool:
        """Attempt to escalate privileges. Currently mocked to fail unless OWNER."""
        # Future: Could send a push notification to user's phone for escalation approval.
        if self.level == TrustLevel.OWNER:
            self.level = target
            return True
        return False
