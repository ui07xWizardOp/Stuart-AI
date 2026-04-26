"""
Tests for Capability Token System (Task 13)
"""

import sys
import time
import pytest
from unittest.mock import Mock, MagicMock

# Mock observability module
mock_logger = MagicMock()
sys.modules['observability'] = MagicMock()
sys.modules['observability'].get_logging_system = Mock(return_value=mock_logger)

from capability_tokens import CapabilityTokenSystem


def test_token_minting_and_validation():
    system = CapabilityTokenSystem()
    
    token = system.mint_token("read_file", "C:\\temp")
    
    # Valid validation
    assert system.validate_capability(token.token_id, "read_file", "C:\\temp") is True
    
    # Missing/wrong token
    assert system.validate_capability("fake_uuid", "read_file", "C:\\temp") is False
    
    # Capability mismatch
    assert system.validate_capability(token.token_id, "write_file", "C:\\temp") is False
    
    # Resource mismatch
    assert system.validate_capability(token.token_id, "read_file", "C:\\windows") is False

def test_token_revocation():
    system = CapabilityTokenSystem()
    token = system.mint_token("web_search")
    
    assert system.validate_capability(token.token_id, "web_search", "query") is True
    
    system.revoke_token(token.token_id)
    assert system.validate_capability(token.token_id, "web_search", "query") is False

def test_token_expiration():
    system = CapabilityTokenSystem()
    token = system.mint_token("quick_action", ttl_sec=0.1)
    
    assert system.validate_capability(token.token_id, "quick_action") is True
    
    time.sleep(0.15)
    assert system.validate_capability(token.token_id, "quick_action") is False

def test_pruning():
    system = CapabilityTokenSystem()
    t1 = system.mint_token("t1", ttl_sec=0.1)
    t2 = system.mint_token("t2", ttl_sec=5.0)
    
    time.sleep(0.15)
    
    pruned = system.prune_expired_tokens()
    assert pruned == 1
    assert t1.token_id not in system._tokens
    assert t2.token_id in system._tokens
