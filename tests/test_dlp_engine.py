"""
Tests for Data Loss Prevention (DLP) Engine (Task 14)
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock

# Mock observability module

from security.dlp_engine import DataLossPreventionEngine, DLPRiskLevel, DLPPattern


def test_dlp_medium_risk_redaction():
    dlp = DataLossPreventionEngine()
    
    # Contains a JWT format
    input_text = "Here is my token: eyJhbGciOiJI.eyJzdWIiOi.SflKxwRJSMeKKF2QT4fwpMeJf36POk"
    
    result = dlp.scan_and_redact(input_text)
    assert not "eyJhbGciOiJI" in result
    assert "<JWT_TOKEN_REDACTED>" in result
    
def test_dlp_high_risk_blocking():
    dlp = DataLossPreventionEngine()
    
    # Contains an OpenAI format key
    input_text = "My sk-abcdefghijklmnopqrstuvwxyz123456 is here."
    
    with pytest.raises(ValueError, match="blocked output"):
        dlp.scan_and_redact(input_text)

def test_dlp_custom_pattern():
    dlp = DataLossPreventionEngine()
    dlp.add_pattern(DLPPattern("social_security", r"\d{3}-\d{2}-\d{4}", DLPRiskLevel.MEDIUM, "SSN"))
    
    result = dlp.scan_and_redact("My ssn is 123-45-6789.")
    assert "123-45" not in result
    assert "<SOCIAL_SECURITY_REDACTED>" in result
