# Stuart Security Specification: Granular Defenses

This technical specification details the exact patterns, paths, and algorithms that govern Stuart's safety layers.

## 🕵️ 1. DLP Pattern Registry
The `DLPEngine` utilizes a optimized regex registry to detect sensitive information.

### Core Regex Specification
| Pattern Name | Tier | Regex Pattern | Target Data |
| :--- | :--- | :--- | :--- |
| `openai_api_key` | HIGH | `sk-[a-zA-Z0-9]{32,}` | OpenAI Secret Keys |
| `aws_access_key` | HIGH | `(?i)AKIA[0-9A-Z]{16}` | AWS Access Key ID |
| `jwt_token` | MEDIUM | `eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+` | Authorization Tokens |
| `generic_pw` | MEDIUM | `(?i)(password\|passwd\|pwd)\s*=\s*['\"]([^'\"]+)['\"]` | Hardcoded Credentials |

### Action Matrix
- **HIGH/CRITICAL**: Immediate `ValueError` raised. The current Orchestrator step is aborted and the observation is wiped.
- **MEDIUM**: Text-based redaction: `<REDACTED_{NAME}>`.

## 📁 2. File Guard Blocklist (Internal Table)
The `FileAccessGuard` performs path resolution against an internal blocklist.

### Default Blocked System Paths
| Category | Targeted Path (Normalized) | Rationale |
| :--- | :--- | :--- |
| **Credentials** | `~/.ssh`, `~/.aws`, `~/.kube` | Prevent SSH/Cloud credential theft |
| **Secrets** | `~/.env`, `~/.bashrc`, `~/.zshrc` | Prevent environment variable leakage |
| **OS Core** | `C:\Windows\System32` | Prevent OS corruption or hijacking |
| **Browsers** | `~/.../Chrome/User Data` | Prevent browser cookie/login theft |

### Extension Blocklist
The agent is prohibited from creating or executing the following extensions:
`{ ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".wsf", ".scr", ".dll", ".sys", ".msi", ".reg", ".com" }`

## 🎟️ 3. Capability Token Lifecycle
Authentication for tools is managed via stateless, time-bound tokens.

1.  **Minting**: `CapabilityTokenSystem.mint_token(capability, target_resource, ttl)`
2.  **Verification**: 
    - Is `revoked == false`?
    - Is `time.now() < expires_at`?
    - Does `capability_name` match the request?
    - Does `target_resource` match or is it `*`?
3.  **Purging**: Automatic cleanup of expired tokens every `N` operations to prevent memory leaks.

## ⚖️ 4. Risk-Based Interception Algorithm
The `ApprovalSystem` determines if an action requires user consent based on a calculated threshold.

```python
def check_approval(tool_risk: str, autonomy_level: str) -> bool:
    # Granular logic matrix
    if autonomy_level == "RESTRICTED":
        return True # Always prompt
    if tool_risk == "CRITICAL":
            return True # Never bypass
    if tool_risk == "HIGH" and autonomy_level != "FULL":
            return True # Prompt unless Full
    return False # Auto-execute
```

---

> [!CAUTION]
> Modifying `DLPPattern` tiers from `HIGH` to `MEDIUM` without equivalent UI warnings is a security violation and is flagged in the observability logs.
