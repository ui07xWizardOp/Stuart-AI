# Stuart Security Architecture: Defensive Guards

Stuart-AI employs a multi-layered defensive strategy to ensure that the agent remains safe, private, and within its intended boundaries. This is achieved through a suite of **Defensive Guards** that intercept actions before execution and scan outputs before presentation.

## 🛡️ 1. File Access Guard
The `FileAccessGuard` is the primary filesystem firewall. It prevents the agent from interacting with dangerous system paths or sensitive user directories.

### Key Protections
- **Process Cloaking**: Prevents the agent from seeing or modifying its own process or system config.
- **Credential Protection**: Hard-blocks access to `~/.ssh`, `~/.aws`, `~/.kube`, and browser data directories.
- **System Integrity**: Blocks access to `C:\Windows\System32` and other critical OS paths.
- **Extension Filtering**: Blocks the creation or execution of dangerous file types (e.g., `.exe`, `.bat`, `.dll`, `.ps1`).

### Implementation
- **File**: `security/file_access_guard.py`
- **Mechanism**: Path normalization + resolved path blocklisting.

## 🔍 2. Data Loss Prevention (DLP) Engine
The `DLPEngine` scans the agent's reasoning streams and tool outputs for sensitive information, such as API keys, passwords, or PII.

### Risk Levels
| Tier | Action | Example |
| :--- | :--- | :--- |
| **LOW** | Allow | Public project names |
| **MEDIUM** | Redact | JWT tokens, partial passwords |
| **HIGH** | Block Action | OpenAI/AWS API keys |
| **CRITICAL** | Block & Alert | Plaintext master passwords |



### Implementation
- **File**: `security/dlp_engine.py`
- **Mechanism**: High-performance regex scanning with redaction masks (e.g., `<OPENAI_API_KEY_REDACTED>`).

## 🎟️ 3. Capability Token System
The `CapabilityTokenSystem` implements a time-bounded, verifiable permissions architecture. It allows the orchestrator to grant "limited-time" permissions for specific high-risk tasks.

### Features
- **TTL Enforcement**: Tokens expire automatically (default: 5 minutes).
- **Resource Pinning**: A token might grant write access *only* to a specific file, not the entire drive.
- **Revocation**: The system can instantly kill active tokens if suspicious behavior is detected.

### Implementation
- **File**: `security/capability_tokens.py`
- **Mechanism**: UUID-based tokens with metadata validation.

## ⚙️ Configuration & Tech Specs
Security guards are configured via `config/security_config.json` and environmental overrides.

For granular technical details (regex patterns, blocked path tables, and token lifecycle), see the **[SECURITY_SPECIFICATION.md](SECURITY_SPECIFICATION.md)**.

---

> [!CAUTION]
> Manually editing the `DEFAULT_BLOCKED_PATHS` in `security/file_access_guard.py` is discouraged unless you are an advanced user. Removing entries like `~/.ssh` could expose your credentials to the LLM.
