"""
CLI Agent Bootstrapper (Task 20/21 Integration MVP)

A headless terminal harness to run the Personal Cognitive Agent (PCA) safely.
Initializes the core logic modules without invoking the heavy PyWebview/FastAPI frontend.
"""

import sys
if sys.stdout and getattr(sys.stdout, 'encoding', '') != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
        
import os
from dotenv import load_dotenv

# Load keys before anything else
load_dotenv()

from core.model_router import ModelRouter, ModelTier
from core.prompt_manager import PromptManager
from core.context_manager import ContextManager
from core.orchestrator import Orchestrator
from memory.memory_system import MemorySystem
from tools.registry import ToolRegistry
from tools.tool_executor import ToolSandboxExecutor
from events.event_bus import EventBus

# Import our implemented tools
from tools.core.file_manager import FileManagerTool
from tools.core.python_executor import PythonExecutorTool
from tools.core.api_caller import ApiCallerTool
from tools.core.database_tool import DatabaseQueryTool
from tools.core.obsidian_tool import ObsidianTool
from tools.core.rag_search_tool import RagSearchTool
from tools.core.browser_agent_tool import BrowserAgentTool

# Import Automation
from automation.task_queue import TaskQueue
from automation.scheduler import AutomationScheduler
from tools.core.automation_tool import AutomationTool

# Import Cognitive Maintenance
from cognitive.maintenance import CognitiveMaintenanceEngine
from cognitive.plan_library import PlanLibrary

def initialize_agent() -> Orchestrator:
    print("Booting Personal Cognitive Agent (Headless Mode ? Phase 9B)...")
    
    from observability import initialize_logging
    initialize_logging()
    
    # 1. Base Logic
    from events import initialize_event_bus
    event_bus = initialize_event_bus()
    
    # Phase 11: Alert Router ? push FLASH/PRIORITY events to OS
    try:
        from events.alert_router import AlertRouter
        alert_router = AlertRouter(event_bus)
    except Exception as e:
        print(f"?? Failed to init AlertRouter: {e}")
    
    # Phase 9A: Token Quota + Hardened Router
    from core.token_quota import TokenQuota
    from core.context_compactor import ContextCompactor
    from core.session_checkpoint import SessionCheckpoint
    
    # Phase 9B: Import power features
    from core.slash_commands import SlashCommandRouter
    from tools.toolset_distributor import ToolsetDistributor
    from automation.cron_manager import CronManager
    from security.file_access_guard import FileAccessGuard
    from core.system_mode_manager import SystemModeManager
    
    token_quota = TokenQuota(daily_limit=500_000, session_limit=100_000, cloud_daily_limit=200_000)
    router = ModelRouter(token_quota=token_quota)
    
    prompt_manager = PromptManager()
    context_manager = ContextManager(max_tokens=6000)
    
    # 2. Memory & Cognition
    memory_sys = MemorySystem()
    plan_library = PlanLibrary(memory_sys)
    maintenance_engine = CognitiveMaintenanceEngine(memory_sys, router, ttl_days=7)
    
    # Phase 12: TELOS Framework (Cognitive Alignment)
    try:
        from cognitive.telos_framework import TelosFramework
        telos_framework = TelosFramework()
    except Exception as e:
        print(f"?? Failed to init TelosFramework: {e}")
        telos_framework = None
    
    # Phase 9A: Context Compactor + Session Checkpoint
    compactor = ContextCompactor(max_context_tokens=6000, local_llm_client=router.local_client)
    checkpoint = SessionCheckpoint()
    mode_manager = SystemModeManager()
    
    # 3. Execution & Security
    from security.approval_system import ApprovalSystem, AutonomyLevel
    
    # We default the system to MODERATE autonomy. 
    # Trivial jobs are auto-accepted. Dangerous files modifications or logic bounds are prompted.
    approval_system = ApprovalSystem(autonomy_level=AutonomyLevel.MODERATE)
    
    registry = ToolRegistry()
    executor = ToolSandboxExecutor(registry=registry, approval_system=approval_system, mode_manager=mode_manager)
    
    # Phase 11: MCP Bridge Manager
    try:
        from tools.mcp_client import MCPBridgeManager
        mcp_manager = MCPBridgeManager(registry)
        import json
        import os
        mcp_config = "Stuart-AI/config/mcp_servers.json" if os.path.exists("Stuart-AI/config/mcp_servers.json") else "config/mcp_servers.json"
        if os.path.exists(mcp_config):
            with open(mcp_config, "r") as f:
                mcp_data = json.load(f)
            for name, conf in mcp_data.get("mcpServers", {}).items():
                if conf.get("enabled"):
                    cmd = [conf["command"]] + conf.get("args", [])
                    mcp_manager.connect_server(name, cmd)
    except Exception as e:
        print(f"?? Failed to init MCPBridgeManager: {e}")

    # Register core tools
    registry.register_tool(FileManagerTool(sandbox_dir="Stuart-AI/data/sandbox/"))
    registry.register_tool(PythonExecutorTool())
    registry.register_tool(ApiCallerTool())
    
    # Add Knowledge Hooks
    registry.register_tool(DatabaseQueryTool())
    registry.register_tool(ObsidianTool(vault_path="Stuart-AI/data/Agent_Vault/"))
    registry.register_tool(RagSearchTool())
    registry.register_tool(BrowserAgentTool())
    
    # Phase 9B: Toolset Distributor ? filter tools per task type (token savings)
    toolset_distributor = ToolsetDistributor(registry=registry)
    
    # Phase 9B: File Access Guard ? block dangerous system paths
    file_access_guard = FileAccessGuard()

    # 4. Background Automation & Maintenance Hooks
    task_queue = TaskQueue(orchestrator_factory=None, max_workers=2)
    scheduler = AutomationScheduler(task_queue.push_background_task)
    
    # Phase 9B: Cron Manager ? proactive scheduled routines
    cron_manager = CronManager(scheduler=scheduler)
    cron_manager.load_persisted()
    
    # Phase 10: RAG & Second Brain - Auto Consolidator
    from memory.flat_file_memory import AutoConsolidator
    auto_consolidator = AutoConsolidator()  # Orchestrator injected later

    # Register the automatic GC distillation cron to run every night at 2 AM
    import schedule
    schedule.every().day.at("02:00").do(maintenance_engine.run_distillation)
    
    # Register purely background memory consolidation at 23:59
    schedule.every().day.at("23:59").do(auto_consolidator.run_consolidation)
    
    scheduler.start()
    
    # Add Automation Hooks
    registry.register_tool(AutomationTool(scheduler, task_queue))
    
    # Phase 9B: Slash Command Router ? intercept /commands
    slash_router = SlashCommandRouter()

    main_orchestrator = Orchestrator(
        event_bus=event_bus,
        memory=memory_sys,
        router=router,
        prompt_manager=prompt_manager,
        executor=executor,
        context_manager=context_manager,
        plan_library=plan_library,
        compactor=compactor,
        checkpoint=checkpoint,
        slash_router=slash_router,
        toolset_distributor=toolset_distributor,
        telos_framework=telos_framework,
        max_reasoning_steps=8
    )

    # Post-init injection for auto consolidator
    auto_consolidator.orchestrator = main_orchestrator

    # Inject runtime context into the slash router
    import time as _time
    
    # Phase 13: Tracing System
    from observability.tracing_system import initialize_tracing
    tracing = initialize_tracing()
    
    # Phase 13: Skills Marketplace
    try:
        from core.skills_marketplace import SkillsMarketplace
        skills_marketplace = SkillsMarketplace()
    except Exception as e:
        print(f"?? Failed to init SkillsMarketplace: {e}")
        skills_marketplace = None
    
    slash_router.set_context(
        orchestrator=main_orchestrator,
        router=router,
        approval_system=approval_system,
        cron_manager=cron_manager,
        plan_library=plan_library,
        memory=memory_sys,
        token_quota=token_quota,
        telos=telos_framework,
        tracing=tracing,
        skills_marketplace=skills_marketplace,
        boot_time=_time.time(),
    )

    # Phase 11: Plugin Manager ? load external tools & commands
    try:
        from core.plugin_manager import PluginManager
        plugin_manager = PluginManager(
            tool_registry=registry,
            event_bus=event_bus,
            slash_router=slash_router
        )
        plugin_manager.load_all()
    except Exception as e:
        print(f"?? Failed to load plugins: {e}")
        
    return main_orchestrator


def run_cli_loop():
    try:
        agent = initialize_agent()
        print("\n=============================================")
        print(" Stuart Agent Online. Type 'exit' to quit.")
        print("=============================================\n")
        
        while True:
            # Basic prompt
            try:
                user_msg = input("\n[YOU]: ").strip()
            except (KeyboardInterrupt, EOFError):
                break
                
            if user_msg.lower() in ['exit', 'quit']:
                print("Shutting down Agent.")
                break
                
            if not user_msg:
                continue
                
            print("\n[STUART]: Thinking...")
            response = agent.process_user_message(user_msg)
            
            print(f"\n[STUART]: {response}")
            
    except Exception as e:
        print(f"\n[CRITICAL FAILURE] Agent crashed: {e}")


if __name__ == "__main__":
    run_cli_loop()
