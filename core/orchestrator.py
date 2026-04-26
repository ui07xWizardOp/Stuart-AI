"""
Agent Orchestrator (Phase 9B — Power Features)

The central brain of the ReAct (Reason and Action) loop.
Merges memory, models, tools, and security boundaries into a conscious workflow cycle.

Phase 9A additions:
  - Context Compaction: compress older turns before each LLM call
  - Session Checkpointing: save agent state after each ReAct cycle step

Phase 9B additions:
  - Slash Command Router: intercept /commands before ReAct loop
  - Toolset Distributor: surface only relevant tools per task type (token savings)
"""

from typing import Dict, Any, List, Optional
import json

from observability import get_logging_system
from core.model_router import ModelRouter, ModelTier
from core.prompt_manager import PromptManager
from core.context_manager import ContextManager
from core.context_compactor import ContextCompactor
from core.session_checkpoint import SessionCheckpoint
from core.slash_commands import SlashCommandRouter
from memory.memory_system import MemorySystem
from memory.short_term import MemoryRole
from tools.tool_executor import ToolSandboxExecutor
from tools.toolset_distributor import ToolsetDistributor
from events.event_bus import EventBus, Event
from cognitive.plan_library import PlanLibrary
from cognitive.telos_framework import TelosFramework

class Orchestrator:
    """The central brain of the ReAct (Reason and Action) loop.

    Merges memory, models, tools, and security boundaries into a conscious workflow cycle.
    Handles intent classification, state persistence, and loop circuit breakers.

    Attributes:
        event_bus (EventBus): Global system event dispatcher.
        memory (MemorySystem): Access to short-term and long-term memory.
        router (ModelRouter): Logic for failover and complexity-based routing.
        prompt_manager (PromptManager): High-level prompt template renderer.
        executor (ToolSandboxExecutor): Handler for safe tool execution.
        context_manager (ContextManager): Context window assembly and trimming.
        plan_library (Optional[PlanLibrary]): Cross-session learning and pattern reuse.
        compactor (Optional[ContextCompactor]): Logic for compressing conversation turns.
        checkpoint (Optional[SessionCheckpoint]): Persistence layer for active states.
        slash_router (Optional[SlashCommandRouter]): Interceptor for local CLI commands.
        toolset_distributor (Optional[ToolsetDistributor]): Intent-based tool filtering.
        telos_framework (Optional[TelosFramework]): Ethical alignment and framework injection.
        max_reasoning_steps (int): Safety limit for the ReAct loop turns.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        memory: MemorySystem,
        router: ModelRouter,
        prompt_manager: PromptManager,
        executor: ToolSandboxExecutor,
        context_manager: ContextManager,
        plan_library: PlanLibrary = None,
        compactor: ContextCompactor = None,
        checkpoint: SessionCheckpoint = None,
        slash_router: SlashCommandRouter = None,
        toolset_distributor: ToolsetDistributor = None,
        telos_framework: Optional[TelosFramework] = None,
        max_reasoning_steps: int = 5
    ):
        """Initializes the Orchestrator with all necessary cognitive and safety sub-systems."""
        self.logger = get_logging_system()
        self.event_bus = event_bus
        self.memory = memory
        self.router = router
        self.prompt_manager = prompt_manager
        self.executor = executor
        self.context_manager = context_manager
        self.plan_library = plan_library
        self.compactor = compactor
        self.checkpoint = checkpoint
        self.slash_router = slash_router
        self.toolset_distributor = toolset_distributor
        self.telos = telos_framework
        self.max_reasoning_steps = max_reasoning_steps
        
        self.logger.info("Agent Orchestrator Booted (Phase 9B — Power Features).")

    def process_user_message(self, text: str) -> str:
        """The principal ReAct loop block.

        Receives user input, fetches contexts, triggers LLM logic, and coordinates 
        multi-step tool cycles until a FINAL_ANSWER is produced.

        Args:
            text (str): The raw input message from the user or automation trigger.

        Returns:
            str: The final agent response or a system error message.

        Notes:
            Phase 9B: Slash commands are intercepted BEFORE the ReAct loop to save tokens.
        """
        # Phase 9B: Intercept slash commands — bypass LLM entirely
        if self.slash_router and self.slash_router.is_slash_command(text):
            self.logger.info(f"Slash command intercepted: {text.split()[0]}")
            return self.slash_router.execute(text)

        # 1. Boot up interactions and commit input to memory
        self.logger.info(f"Orchestrator received user input: {text[:50]}...")
        self.memory.commit_interaction(MemoryRole.USER, text)
        
        # Reset tracker for learning
        self._current_loop_tools = []
        
        # Look up Known Plans (Task 24)
        known_plan_injection = ""
        if self.plan_library:
            plan = self.plan_library.lookup_plan(text)
            if plan:
                known_plan_injection = f"\n<PROVEN_PLAN>\n{plan}\n</PROVEN_PLAN>\n"
        
        # Phase 9B: Get task-specific tools (saves tokens!)
        if self.toolset_distributor:
            schema_array = self.toolset_distributor.get_tools_for_task(text)
        else:
            schema_array = self.executor.registry.list_tools()
        
        # We start the dynamic reasoning loop
        budget = self.max_reasoning_steps
        step = 0
        consecutive_errors = 0
        last_tool_call_signature = None
        
        while step < budget:
            self.logger.debug(f"Starting ReAct loop turn {step+1} (Current Budget: {budget})")
            
            # 2. Assemble State
            raw_entries = self.memory.short_term.get_context_window()
            # Trim boundaries using the ContextManager
            trimmed_entries = self.context_manager.trim_working_memory(raw_entries)
            
            # We convert to a formatted block
            lines = []
            for entry in trimmed_entries:
                role = entry.role.value.upper()
                lines.append(f"<{role}>\n{entry.content}\n</{role}>")
            context_blob = "\n\n".join(lines)
            
            # Use the pre-computed task-specific tool schemas
            tools_json = json.dumps(schema_array, indent=2)
            
            # 3. Generate Prompt using Prompt Manager System
            system_prompt = self.prompt_manager.render_prompt(
                template_name="system_default",
                variables={
                    "os_details": "Windows", # Hardcoded system vars
                    "available_tools": tools_json
                }
            )
            
            # Construct standard ChatGPT/Ollama JSON message array
            telos_injection = self.telos.get_alignment_prompt() if self.telos else ""
            user_content = f"{telos_injection}\n\n{known_plan_injection}\n\n--- WORKING MEMORY ---\n\n{context_blob}\n\n<THOUGHT_REQUIREMENT>\nReason precisely. Either generate a final answer starting with 'FINAL_ANSWER:', or request a tool execution starting with 'TOOL_CALL: {{\"tool\": \"name\", \"action\": \"...\", \"parameters\": {{}}}}'.\n"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
            
            # Phase 9A: Context Compaction — compress older turns before LLM call
            if self.compactor and self.compactor.should_compact(messages):
                messages = self.compactor.compact(messages)
                self.logger.info("🗜️ Context compacted before LLM dispatch.")
            
            try:
                # Dispatcher natively assesses complexity and sends either to Ollama or OpenAI
                response_text = self.router.execute_with_failover(messages)
            except Exception as e:
                err = f"Model execution crushed: {e}"
                self.logger.error(err)
                return f"SYSTEM FAILURE: {err}"
                
            self.memory.commit_interaction(MemoryRole.THOUGHT, response_text)
            
            # 4. Action Execution Parse
            if "FINAL_ANSWER:" in response_text:
                final_answer = response_text.split("FINAL_ANSWER:", 1)[1].strip()
                self.memory.commit_interaction(MemoryRole.AGENT, final_answer)
                
                # Check mapping for plan caching (flawless execution check)
                if consecutive_errors == 0 and self.plan_library and getattr(self, "_current_loop_tools", []):
                    self.plan_library.record_successful_plan(text, self._current_loop_tools)
                self._current_loop_tools = []
                
                return final_answer
                
            elif "TOOL_CALL:" in response_text:
                try:
                    # Very crude parse. LLM must adhere to JSON string right after TOOL_CALL:
                    json_str = response_text.split("TOOL_CALL:", 1)[1].strip()
                    if json_str.startswith("```json"):
                        json_str = json_str[7:]
                    if json_str.endswith("```"):
                        json_str = json_str[:-3]
                        
                    call_def = json.loads(json_str)
                    
                    tool_name = call_def.get("tool")
                    action = call_def.get("action")
                    params = call_def.get("parameters", {})
                    
                    # DYNAMIC: Loop Detection
                    current_signature = f"{tool_name}:{action}:{hash(json.dumps(params, sort_keys=True))}"
                    if current_signature == last_tool_call_signature:
                        warn_msg = f"SYSTEM ABORT: You requested the exact same tool call twice in a row. Force-exiting infinite loop to protect budget."
                        self.logger.error(warn_msg)
                        self.memory.commit_interaction(MemoryRole.SYSTEM, warn_msg)
                        return warn_msg
                        
                    last_tool_call_signature = current_signature
                    
                    self.logger.info(f"Executing Tool Call: {tool_name}.{action}")
                    
                    # Execute Sandbox
                    result = self.executor.execute_tool(tool_name, action, params, context=None)
                    
                    # Track executed tools for PlanLibrary recording
                    if not hasattr(self, "_current_loop_tools"):
                        self._current_loop_tools = []
                    self._current_loop_tools.append({"tool": tool_name, "action": action, "parameters": params})
                    
                    # DYNAMIC: Budget adjusting based on tool success
                    # (Assuming ToolSandboxExecutor returns a ToolResult object with .success)
                    # If it returns a raw string or dict, we infer success based on exceptions
                    success = getattr(result, "success", True)
                    
                    if success:
                        consecutive_errors = 0
                        # Reward progress by slightly extending the budget (cap at 15)
                        if budget < 15:
                            budget += 1 
                    else:
                        consecutive_errors += 1
                        error_str = getattr(result, "error", "Unknown error")
                        self.logger.warning(f"Tool failed: {error_str}")
                        
                        # DYNAMIC: Punish consecutive errors massively
                        if consecutive_errors >= 3:
                            warn_msg = f"SYSTEM ABORT: 3 consecutive tool failures. Aborting task to protect API budget."
                            self.logger.error(warn_msg)
                            self.memory.commit_interaction(MemoryRole.SYSTEM, warn_msg)
                            
                            # Wipe tracked tools since this failed
                            self._current_loop_tools = []
                            return warn_msg
                    
                    # Content formatting
                    if hasattr(result, "output"):
                        result_raw = result.output
                    else:
                        result_raw = result
                        
                    if isinstance(result_raw, str):
                        result_str = self.context_manager.trim_semantic_search_results(result_raw)
                    else:
                        result_str = str(result_raw)
                        
                    obs_str = f"Execution Result from {tool_name}:\n{result_str}"
                    self.memory.commit_interaction(MemoryRole.OBSERVATION, obs_str)
                    
                except Exception as e:
                    consecutive_errors += 1
                    err_msg = f"Failed to execute tool command. Error: {str(e)}\nMake sure output strictly matches 'TOOL_CALL: {{...}}' JSON."
                    self.logger.error(err_msg)
                    self.memory.commit_interaction(MemoryRole.OBSERVATION, err_msg)
                    
            else:
                consecutive_errors += 1
                warn = "System Observation: You failed to prefix your text with FINAL_ANSWER: or TOOL_CALL:. Please retry adhering to the requested format."
                self.memory.commit_interaction(MemoryRole.OBSERVATION, warn)
                
            step += 1
            
            # Phase 9A: Checkpoint state after each cycle step
            self._save_checkpoint(step, budget, text)
                
        # If loop breaks the step bounds
        fail_msg = f"Agent exhausted the max reasoning budget ({budget} loops) without returning a FINAL_ANSWER."
        self.logger.error(fail_msg)
        self.memory.commit_interaction(MemoryRole.SYSTEM, fail_msg)
        self._current_loop_tools = []
        return fail_msg

    def _save_checkpoint(self, step: int, budget: int, original_query: str):
        """Save agent state checkpoint after each ReAct step (Phase 9A)."""
        if not self.checkpoint:
            return
        try:
            state = {
                "step": step,
                "budget": budget,
                "original_query": original_query,
                "tools_executed": getattr(self, "_current_loop_tools", []),
                "memory_entries_count": len(self.memory.short_term.get_context_window()),
            }
            self.checkpoint.save(state)
        except Exception as e:
            self.logger.warning(f"⚠️ Checkpoint save failed (non-fatal): {e}")
