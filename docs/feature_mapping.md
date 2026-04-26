# Exhaustive Feature Mapping: 12 Agents vs Stuart-PCA

## Agents Analyzed

| # | Project | ⭐ Stars | Language | Focus |
|---|---------|---------|----------|-------|
| 1 | **OpenClaw** | 359K | TypeScript | The "OS" — Skills, Memory Plugins, Multi-channel, MCP |
| 2 | **Hermes Agent** | ~10K | Python | Tool-use, RL training, Trajectory Compression |
| 3 | **ZeroClaw** | 30K | Rust | Ultra-lightweight, Secure-by-default, Edge-ready |
| 4 | **Nanobot** (HKUDS) | 40K | Python | Minimalist, Flat-file memory, Auto-consolidation |
| 5 | **Khoj** | 34K | Python | Second brain, RAG, Scheduling, Deep Research |
| 6 | **CheetahClaws** | 565 | Python | Circuit Breaker, Quota, Checkpointing |
| 7 | **QwenPaw** (AgentScope) | 15.5K | Python | Multi-agent, Skills, Security Guards |
| 8 | **Crucix** | 8.8K | JavaScript | OSINT, Data Aggregation, 3D Globe, Alerting |
| 9 | **DeepChat** | 5.7K | TypeScript | Electron desktop, MCP/ACP, Harness Design |
| 10 | **Manifest** | 4.4K | TypeScript | Smart Model Routing, Cost Tracking |
| 11 | **OpenDAN** | 2K | Python | Personal AI OS, Multi-Agent, IoT |
| 12 | **Personal AI Infra** (Miessler) | 11.5K | TypeScript | Human Augmentation, TELOS Framework |

---

## Feature Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | **Already Implemented** in Stuart-PCA |
| 🔜 | **Planned / Partially Done** — on our roadmap or partially built |
| 🆕 | **Unique to Adopt** — not yet considered, high-value feature to incorporate |
| ❌ | Not applicable / out of scope |

---

## 1. Core Agent Loop & Orchestration

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 1 | ReAct (Reason-Act) Loop | All agents | ✅ | `core/orchestrator.py` |
| 2 | Dynamic max reasoning steps | Hermes, CheetahClaws | ✅ | Configurable `max_reasoning_steps` |
| 3 | Plan decomposition & execution | Hermes, QwenPaw | 🔜 | `PlanLibrary` exists but needs persistence |
| 4 | **Plan Persistence across sessions** | Hermes (`.plans/`) | ✅ | `cognitive/plan_library.py` — disk-persisted plans |
| 5 | **Parallel sub-agent spawning** | Nanobot, CheetahClaws, QwenPaw | 🆕 | Spawn child agents for parallel subtasks |
| 6 | **Batch runner / multi-task execution** | Hermes (`batch_runner.py`) | 🆕 | Run multiple agent instances on different tasks simultaneously |
| 7 | **Supervisor-worker multi-agent** | QwenPaw (AgentScope), OpenDAN | 🆕 | A "supervisor" agent that delegates and coordinates "worker" agents |
| 8 | **Agent-Oriented Programming (AOP)** | QwenPaw (AgentScope) | 🆕 | Treat agents as first-class objects, not just LLM wrappers |
| 9 | **Self-evolving skill engine** | HKUDS OpenSpace | 🆕 | Capture, reuse, and share patterns from completed tasks |
| 10 | **Verifiable iteration / "Permission to fail"** | Personal AI Infra | 🆕 | Agent reviews its own work, upgrades its own processes |

---

## 2. LLM Provider Management

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 11 | Dynamic Model Router (Local/Cloud) | CheetahClaws, Hermes | ✅ | `core/model_router.py` — complexity-based dispatch |
| 12 | Circuit Breaker (per-provider) | CheetahClaws | ✅ | `core/circuit_breaker.py` — CLOSED/OPEN/HALF_OPEN |
| 13 | Token Quota Manager | CheetahClaws | ✅ | `core/token_quota.py` — daily+session+cloud limits |
| 14 | Smart failover (Ollama→Cloud) | CheetahClaws, Manifest | ✅ | In `model_router.py`, budget-gated failover |
| 15 | **4-tier complexity routing** | Manifest | 🆕 | Simple→Standard→Complex→Reasoning tiers with per-tier model assignment |
| 16 | **Cost-per-request tracking (USD)** | Manifest | 🔜 | `TokenQuota` has basic tracking, but no per-request cost breakdown |
| 17 | **Provider-agnostic via LiteLLM** | Nanobot | 🆕 | Unified interface to 20+ LLM providers via single library |
| 18 | **Model warmup / pre-loading** | ZeroClaw | 🆕 | Pre-load model weights at boot to eliminate cold-start latency |
| 19 | **Real-time cost dashboard (frontend)** | Manifest | 🔜 | `/health` endpoint exists but no frontend visualization |
| 20 | **Budget alerts (80% warning, hard stop)** | Manifest, CheetahClaws | ✅ | In `token_quota.py` |

---

## 3. Context & Memory Management

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 21 | Context window management (hard trim) | All agents | ✅ | `core/context_manager.py` |
| 22 | Context Compaction (summarize old turns) | Hermes, CheetahClaws | ✅ | `core/context_compactor.py` |
| 23 | Short-term memory (conversation) | All agents | ✅ | In Orchestrator state |
| 24 | Long-term memory (persistent store) | Khoj, OpenClaw | ✅ | `memory/long_term.py` |
| 25 | Episodic memory (experience recall) | OpenClaw, OpenDAN | 🔜 | `MemorySystem` exists, episodic layer partial |
| 26 | **Flat-file memory (HISTORY.md + MEMORY.md)** | Nanobot | 🆕 | Human-readable, auditable, zero-dependency memory. No vector DB needed |
| 27 | **Auto-consolidation** | Nanobot | 🆕 | Automatically extract long-term facts from conversations into a MEMORY.md |
| 28 | **Plugin-slot memory architecture** | OpenClaw | 🆕 | Swap memory backends (SQLite, PostgreSQL, vector stores) via plugin |
| 29 | **Knowledge graph memory** | OpenDAN, Khoj | 🆕 | Build and query a graph of entities and relationships |
| 30 | **RAG with personal documents** | Khoj | 🆕 | Index PDFs, Markdown, Word, Notion, GitHub repos for retrieval |
| 31 | **Semantic search over memory** | Khoj, QwenPaw | ✅ | Vector-based similarity search via KnowledgeManager |
| 32 | **Cross-session memory persistence** | Nanobot, OpenClaw | 🔜 | Memory survives agent restarts (partial via checkpoint) |
| 33 | **Cognitive maintenance (TTL pruning)** | Internal | ✅ | `CognitiveMaintenanceEngine` with TTL-based cleanup |

---

## 4. Tool System & Execution

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 34 | Tool Registry | All agents | ✅ | `tools/tool_registry.py` |
| 35 | Sandboxed tool execution | OpenClaw, QwenPaw | ✅ | `ToolSandboxExecutor` with approval gates |
| 36 | **Structured tool schemas (YAML/JSON)** | ZeroClaw, Nanobot | 🆕 | Machine-readable tool descriptions with Pydantic validation |
| 37 | **Dynamic toolset distributions** | Hermes (`toolset_distributions.py`) | 🆕 | Load different tool sets per task type (coding→coding tools, research→search tools) |
| 38 | **Tool Guard (dangerous command intercept)** | QwenPaw | 🔜 | Partially covered by `ApprovalSystem`, but no dedicated command blocklist |
| 39 | **File Access Guard** | QwenPaw | ✅ | `security/file_access_guard.py` — path blocklisting |
| 40 | **DLP Engine (Data Loss Prevention)** | Internal | ✅ | `security/dlp_engine.py` — sensitive data redaction |
| 41 | **Pre/post-execution hooks** | Nanobot, OpenClaw | 🆕 | Security hooks before and after each tool execution |
| 42 | **MCP (Model Context Protocol) support** | OpenClaw, DeepChat, Nanobot | 🆕 | Connect to the MCP ecosystem for expanded tool capabilities |
| 43 | **ACP (Agentic Protocol) support** | DeepChat | 🆕 | Agent-to-agent communication protocol |
| 44 | **Environment sandboxing (Docker/VM)** | Hermes (`environments/`), OpenClaw | 🆕 | Isolated execution contexts per task type |

---

## 5. Security & Permissions

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 45 | Human-in-the-Loop (HIL) | All agents | ✅ | `security/approval_system.py` |
| 46 | Dynamic autonomy levels (tunable) | Internal **UNIQUE** | ✅ | UI slider to adjust autonomy in real-time |
| 47 | **Capability tokens** | OpenClaw | ✅ | `security/capability_tokens.py` — time-bounded permissions |
| 48 | **Trust levels** | OpenClaw | 🆕 | Graduated trust (untrusted→low→high→system) per source |
| 49 | **Permission manifests for plugins** | OpenClaw | 🆕 | Each plugin declares required permissions upfront |
| 50 | **DM pairing / secure connection auth** | ZeroClaw, OpenClaw | 🆕 | Require pairing codes for new connections |
| 51 | **API key encryption at rest** | ZeroClaw | 🆕 | Encrypt sensitive data in config files |
| 52 | **Command allowlisting** | ZeroClaw | 🆕 | Only explicitly permitted commands can be executed |
| 53 | **Security audit plugin** | OpenClaw (`SecureClaw`) | 🆕 | Runtime behavior monitoring and config audit |
| 54 | **Fuzz testing for tool executors** | ZeroClaw (`fuzz/`) | 🆕 | Random input testing to find tool vulnerabilities |
| 55 | **Cybersecurity defensive monitoring** | Personal AI Infra | 🆕 | Always-on monitoring for AI-accelerated threats |

---

## 6. Scheduling & Automation

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 56 | Task queue (background jobs) | Internal | ✅ | `automation/task_queue.py` |
| 57 | **Cron/scheduled routines** | Hermes, Nanobot, Khoj | ✅ | `automation/cron_manager.py` — disk-persisted scheduling |
| 58 | **Scheduled automations with inbox delivery** | Khoj | 🆕 | Run jobs on schedule, deliver results to email/app inbox |
| 59 | **Recurring task templates** | Hermes, Khoj | 🆕 | Pre-defined templates for common recurring jobs |
| 60 | **Periodic health/status checks** | CheetahClaws (`health.py`) | 🔜 | `/health` endpoint exists, but no periodic self-check |

---

## 7. User Interface & UX

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 61 | **Stealth desktop overlay (Alt+Z)** | **STUART UNIQUE** | ✅ | PyWebview window, process cloaking, Alt+Z toggle |
| 62 | **Interview Coach mode** | **STUART UNIQUE** | ✅ | Dual-mode: interview assistant + general agent |
| 63 | **Slash command parser** | OpenClaw, Hermes | 🔜 | `/search`, `/clear`, `/autonomy`, `/status` — planned |
| 64 | **Quick Actions / speed dial** | Internal design | 🔜 | One-key macros from overlay — planned |
| 65 | **Web dashboard** | OpenClaw, ZeroClaw, CheetahClaws | 🔜 | Basic web UI exists, needs monitoring dashboard |
| 66 | **Terminal UI (TUI)** | Hermes (`tui_gateway/`) | ✅ | `cli_agent.py` provides headless CLI |
| 67 | **3D data visualization (Globe)** | Crucix | 🆕 | WebGL-powered 3D globe for data display |
| 68 | **Native desktop apps** | OpenClaw (`apps/`), DeepChat | 🆕 | Standalone macOS/Windows/Linux apps |
| 69 | **Browser extension** | OpenClaw (`extensions/`) | 🆕 | Chrome/Firefox extension for in-browser agent access |
| 70 | **Mobile app** | OpenClaw, Khoj | 🆕 | iOS/Android companion app |
| 71 | **Chain-of-thought visibility** | Nanobot | 🔜 | Show reasoning steps to user in real-time |

---

## 8. Multi-Channel & Communication

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 72 | Desktop overlay channel | **STUART UNIQUE** | ✅ | The stealth PyWebview overlay |
| 73 | CLI channel | Internal | ✅ | `cli_agent.py` |
| 74 | REST API channel | Internal | ✅ | `api/agent_api.py` |
| 75 | **WhatsApp channel** | OpenClaw, Nanobot, Secure-OC | 🆕 | Agent accessible via WhatsApp messages |
| 76 | **Telegram channel** | Nanobot, Crucix, OpenClaw | 🆕 | Agent accessible via Telegram bot |
| 77 | **Discord channel** | OpenClaw, ZeroClaw | 🆕 | Agent accessible in Discord servers |
| 78 | **Slack channel** | OpenClaw, ZeroClaw | 🆕 | Agent accessible in Slack workspace |
| 79 | **Email channel** | Nanobot, Khoj | 🆕 | Agent processes and responds to emails |
| 80 | **Cross-platform memory** | Secure-OC | 🆕 | Ask on WhatsApp, continue on Telegram — shared context |
| 81 | **Multi-tier alert system** | Crucix (FLASH/PRIORITY/ROUTINE) | 🆕 | Alert routing by severity to different channels |

---

## 9. Voice & Multimodal

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 82 | Speech-to-Text (STT) | Internal (Deepgram) | ✅ | Deepgram integration exists |
| 83 | **Text-to-Speech (TTS)** | QwenPaw, CheetahClaws | 🔜 | STT exists but TTS not yet wired |
| 84 | **Voice I/O in agent mode** | CheetahClaws (`voice/`) | 🔜 | Planned but not built |
| 85 | **Video processing** | CheetahClaws (`video/`) | 🆕 | Agent can process and analyze video input |
| 86 | **Image generation** | OpenDAN (Stable Diffusion) | 🆕 | Generate images as part of agent responses |

---

## 10. Knowledge & Research

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 87 | **Deep research mode** | Khoj | 🆕 | Multi-step web research with source synthesis |
| 88 | **Personal document indexing (RAG)** | Khoj | ✅ | Index and query user's Obsidian vault and PDFs |
| 89 | **Obsidian integration** | Khoj | ✅ | Sync with Obsidian vaults for knowledge management |
| 90 | **Google Drive / Notion sync** | Khoj | 🆕 | Pull data from cloud productivity tools |
| 91 | **OSINT data aggregation** | Crucix | 🆕 | Pull from 27+ global data sources every 15 min |
| 92 | **AI-powered signal correlation** | Crucix | 🆕 | Cross-reference conflict events with market data |
| 93 | **News digest generation** | QwenPaw, Crucix | 🆕 | Daily curated news/intel summaries |

---

## 11. Reliability & Crash Recovery

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 94 | Session Checkpointing | CheetahClaws | ✅ | `core/session_checkpoint.py` |
| 95 | Resume from checkpoint | CheetahClaws | ✅ | `load_latest()` in checkpoint module |
| 96 | **Durable execution (exactly-once)** | ZeroClaw | 🆕 | Guarantee each tool runs exactly once, even across crashes |
| 97 | **Checkpoint pruning** | Internal | ✅ | Keeps last 10 checkpoints |
| 98 | **Health monitoring dashboard** | CheetahClaws, ZeroClaw | 🔜 | `/health` API exists, frontend needed |

---

## 12. Observability & Monitoring

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 99 | Event bus (pub/sub) | Internal | ✅ | `events/event_bus.py` |
| 100 | Health API endpoint | Internal | ✅ | `GET /api/agent/health` |
| 101 | **OpenTelemetry (OTel) tracing** | QwenPaw (AgentScope) | 🆕 | Full-stack observability with distributed traces |
| 102 | **Token usage analytics** | Manifest | 🔜 | Basic tracking exists, no trend analysis |
| 103 | **LLM latency tracking** | Manifest | 🆕 | Track response times per provider per request |
| 104 | **Error rate dashboards** | ZeroClaw | 🆕 | Visualize error rates, circuit breaker triggers |
| 105 | **Agent decision logging** | Hermes | 🔜 | Partial via event bus, no structured log export |

---

## 13. Deployment & DevOps

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 106 | Local desktop deployment | Internal | ✅ | `run.bat`, `main.py` |
| 107 | **Docker deployment** | Khoj, OpenDAN, ZeroClaw | 🆕 | One-command Docker setup |
| 108 | **Single static binary** | ZeroClaw (~3.4MB) | ❌ | Not applicable (Python), but could PyInstaller bundle |
| 109 | **Edge/IoT deployment** | ZeroClaw (`firmware/`) | 🆕 | Run on Raspberry Pi or home server |
| 110 | **Kubernetes deployment** | QwenPaw | ❌ | Enterprise-grade, overkill for personal agent |

---

## 14. Ecosystem & Extensibility

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 111 | **Skills marketplace (ClawHub)** | OpenClaw (13K+ skills), ZeroClaw | 🆕 | Community skill publishing & consumption |
| 112 | **Plugin system** | OpenClaw, CheetahClaws, QwenPaw | 🆕 | Hot-pluggable capability modules |
| 113 | **SKILL.md skill definitions** | OpenClaw | 🆕 | Natural-language skill specs the AI interprets at runtime |
| 114 | **Skill import from other ecosystems** | OpenClaw (Claude, Codex bundles) | 🆕 | Map skills from other agent frameworks |
| 115 | **500+ app integrations** | Secure-OC (via Composio) | 🆕 | Pre-built integrations with SaaS tools |

---

## 15. Unique-to-Stuart (Our Competitive Moat)

| # | Feature | Present In Others? | Stuart Status | Notes |
|---|---------|-------------------|-------------|-------|
| 116 | 🥷 Stealth desktop overlay | **NO** | ✅ | PyWebview + Alt+Z, process cloaking, hidden from task manager |
| 117 | 🔒 Dynamic HIL with UI slider | **NO** (others have fixed levels) | ✅ | Real-time autonomy adjustment |
| 118 | 🧠 Dual-LLM complexity dispatch | Partial (Manifest has 4-tier) | ✅ | Auto-route trivial→Ollama, complex→Cloud |
| 119 | 📋 Interview Coach + Agent dual-mode | **NO** | ✅ | Same overlay = interview helper AND general agent |
| 120 | 🔮 Window anti-detection (stealth) | **NO** | ✅ | Class name randomization, title spoofing |

---

## 16. Purpose & Philosophy

| # | Feature | Source Agent(s) | Stuart Status | Notes |
|---|---------|----------------|-------------|-------|
| 121 | **TELOS framework (purpose alignment)** | Personal AI Infra | 🆕 | Define purpose/mission/goals so agent actions are always aligned |
| 122 | **"Human 3.0" augmentation mindset** | Personal AI Infra | 🆕 | Agent exists to amplify human capability, not replace |
| 123 | **"One-Person Company" enablement** | Personal AI Infra | 🆕 | Design the agent to handle everything a full team would |

---

## Summary Statistics

| Status | Count | % |
|--------|-------|---|
| ✅ **Already Implemented** | 33 | 27% |
| 🔜 **Planned / Partial** | 18 | 15% |
| 🆕 **Unique to Adopt** | 68 | 55% |
| ❌ **Not Applicable** | 4 | 3% |
| **TOTAL unique features** | **123** | |

---

## Priority Adoption Roadmap

### 🔴 Tier 1 — Must-Have (Next 2 weeks)

| Feature | Source | Why |
|---------|--------|-----|
| Cron/Scheduled Routines | Hermes, Khoj | "Every morning at 8am, summarize X" is the #1 most requested personal agent feature |
| Slash Commands | OpenClaw, Hermes | Power-user UX for agent control |
| Plan Persistence | Hermes | Resume complex multi-step tasks across sessions |
| Dynamic Toolset Distributions | Hermes | Give coding tasks coding tools, research tasks search tools — massive token savings |
| RAG/Personal Document Indexing | Khoj | Let agent search user's files — transforms from chatbot to true personal assistant |

### 🟡 Tier 2 — High-Value (Next 1-2 months)

| Feature | Source | Why |
|---------|--------|-----|
| MCP Support | OpenClaw, Nanobot, DeepChat | Industry-standard protocol — expand tool ecosystem infinitely |
| Flat-file Memory (MEMORY.md) | Nanobot | Human-readable persistent memory with zero dependencies |
| Auto-Consolidation | Nanobot | Automatically extract facts from conversations |
| Plugin System | OpenClaw, QwenPaw | Allow users to extend agent without modifying core |
| Docker Deployment | Khoj, ZeroClaw | One-command setup for self-hosting |
| File Access Guard | QwenPaw | Block agent from accessing ~/.ssh, /etc, etc. |
| Multi-tier Alerting | Crucix | Route alerts by severity to appropriate channels |

### 🟢 Tier 3 — Differentiators (Next 3-6 months)

| Feature | Source | Why |
|---------|--------|-----|
| TELOS Framework (purpose alignment) | Personal AI Infra | The agent should be aligned with user's life goals |
| Deep Research Mode | Khoj | Multi-step web research with synthesis |
| Parallel Sub-agent Spawning | Nanobot, QwenPaw | Speed up complex tasks via parallelism |
| OSINT Data Aggregation | Crucix | "Bloomberg Terminal" for personal intelligence |
| Skills Marketplace | OpenClaw, ZeroClaw | Community ecosystem — the real moat |
| Telegram/WhatsApp Channels | OpenClaw, Nanobot | Access agent from anywhere, not just desktop |
| OTel Observability | QwenPaw | Enterprise-grade tracing and debugging |
| News Digest Generation | QwenPaw, Crucix | Daily automated intelligence briefings |

---

> [!IMPORTANT]
> **The 5 features that would set us apart the most:**
> 1. **Cron Scheduler** — Turns agent from reactive to proactive
> 2. **RAG/Document Indexing** — Transforms chatbot into true second brain
> 3. **MCP Support** — Unlocks 13,000+ community skills
> 4. **TELOS Framework** — Aligns agent with user's life purpose (nobody else does this well)
> 5. **OSINT Data Aggregation** — "Personal Bloomberg Terminal" is a unique killer feature
