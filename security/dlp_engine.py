"""
Data Loss Prevention (DLP) Engine (Task 14)

Scans tool outputs and agent reasoning streams for sensitive data
like API keys, passwords, or personal info, and structurally redacts or blocks them.
"""

import re
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass

from observability import get_logging_system


class DLPRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"      # Redact and allow
    HIGH = "high"          # Block entirely
    CRITICAL = "critical"  # Block and trigger alert


@dataclass
class DLPPattern:
    name: str
    pattern: str
    risk_level: DLPRiskLevel
    description: str


class DataLossPreventionEngine:
    """Scans text strings for sensitive tokens using a priority-based regex registry.

    Provides real-time redaction of medium-risk data (e.g., JWTs) and hard-blocking 
    for high-risk data (e.g., API keys) to prevent information leakage from 
    tool outputs or reasoning streams.

    Attributes:
        _patterns (List[DLPPattern]): The internal registry of compiled regex patterns and their risk tiers.
    """
    
    def __init__(self):
        self.logger = get_logging_system()
        self._patterns: List[DLPPattern] = self._default_patterns()
        
    def _default_patterns(self) -> List[DLPPattern]:
        return [
            # Dummy mock patterns for testing and standard formats
            DLPPattern(
                name="openai_api_key",
                pattern=r"sk-[a-zA-Z0-9]{32,}",
                risk_level=DLPRiskLevel.HIGH,
                description="OpenAI API Key"
            ),
            DLPPattern(
                name="aws_access_key",
                pattern=r"(?i)AKIA[0-9A-Z]{16}",
                risk_level=DLPRiskLevel.HIGH,
                description="AWS Access Key ID"
            ),
            DLPPattern(
                name="jwt_token",
                pattern=r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+",
                risk_level=DLPRiskLevel.MEDIUM,
                description="JWT Authorization Token"
            ),
            DLPPattern(
                name="generic_password_assignment",
                pattern=r"(?i)(password|passwd|pwd)\s*=\s*['\"]([^'\"]+)['\"]",
                risk_level=DLPRiskLevel.MEDIUM,
                description="Hardcoded password assignment"
            )
        ]
        
    def add_pattern(self, pattern: DLPPattern) -> None:
        self._patterns.append(pattern)
        
    def scan_and_redact(self, text: str) -> str:
        """
        Scans text. If MEDIUM risk issues are found, redacts them safely.
        If HIGH or CRITICAL issues are found, raises a ValueError to block the channel entirely.
        """
        if not isinstance(text, str):
            # We only scan strings. Complex objects should be serialized to JSON first if scanning is required.
            return text
            
        redacted_text = text
        highest_risk = DLPRiskLevel.LOW
        
        for p in self._patterns:
            matches = re.finditer(p.pattern, redacted_text)
            has_match = False
            
            for match in matches:
                has_match = True
                if p.risk_level in (DLPRiskLevel.HIGH, DLPRiskLevel.CRITICAL):
                    self.logger.critical(f"DLP blocked output: Detected {p.name} (Risk: {p.risk_level.value})")
                    raise ValueError(f"DLP Engine blocked output due to sensitive data: {p.name}")
                    
                # Redact MEDIUM risk
                if p.risk_level == DLPRiskLevel.MEDIUM:
                    # If groups exist, redact the specific group (e.g., in password assignment)
                    if match.groups():
                        # Just a basic replace for the whole match for simplicity here,
                        # in a real engine you'd replace just the capture group
                        redacted_text = redacted_text.replace(match.group(0), f"<{p.name.upper()}_REDACTED>")
                    else:
                        redacted_text = redacted_text.replace(match.group(0), f"<{p.name.upper()}_REDACTED>")
            
            if has_match:
                self.logger.warning(f"DLP Redacted {p.name} from output.")
                
        return redacted_text
