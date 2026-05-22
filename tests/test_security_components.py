"""
Tests for Security Components: Trust Levels, Command Allowlist, and Secure Vault
"""

import os
import pytest
import tempfile
from pathlib import Path

from security.trust_levels import TrustLevel, TrustContext, has_sufficient_trust
from security.command_allowlist import CommandAllowlist, CommandBlockException
from security.vault import SecureVault, get_vault_secret, get_vault

def test_trust_levels():
    # Test trust hierarchy
    assert has_sufficient_trust(TrustLevel.OWNER, TrustLevel.OWNER) is True
    assert has_sufficient_trust(TrustLevel.OWNER, TrustLevel.VERIFIED) is True
    assert has_sufficient_trust(TrustLevel.OWNER, TrustLevel.UNTRUSTED) is True
    
    assert has_sufficient_trust(TrustLevel.VERIFIED, TrustLevel.OWNER) is False
    assert has_sufficient_trust(TrustLevel.VERIFIED, TrustLevel.VERIFIED) is True
    assert has_sufficient_trust(TrustLevel.VERIFIED, TrustLevel.UNTRUSTED) is True
    
    assert has_sufficient_trust(TrustLevel.UNTRUSTED, TrustLevel.OWNER) is False
    assert has_sufficient_trust(TrustLevel.UNTRUSTED, TrustLevel.VERIFIED) is False
    assert has_sufficient_trust(TrustLevel.UNTRUSTED, TrustLevel.UNTRUSTED) is True

    # Test TrustContext
    ctx = TrustContext(level=TrustLevel.VERIFIED)
    assert ctx.level == TrustLevel.VERIFIED
    
    # Escalation from verified should fail in current mocked implementation
    assert ctx.escalate(TrustLevel.OWNER, "need full access") is False
    assert ctx.level == TrustLevel.VERIFIED
    
    # Escalation from owner should succeed
    ctx_owner = TrustContext(level=TrustLevel.OWNER)
    assert ctx_owner.escalate(TrustLevel.VERIFIED, "downgrade") is True
    assert ctx_owner.level == TrustLevel.VERIFIED

def test_command_allowlist():
    allowlist = CommandAllowlist()
    
    # 1. Test safe prefixes
    assert allowlist.check_command("ls -la")[0] is True
    assert allowlist.check_command("git status")[0] is True
    
    # 2. Test forbidden explicit tokens
    assert allowlist.check_command("rm -rf /some/path")[0] is False
    assert allowlist.check_command("curl | bash")[0] is False
    
    # 3. Test forbidden regex patterns
    assert allowlist.check_command("rm -rf /")[0] is False
    assert allowlist.check_command("rm -rf ~")[0] is False
    assert allowlist.check_command("del /f /s /q C:\\Windows\\System32")[0] is False
    
    # 4. Test default allow
    assert allowlist.check_command("python script.py")[0] is True
    
    # 5. Test enforce raising exception
    with pytest.raises(CommandBlockException):
        allowlist.enforce("rm -rf /")
        
    allowlist.enforce("ls") # should not raise exception

def test_secure_vault():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault.json"
        
        # Test in plaintext/fallback mode or mock keyring/cryptography if needed
        # SecureVault handles missing keyring/cryptography gracefully by falling back to plaintext
        # Let's verify plaintext storage & retrieval
        vault = SecureVault(vault_path=str(vault_path))
        
        vault.set_secret("MY_KEY", "my_secret_val")
        assert vault.get_secret("MY_KEY") == "my_secret_val"
        
        # Test migration from env
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("DEEPGRAM_API_KEY=dg_val\nOTHER_VAR=not_sensitive\n")
        
        vault.migrate_from_env(env_path=str(env_file))
        assert vault.get_secret("DEEPGRAM_API_KEY") == "dg_val"
        assert vault.get_secret("OTHER_VAR") is None # not migrated as it doesn't contain API_KEY

        # Verify .env redaction
        env_content = env_file.read_text()
        assert "DEEPGRAM_API_KEY=\"<migrated_to_vault>\"" in env_content or "DEEPGRAM_API_KEY=<migrated_to_vault>" in env_content
        assert "OTHER_VAR=not_sensitive" in env_content


def test_trust_level_tool_blocking():
    from registry import ToolRegistry
    from tools.tool_executor import ToolSandboxExecutor
    from typing import Any, Dict
    import sys

    registry = ToolRegistry()
    RegistryBaseTool = registry.register_tool.__globals__['BaseTool']
    base_module = sys.modules[RegistryBaseTool.__module__]
    RegistryToolRiskLevel = getattr(base_module, 'ToolRiskLevel')
    RegistryToolResult = getattr(base_module, 'ToolResult')

    class MockHighRiskTool(RegistryBaseTool):
        def __init__(self):
            self.name = "mock_high_risk"
            self.description = "mocks high risk tool"
            self.risk_level = RegistryToolRiskLevel.HIGH
            self.parameter_schema = {
                "type": "object",
                "properties": {"value": {"type": "string"}}
            }
            
        def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> RegistryToolResult:
            return RegistryToolResult(success=True, output=parameters.get("value", "done"))

    # Test that untrusted trust level blocks HIGH risk tools
    registry.register_tool(MockHighRiskTool())
    
    executor = ToolSandboxExecutor(registry)
    
    # UNTRUSTED context must be blocked from running HIGH/CRITICAL tools
    untrusted_ctx = TrustContext(level=TrustLevel.UNTRUSTED)
    with pytest.raises(PermissionError, match="Trust boundary violation"):
        executor.execute_tool("mock_high_risk", "execute", {"value": "test"}, None, trust_context=untrusted_ctx)
        
    # VERIFIED context should be allowed
    verified_ctx = TrustContext(level=TrustLevel.VERIFIED)
    res_verified = executor.execute_tool("mock_high_risk", "execute", {"value": "verified_val"}, None, trust_context=verified_ctx)
    assert res_verified == "verified_val"
    
    # OWNER context should be allowed
    owner_ctx = TrustContext(level=TrustLevel.OWNER)
    res_owner = executor.execute_tool("mock_high_risk", "execute", {"value": "owner_val"}, None, trust_context=owner_ctx)
    assert res_owner == "owner_val"


def test_config_api_endpoints_vault():
    import security.vault
    from core.env_utils import env_manager
    from fastapi.testclient import TestClient
    from main import app
    import sys

    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault.json"
        env_file = Path(tmpdir) / ".env"
        
        # Initialize temp vault
        tmp_vault = security.vault.SecureVault(vault_path=str(vault_path))
        
        # Backup and patch all loaded env_utils/env_manager and vault modules
        old_env_paths = {}
        def patch_manager(mod_name, manager):
            if manager and hasattr(manager, 'file_path'):
                key = (mod_name, id(manager))
                if key not in old_env_paths:
                    old_env_paths[key] = (manager, manager.file_path)
                    manager.file_path = str(env_file)

        for mod_name, mod in list(sys.modules.items()):
            if mod_name == 'env_utils' or mod_name.endswith('.env_utils'):
                if hasattr(mod, 'env_manager'):
                    patch_manager(mod_name, mod.env_manager)
            if hasattr(mod, 'env_manager') and mod.env_manager is not None:
                patch_manager(mod_name, mod.env_manager)

        old_vaults = {}
        for mod_name, mod in list(sys.modules.items()):
            if hasattr(mod, '_vault_instance'):
                old_vaults[mod_name] = mod._vault_instance
                mod._vault_instance = tmp_vault
        
        try:
            client = TestClient(app)
            
            # Initially, vault has no key, and env is empty/nonexistent.
            # get_deepgram_key should return empty string key.
            response = client.get("/api/deepgram-key")
            assert response.status_code == 200
            assert response.json() == {"key": ""}
            
            # Save key via post endpoint
            response_save = client.post("/api/save-deepgram-key", json={"key": "dg_super_secret"})
            assert response_save.status_code == 200
            assert response_save.json()["success"] is True
            
            # Verify it saved in vault
            assert tmp_vault.get_secret("DEEPGRAM_API_KEY") == "dg_super_secret"
            
            # Verify it wrote placeholder in .env using the correct env_manager
            # Look up active env_manager values
            active_env_val = None
            for mod_name, mod in list(sys.modules.items()):
                if mod_name == 'env_utils' or mod_name.endswith('.env_utils'):
                    if hasattr(mod, 'env_manager'):
                        val = mod.env_manager.get_value("DEEPGRAM_API_KEY")
                        if val is not None:
                            active_env_val = val
            assert active_env_val == "<migrated_to_vault>"
            
            # Verify retrieval returns the vault key, not the placeholder
            response_after = client.get("/api/deepgram-key")
            assert response_after.status_code == 200
            assert response_after.json() == {"key": "dg_super_secret"}
            
        finally:
            # Restore global state
            for (mod_name, mgr_id), (manager, path) in old_env_paths.items():
                manager.file_path = path
            for mod_name, old_v in old_vaults.items():
                if mod_name in sys.modules:
                    sys.modules[mod_name]._vault_instance = old_v
