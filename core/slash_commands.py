"""
Slash Command Router (Phase 9B)

Intercepts messages prefixed with '/' and routes them to internal system
actions instead of passing through the LLM. Inspired by OpenClaw and Hermes Agent.

Built-in commands:
  /status     ? Show agent health, uptime, autonomy level
  /model      ? Show current model routing info
  /autonomy   ? Change autonomy level
  /cron       ? Manage scheduled jobs (add/list/remove)
  /clear      ? Clear short-term memory
  /plan       ? List cached proven plans
  /budget     ? Show token quota dashboard
  /tools      ? List registered tools
  /help       ? List all available commands

Extensible: router.register_command("name", handler_fn, "description")
"""

from typing import Dict, Any, Callable, Optional, Tuple
import time

from observability import get_logging_system


class SlashCommandRouter:
    """
    Routes slash-prefixed messages to internal handlers,
    bypassing the LLM entirely for system-level operations.
    """

    def __init__(self):
        self.logger = get_logging_system()
        self._commands: Dict[str, Dict[str, Any]] = {}
        self._context: Dict[str, Any] = {}  # Injected references

        # Register built-in commands
        self._register_builtins()

        self.logger.info(f"SlashCommandRouter initialized with {len(self._commands)} commands (Phase 9B).")

    def set_context(self, **kwargs):
        """
        Inject runtime references needed by command handlers.
        Called during bootstrap to provide orchestrator, router, etc.
        
        Expected keys: orchestrator, router, approval_system, cron_manager,
                       plan_library, memory, token_quota, boot_time
        """
        self._context.update(kwargs)

    def is_slash_command(self, text: str) -> bool:
        """Check if a message is a slash command."""
        return text.strip().startswith("/")

    def execute(self, text: str) -> str:
        """
        Parse and execute a slash command.
        Returns the formatted response string.
        """
        text = text.strip()
        parts = text.split(maxsplit=1)
        cmd_name = parts[0].lower()  # e.g., "/status"
        args_str = parts[1] if len(parts) > 1 else ""

        handler_info = self._commands.get(cmd_name)
        if not handler_info:
            return f"? Unknown command: `{cmd_name}`\nType `/help` to see available commands."

        try:
            return handler_info["handler"](args_str)
        except Exception as e:
            self.logger.error(f"Slash command {cmd_name} failed: {e}")
            return f"? Command `{cmd_name}` failed: {str(e)}"

    def register_command(self, name: str, handler: Callable[[str], str], description: str):
        """Register a custom slash command."""
        if not name.startswith("/"):
            name = "/" + name
        self._commands[name] = {"handler": handler, "description": description}

    # ?? Built-in Command Handlers ??????????????????????????????????????

    def _register_builtins(self):
        """Register all built-in slash commands."""
        builtins = {
            "/status": (self._cmd_status, "Show agent health, uptime, and autonomy level"),
            "/model": (self._cmd_model, "Show current model routing configuration"),
            "/autonomy": (self._cmd_autonomy, "Change autonomy level: /autonomy [restricted|moderate|full]"),
            "/cron": (self._cmd_cron, "Manage cron jobs: /cron [add|list|remove] ..."),
            "/clear": (self._cmd_clear, "Clear short-term memory"),
            "/plan": (self._cmd_plan, "List cached proven plans"),
            "/budget": (self._cmd_budget, "Show token quota and cost dashboard"),
            "/tools": (self._cmd_tools, "List all registered tools"),
            "/index": (self._cmd_index, "Run the Document Indexer on a folder: /index <path>"),
            "/memory": (self._cmd_memory, "Force a flat-file memory consolidation run"),
            "/search": (self._cmd_search, "Directly search the indexed personal documents: /search <query>"),
            "/telos": (self._cmd_telos, "View or update the core cognitive alignment: /telos [update <text>]"),
            "/skills": (self._cmd_skills, "Manage community skills: /skills [list|install|remove] <name>"),
            "/traces": (self._cmd_traces, "Show recent trace/span statistics: /traces [stats|recent]"),
            "/help": (self._cmd_help, "Show this help message"),
        }
        for name, (handler, desc) in builtins.items():
            self._commands[name] = {"handler": handler, "description": desc}

    def _cmd_help(self, args: str) -> str:
        """List all available commands."""
        lines = ["? **Available Slash Commands:**\n"]
        for name, info in sorted(self._commands.items()):
            lines.append(f"  `{name}` ? {info['description']}")
        return "\n".join(lines)

    def _cmd_telos(self, args: str) -> str:
        """View or update TELOS constitutional alignment."""
        telos = self._context.get("telos")
        if not telos:
            return "?? TELOS Framework is not initialized."
            
        if not args:
            return f"? **Current TELOS Alignment**\n\n{telos.current_telos}\n\n*Use `/telos update <new mission>` to change.*"
            
        parts = args.split(maxsplit=1)
        if parts[0].lower() == "update" and len(parts) > 1:
            try:
                telos.update_telos(parts[1])
                return "? **TELOS Alignment Updated.** The agent will now adhere to this new purpose."
            except Exception as e:
                return f"? Failed to update TELOS: {e}"
        
        return "?? Invalid syntax. Use `/telos` to view, or `/telos update <text>` to change."

    def _cmd_skills(self, args: str) -> str:
        """Manage community skill plugins."""
        marketplace = self._context.get("skills_marketplace")
        if not marketplace:
            return "?? Skills Marketplace is not initialized."

        parts = args.strip().split(maxsplit=1)
        action = parts[0].lower() if parts else "list"
        name = parts[1].strip() if len(parts) > 1 else ""

        if action == "list":
            skills = marketplace.list_available()
            if not skills:
                return "? No skills found in the registry."
            lines = ["? **Available Skills:**\n"]
            for s in skills:
                status = "? Installed" if s["installed"] else "?? Available"
                lines.append(f"  `{s['name']}` v{s['version']} ? {s['description']} [{status}]")
            lines.append("\n*Use `/skills install <name>` or `/skills remove <name>`.*")
            return "\n".join(lines)

        elif action == "install":
            if not name:
                return "?? Specify a skill name: `/skills install <name>`"
            return marketplace.install_skill(name)

        elif action == "remove":
            if not name:
                return "?? Specify a skill name: `/skills remove <name>`"
            return marketplace.remove_skill(name)

        return "?? Unknown action. Use `/skills list`, `/skills install <name>`, or `/skills remove <name>`."

    def _cmd_traces(self, args: str) -> str:
        """Show tracing statistics."""
        tracing = self._context.get("tracing")
        if not tracing:
            return "?? Tracing system is not initialized."

        action = args.strip().lower() if args.strip() else "stats"

        if action == "stats":
            stats = tracing.get_tracing_stats()
            return (
                f"? **Tracing Statistics**\n"
                f"  ? Enabled: {stats['enabled']}\n"
                f"  ? Total Spans: {stats['total_spans']}\n"
                f"  ? Finished: {stats['finished_spans']}\n"
                f"  ? Active: {stats['active_spans']}\n"
                f"  ? Traces: {stats['total_traces']}"
            )

        elif action == "recent":
            spans = tracing.query_spans(limit=5)
            if not spans:
                return "No recent spans recorded."
            lines = ["? **Recent Spans (last 5):**\n"]
            for s in spans:
                dur = f"{s.duration_ms:.1f}ms" if s.duration_ms else "running"
                lines.append(f"  `{s.operation_name}` [{s.status}] {dur}")
            return "\n".join(lines)

        return "?? Use `/traces stats` or `/traces recent`."

    def _cmd_status(self, args: str) -> str:
        """Show agent health summary."""
        boot_time = self._context.get("boot_time", 0)
        uptime = time.time() - boot_time if boot_time else 0

        approval = self._context.get("approval_system")
        autonomy = approval.autonomy_level.value if approval else "unknown"

        cron = self._context.get("cron_manager")
        cron_count = len(cron.jobs) if cron else 0

        return (
            f"? **Agent Status**\n"
            f"  ? Status: Online\n"
            f"  ? Uptime: {uptime:.0f}s\n"
            f"  ? Autonomy: {autonomy}\n"
            f"  ? Active Cron Jobs: {cron_count}\n"
        )

    def _cmd_model(self, args: str) -> str:
        """Show model routing info."""
        router = self._context.get("router")
        if not router:
            return "?? Model router not available."

        try:
            status = router.get_status()
            lines = ["? **Model Router Status**\n"]

            # Ollama info
            ollama = status.get("ollama", {})
            lines.append(f"  ? Ollama Circuit: {ollama.get('circuit_state', 'N/A')}")

            # Cloud info
            cloud = status.get("cloud", {})
            lines.append(f"  ? Cloud Circuit: {cloud.get('circuit_state', 'N/A')}")

            # Quota info
            quota = status.get("quota", {})
            lines.append(f"  ? Daily Tokens Used: {quota.get('daily_used', 0):,}")
            lines.append(f"  ? Session Tokens Used: {quota.get('session_used', 0):,}")

            return "\n".join(lines)
        except Exception as e:
            return f"?? Could not fetch router status: {e}"

    def _cmd_autonomy(self, args: str) -> str:
        """Change or display autonomy level."""
        approval = self._context.get("approval_system")
        if not approval:
            return "?? Approval system not available."

        args = args.strip().lower()
        if not args:
            return f"? Current autonomy level: **{approval.autonomy_level.value}**\nUsage: `/autonomy [restricted|moderate|full]`"

        valid = ["restricted", "moderate", "full"]
        if args not in valid:
            return f"? Invalid level: `{args}`. Use one of: {', '.join(valid)}"

        from security.approval_system import AutonomyLevel
        level_map = {
            "restricted": AutonomyLevel.RESTRICTED,
            "moderate": AutonomyLevel.MODERATE,
            "full": AutonomyLevel.FULL,
        }
        approval.set_autonomy(level_map[args])
        return f"? Autonomy level changed to **{args}**"

    def _cmd_cron(self, args: str) -> str:
        """Manage cron jobs."""
        cron = self._context.get("cron_manager")
        if not cron:
            return "?? Cron manager not available."

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        sub_args = parts[1] if len(parts) > 1 else ""

        if sub == "list" or not sub:
            return cron.list_all()

        elif sub == "add":
            # Expected format: /cron add 08:00 Summarize my emails
            add_parts = sub_args.split(maxsplit=1)
            if len(add_parts) < 2:
                return "? Usage: `/cron add <HH:MM> <prompt>`\nExample: `/cron add 08:00 Summarize my emails`"
            time_str, prompt = add_parts
            try:
                job_id = cron.add(time_str, prompt, job_type="daily")
                return f"? Cron job created: `{job_id}` ? Daily @ {time_str}\n? Prompt: \"{prompt}\""
            except Exception as e:
                return f"? Failed to create job: {e}"

        elif sub == "remove":
            job_id = sub_args.strip()
            if not job_id:
                return "? Usage: `/cron remove <job_id>`"
            if cron.remove(job_id):
                return f"? Cron job `{job_id}` removed."
            else:
                return f"? Job `{job_id}` not found."

        else:
            return "? Usage: `/cron [add|list|remove] ...`"

    def _cmd_clear(self, args: str) -> str:
        """Clear short-term memory."""
        memory = self._context.get("memory")
        if not memory:
            return "?? Memory system not available."

        try:
            memory.short_term.clear()
            return "?? Short-term memory cleared."
        except Exception as e:
            return f"? Failed to clear memory: {e}"

    def _cmd_plan(self, args: str) -> str:
        """List proven plans."""
        plan_lib = self._context.get("plan_library")
        if not plan_lib:
            return "?? Plan library not available."

        try:
            plans = plan_lib.list_all_plans()
            if not plans:
                return "? No proven plans cached yet."

            lines = ["? **Saved Plans:**\n"]
            for p in plans:
                lines.append(f"  ? `{p['intent_hash']}` ? \"{p['prompt'][:50]}...\"")
            return "\n".join(lines)
        except Exception as e:
            return f"?? Could not list plans: {e}"

    def _cmd_budget(self, args: str) -> str:
        """Show token quota dashboard."""
        quota = self._context.get("token_quota")
        if not quota:
            return "?? Token quota not available."

        try:
            status = quota.get_status()
            # TokenQuota.get_status() returns nested dicts: session, daily, cloud_daily
            daily = status.get("daily", {})
            session = status.get("session", {})
            cloud = status.get("cloud_daily", {})

            daily_used = daily.get("used", 0)
            daily_limit = daily.get("limit", 0)
            session_used = session.get("used", 0)
            session_limit = session.get("limit", 0)
            cloud_used = cloud.get("used", 0)
            cloud_limit = cloud.get("limit", 0)

            daily_pct = (daily_used / daily_limit * 100) if daily_limit else 0
            session_pct = (session_used / session_limit * 100) if session_limit else 0
            cloud_pct = (cloud_used / cloud_limit * 100) if cloud_limit else 0

            # Progress bar helper
            def bar(pct):
                filled = int(pct / 10)
                return f"[{'?' * filled}{'?' * (10 - filled)}] {pct:.0f}%"

            return (
                f"? **Token Budget Dashboard**\n\n"
                f"  ? Daily:   {bar(daily_pct)}  ({daily_used:,} / {daily_limit:,})\n"
                f"  ? Session: {bar(session_pct)}  ({session_used:,} / {session_limit:,})\n"
                f"  ?? Cloud:   {bar(cloud_pct)}  ({cloud_used:,} / {cloud_limit:,})\n"
                f"  ? Est. Cost: ${cloud.get('estimated_cost_usd', 0):.4f}\n"
            )
        except Exception as e:
            return f"?? Could not fetch budget: {e}"

    def _cmd_tools(self, args: str) -> str:
        """List registered tools."""
        orchestrator = self._context.get("orchestrator")
        if not orchestrator or not hasattr(orchestrator, 'executor'):
            return "?? Tool registry not available."

        try:
            tools = orchestrator.executor.registry.get_all_tools()
            if not tools:
                return "? No tools registered."

            lines = ["? **Registered Tools:**\n"]
            for tool in tools:
                risk = tool.risk_level.value if hasattr(tool.risk_level, 'value') else str(tool.risk_level)
                lines.append(f"  ? `{tool.name}` ({risk}) ? {tool.description[:60]}")
            return "\n".join(lines)
        except Exception as e:
            return f"?? Could not list tools: {e}"

    def _cmd_index(self, args: str) -> str:
        """Run the document indexer on a folder."""
        path = args.strip()
        if not path:
            return "? Usage: `/index <folder_path>`"
            
        try:
            from knowledge.document_indexer import DocumentIndexer
            indexer = DocumentIndexer()
            stats = indexer.index_directory(path)
            return (
                f"? **Indexing Complete:** {path}\n"
                f"  ? Files Processed: {stats.get('files_processed', 0)}\n"
                f"  ? Chunks Created: {stats.get('chunks_created', 0)}\n"
                f"  ? Skipped: {stats.get('files_skipped', 0)}\n"
                f"  ? Errors: {stats.get('errors', 0)}"
            )
        except Exception as e:
            return f"? Indexing failed: {e}"

    def _cmd_memory(self, args: str) -> str:
        """Force a memory consolidation run."""
        orchestrator = self._context.get("orchestrator")
        if not orchestrator:
            return "?? Orchestrator not available for consolidation."
            
        try:
            from memory.flat_file_memory import AutoConsolidator
            consolidator = AutoConsolidator(orchestrator)
            result = consolidator.run_consolidation()
            return result
        except Exception as e:
            return f"? Memory consolidation failed: {e}"

    def _cmd_search(self, args: str) -> str:
        """Directly search the vector DB."""
        query = args.strip()
        if not query:
            return "? Usage: `/search <query>`"
            
        try:
            from knowledge.vectorizer import Vectorizer, TextChunk
            from knowledge.vector_db import VectorDatabase
            
            vec = Vectorizer()
            db = VectorDatabase()
            
            dummy = [TextChunk("query", query, 0, {})]
            vec.calculate_embeddings(dummy)
            
            if not dummy[0].vector:
                return "? Check your OpenAI API Key."
                
            hits = db.semantic_search(dummy[0].vector, limit=5)
            if not hits:
                return "? No matches found."
                
            lines = [f"? **Search Results for:** `{query}`\n"]
            for i, hit in enumerate(hits):
                score = round(hit['score'], 3)
                lines.append(f"? [Score: {score}] {hit.get('document_id')}\n  > {hit.get('text', '')[:100]}...")
                
            return "\n".join(lines)
            
        except Exception as e:
            return f"? Search failed: {e}"
