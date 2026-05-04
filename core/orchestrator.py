"""
Agent Orchestrator (Phase 9B ? Power Features)

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
import platform
from dataclasses import dataclass

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

@dataclass
class ReasoningStepResult:
    """The outcome of a single reasoning turn."""
    is_final: bool
    answer: Optional[str] = None
    tool_call: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    error: Optional[str] = None
    thought: Optional[str] = None

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
        self._initial_budget = max_reasoning_steps  # BUG-08: Track initial budget for cap
        
        self._current_loop_tools = []
        self.logger.info("Agent Orchestrator Booted (Phase 9B ? Power Features).")

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
            Phase 11: Durable Execution ? supports auto-resumption from checkpoints.
        """
        # Phase 11: Check for existing checkpoint to resume from
        if self.checkpoint and self.checkpoint.has_checkpoint():
            checkpoint_data = self.checkpoint.load_latest()
            if checkpoint_data:
                self.logger.info("?? Resuming from checkpoint...")
                if checkpoint_data.get("original_query") == text:
                    # Rehydrate step counter and tool history from checkpoint
                    resumed_step = checkpoint_data.get("step", 0)
                    resumed_tools = checkpoint_data.get("tools_executed", [])
                    self.logger.info(f"?? Resumed from step {resumed_step}, {len(resumed_tools)} tools previously executed.")

        # Phase 9B: Intercept slash commands ? bypass LLM entirely
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
            schema_array = [t.get_metadata() for t in self.executor.registry.get_all_tools()]
        
        # We start the dynamic reasoning loop
        budget = self.max_reasoning_steps
        step = 0
        consecutive_errors = 0
        last_tool_call_signature = None
        
        while step < budget:
            self.logger.debug(f"Starting ReAct loop turn {step+1} (Current Budget: {budget})")
            
            # Execute one step
            result = self.run_reasoning_step(
                text=text,
                schema_array=schema_array,
                known_plan_injection=known_plan_injection,
                last_tool_call_signature=last_tool_call_signature,
                consecutive_errors=consecutive_errors,
                budget=budget
            )
            
            # Handle result
            if result.error and not result.observation:
                return result.error
                
            if result.is_final:
                # Check mapping for plan caching (flawless execution check)
                if consecutive_errors == 0 and self.plan_library and self._current_loop_tools:
                    self.plan_library.record_successful_plan(text, self._current_loop_tools)
                self._current_loop_tools = []
                return result.answer
                
            # Update state for next iteration
            if result.tool_call:
                tool_name = result.tool_call.get("tool")
                action = result.tool_call.get("action")
                params = result.tool_call.get("parameters", {})
                last_tool_call_signature = f"{tool_name}:{action}:{hash(json.dumps(params, sort_keys=True))}"
                
                # Check for successful tool execution to adjust budget
                if "Execution Result from" in (result.observation or ""):
                    consecutive_errors = 0
                    # Reward progress by slightly extending the budget (cap at 15)
                    max_allowed = self._initial_budget + 3
                    if budget < max_allowed:
                        budget += 1
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        warn_msg = f"SYSTEM ABORT: 3 consecutive tool failures. Aborting task to protect API budget."
                        self.logger.error(warn_msg)
                        self.memory.commit_interaction(MemoryRole.SYSTEM, warn_msg)
                        self._current_loop_tools = []
                        return warn_msg
            else:
                consecutive_errors += 1
                
            step += 1
            # Phase 9A: Checkpoint state after each cycle step
            self._save_checkpoint(step, budget, text)
                
        # If loop breaks the step bounds
        fail_msg = f"Agent exhausted the max reasoning budget ({budget} loops) without returning a FINAL_ANSWER."
        self.logger.error(fail_msg)
        self.memory.commit_interaction(MemoryRole.SYSTEM, fail_msg)
        self._current_loop_tools = []
        return fail_msg

    def run_reasoning_step(
        self, 
        text: str, 
        schema_array: List[Dict[str, Any]], 
        known_plan_injection: str = "",
        last_tool_call_signature: str = None,
        consecutive_errors: int = 0,
        budget: int = 5
    ) -> ReasoningStepResult:
        """
        Executes a single reasoning turn: 
        State Assembly ? Prompt ? Model Dispatch ? Parse ? Action/Answer.
        """
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
                "os_details": platform.system(),
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
        
        # Phase 9A: Context Compaction ? compress older turns before LLM call
        if self.compactor and self.compactor.should_compact(messages):
            messages = self.compactor.compact(messages)
            self.logger.info("?? Context compacted before LLM dispatch.")
        
        try:
            # Dispatcher natively assesses complexity and sends either to Ollama or OpenAI
            response_text = self.router.execute_with_failover(messages)
        except Exception as e:
            err = f"Model execution crushed: {e}"
            self.logger.error(err)
            return ReasoningStepResult(is_final=False, error=f"SYSTEM FAILURE: {err}")
            
        self.memory.commit_interaction(MemoryRole.THOUGHT, response_text)
        
        # 4. Action Execution Parse
        if "FINAL_ANSWER:" in response_text:
            final_answer = response_text.split("FINAL_ANSWER:", 1)[1].strip()
            self.memory.commit_interaction(MemoryRole.AGENT, final_answer)
            return ReasoningStepResult(is_final=True, answer=final_answer, thought=response_text)
            
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
                    return ReasoningStepResult(is_final=False, error=warn_msg, thought=response_text)
                
                self.logger.info(f"Executing Tool Call: {tool_name}.{action}")
                
                # Execute Sandbox
                result = self.executor.execute_tool(tool_name, action, params, context=None)
                
                # Track executed tools for PlanLibrary recording
                self._current_loop_tools.append({"tool": tool_name, "action": action, "parameters": params})
                
                success = getattr(result, "success", True)
                
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
                
                if not success:
                    error_str = getattr(result, "error", "Unknown error")
                    self.logger.warning(f"Tool failed: {error_str}")
                    obs_str = f"TOOL ERROR from {tool_name}: {error_str}\n{result_str}"
                
                self.memory.commit_interaction(MemoryRole.OBSERVATION, obs_str)
                return ReasoningStepResult(
                    is_final=False, 
                    tool_call=call_def, 
                    observation=obs_str, 
                    thought=response_text
                )
                
            except Exception as e:
                err_msg = f"Failed to execute tool command. Error: {str(e)}\nMake sure output strictly matches 'TOOL_CALL: {{...}}' JSON."
                self.logger.error(err_msg)
                self.memory.commit_interaction(MemoryRole.OBSERVATION, err_msg)
                return ReasoningStepResult(is_final=False, error=err_msg, thought=response_text)
                
        else:
            warn = "System Observation: You failed to prefix your text with FINAL_ANSWER: or TOOL_CALL:. Please retry adhering to the requested format."
            self.memory.commit_interaction(MemoryRole.OBSERVATION, warn)
            return ReasoningStepResult(is_final=False, observation=warn, thought=response_text)

    def hydrate_session(self, session_id: str):
        """
        Restores the full cognitive state from a session checkpoint.
        Part of Phase 11 Durable Execution.
        """
        if not self.checkpoint:
            return
            
        data = self.checkpoint.load_latest(session_id)
        if not data:
            return
            
        self.logger.info(f"? Hydrating session {session_id} from checkpoint")
        # Restore memory, plan progress, etc.
        # This implementation assumes the checkpoint 'state' matches our needs.
        state = data.get("state", {})
        
        # We can re-populate memory if the checkpoint includes history
        if "history" in state:
            for entry in state["history"]:
                role = MemoryRole(entry["role"])
                self.memory.commit_interaction(role, entry["content"], entry.get("metadata"))

    def replay_events(self, events: List[Dict[str, Any]]):
        """
        Deterministically replays a sequence of events to reconstruct state.
        Useful for debugging and durable recovery.
        """
        self.logger.info(f"? Replaying {len(events)} events...")
        for ev in events:
            role = MemoryRole(ev.get("role", "thought"))
            content = ev.get("content", "")
            self.memory.commit_interaction(role, content, ev.get("metadata"))

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
            self.logger.warning(f"?? Checkpoint save failed (non-fatal): {e}")
