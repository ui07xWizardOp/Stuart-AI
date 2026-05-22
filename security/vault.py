"""
Secure Vault (Feature #51)

Provides API Key encryption at rest. 
Uses the OS Keyring to store a master encryption key, and Fernet to encrypt/decrypt
sensitive values stored in a local vault file.
"""

import os
from typing import Optional
import json
import base64
from pathlib import Path
from observability import get_logging_system

try:
    import keyring
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

class SecureVault:
    def __init__(self, vault_path: str = "data/vault.json", service_name: str = "stuart_ai"):
        self.logger = get_logging_system()
        self.vault_path = Path(vault_path)
        self.service_name = service_name
        self.fernet = None
        
        # Ensure vault file exists in all modes (plaintext fallback & encrypted)
        if not self.vault_path.parent.exists():
            self.vault_path.parent.mkdir(parents=True, exist_ok=True)
            
        if not self.vault_path.exists():
            self.vault_path.write_text("{}")
            
        if not CRYPTO_AVAILABLE:
            self.logger.warning("Cryptography or Keyring not installed. Vault is running in plaintext mode.")
            return

        self._initialize_vault()

    def _initialize_vault(self):
        # Try to load master key from OS Keyring
        key_str = keyring.get_password(self.service_name, "vault_master_key")
        if not key_str:
            self.logger.info("Generating new master encryption key in OS Keyring.")
            new_key = Fernet.generate_key()
            key_str = new_key.decode("utf-8")
            keyring.set_password(self.service_name, "vault_master_key", key_str)
            
        self.fernet = Fernet(key_str.encode("utf-8"))
        self.logger.info("Secure Vault unlocked via OS Keyring.")

    def _read_vault(self) -> dict:
        try:
            return json.loads(self.vault_path.read_text())
        except json.JSONDecodeError:
            return {}

    def _write_vault(self, data: dict):
        self.vault_path.write_text(json.dumps(data, indent=4))

    def set_secret(self, key: str, value: str):
        """Encrypt and store a secret."""
        vault_data = self._read_vault()
        if self.fernet:
            encrypted_value = self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")
            vault_data[key] = f"ENC:{encrypted_value}"
        else:
            # Plaintext fallback if crypto is unavailable
            vault_data[key] = f"PT:{value}"
            
        self._write_vault(vault_data)
        self.logger.info(f"Secret '{key}' stored in vault.")

    def get_secret(self, key: str) -> str:
        """Retrieve and decrypt a secret."""
        vault_data = self._read_vault()
        if key not in vault_data:
            return None
            
        val = vault_data[key]
        if val.startswith("ENC:"):
            if not self.fernet:
                raise RuntimeError("Vault contains encrypted secrets but crypto/keyring is unavailable.")
            encrypted_value = val[4:]
            return self.fernet.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
        elif val.startswith("PT:"):
            return val[3:]
            
        return val # legacy fallback

    def migrate_from_env(self, env_path: str = ".env"):
        """Utility to scan .env and migrate sensitive keys (e.g. *_API_KEY) into the vault."""
        path = Path(env_path)
        if not path.exists():
            return
            
        from core.env_utils import EnvManager
        env_mgr = EnvManager(file_path=str(path))
        
        lines = path.read_text().splitlines()
        migrated = False
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip('"\' ')
                if "API_KEY" in k and v and v != "<migrated_to_vault>":
                    self.set_secret(k, v)
                    env_mgr.update_key(k, "<migrated_to_vault>")
                    migrated = True
        
        if migrated:
            self.logger.info(f"Migrated API keys from {env_path} to secure vault.")

_vault_instance = None

def get_vault() -> SecureVault:
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = SecureVault()
    return _vault_instance

def get_vault_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve secret from vault, falling back to environment/default."""
    try:
        vault = get_vault()
        secret = vault.get_secret(key)
        if secret is not None:
            return secret
    except Exception:
        pass
    return os.getenv(key, default)
