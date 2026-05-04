"""
Agent-Oriented Programming (Feature #8: Advanced Orchestration)

Treats agents as first-class configurable objects. Each agent is defined
declaratively with a role, system prompt, allowed tools, constraints,
and model preferences.

Provides:
  - AgentDefinition: Dataclass for agent configs
  - AgentRegistry: Named agent storage with disk persistence
  - AgentFactory: Spawns configured Orchestrator instances from definitions
  - Built-in templates: researcher, coder, analyst, writer
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict

from observability import get_logging_system


@dataclass
class AgentDefinition:
    """
    Declarative configuration for an agent persona.

    Attributes:
        name: Unique identifier for this agent type.
        role: High-level role description (e.g., "Senior Python Developer").
        system_prompt: Custom system prompt injected into the Orchestrator.
        allowed_tools: List of tool names this agent can use (empty = all).
        blocked_tools: Tools explicitly denied to this agent.
        max_steps: Maximum ReAct loop iterations.
        model_tier: Preferred model tier ("fast_cheap" or "complex_capable").
        constraints: Free-form constraints injected into reasoning.
        temperature: LLM temperature override (None = use default).
        metadata: Arbitrary key-value metadata.
    """
    name: str
    role: str = "General Assistant"
    system_prompt: str = ""
    allowed_tools: List[str] = field(default_factory=list)
    blocked_tools: List[str] = field(default_factory=list)
    max_steps: int = 5
    model_tier: str = "fast_cheap"
    constraints: List[str] = field(default_factory=list)
    temperature: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentDefinition":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Built-in Agent Templates ─────────────────────────────────────────

BUILTIN_TEMPLATES: Dict[str, AgentDefinition] = {
    "researcher": AgentDefinition(
        name="researcher",
        role="Deep Research Specialist",
        system_prompt=(
            "You are a meticulous research agent. Your goal is to find accurate, "
            "well-sourced information on any topic. Always cite sources when possible. "
            "Use web search and document retrieval tools extensively. "
            "Prioritize depth and accuracy over speed."
        ),
        allowed_tools=["web_search", "rag_search", "deep_research", "api_caller"],
        max_steps=8,
        model_tier="complex_capable",
        constraints=[
            "Always verify claims from multiple sources.",
            "Never fabricate citations or URLs.",
            "Structure output with clear headings and bullet points.",
        ],
    ),
    "coder": AgentDefinition(
        name="coder",
        role="Senior Software Engineer",
        system_prompt=(
            "You are an expert software engineer. Write clean, well-documented, "
            "production-quality code. Always handle edge cases and errors. "
            "Prefer readability over cleverness. Follow the project's existing patterns."
        ),
        allowed_tools=["code_executor", "file_manager", "terminal"],
        max_steps=7,
        model_tier="complex_capable",
        constraints=[
            "Always include error handling in code.",
            "Follow PEP 8 for Python code.",
            "Add docstrings to all functions and classes.",
            "Never execute destructive commands without explicit confirmation.",
        ],
    ),
    "analyst": AgentDefinition(
        name="analyst",
        role="Data Analyst",
        system_prompt=(
            "You are a data analysis specialist. Extract insights from data, "
            "create summaries, identify patterns, and present findings clearly. "
            "Use structured formats (tables, bullet points) for output."
        ),
        allowed_tools=["code_executor", "rag_search", "file_manager"],
        max_steps=6,
        model_tier="fast_cheap",
        constraints=[
            "Always show your methodology.",
            "Use precise numbers, not vague qualifiers.",
            "Present findings in structured tables when applicable.",
        ],
    ),
    "writer": AgentDefinition(
        name="writer",
        role="Technical Writer",
        system_prompt=(
            "You are a skilled technical writer. Produce clear, concise, "
            "well-structured documents. Adapt tone to the audience. "
            "Use markdown formatting for all output."
        ),
        allowed_tools=["web_search", "rag_search", "file_manager"],
        max_steps=5,
        model_tier="fast_cheap",
        constraints=[
            "Keep sentences concise and direct.",
            "Use active voice whenever possible.",
            "Structure all output with proper markdown headings.",
        ],
    ),
}


class AgentRegistry:
    """
    Named agent definition storage with JSON file persistence.

    Stores agent definitions in config/agents/*.json and provides
    CRUD operations for managing agent configurations.
    """

    AGENTS_DIR = os.path.join("config", "agents")

    def __init__(self):
        self.logger = get_logging_system()
        self._agents: Dict[str, AgentDefinition] = {}

        os.makedirs(self.AGENTS_DIR, exist_ok=True)

        # Load built-in templates
        for name, defn in BUILTIN_TEMPLATES.items():
            self._agents[name] = defn

        # Load custom agents from disk (overrides built-ins if same name)
        self._load_from_disk()

        self.logger.info(
            f"AgentRegistry initialized: {len(BUILTIN_TEMPLATES)} built-in + "
            f"{len(self._agents) - len(BUILTIN_TEMPLATES)} custom agents."
        )

    def _load_from_disk(self):
        """Load custom agent definitions from config/agents/*.json."""
        if not os.path.exists(self.AGENTS_DIR):
            return
        for filename in os.listdir(self.AGENTS_DIR):
            if not filename.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.AGENTS_DIR, filename), "r", encoding="utf-8") as f:
                    data = json.load(f)
                defn = AgentDefinition.from_dict(data)
                self._agents[defn.name] = defn
            except Exception as e:
                self.logger.warning(f"Failed to load agent definition {filename}: {e}")

    def get(self, name: str) -> Optional[AgentDefinition]:
        """Retrieve an agent definition by name."""
        return self._agents.get(name)

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all available agent definitions."""
        return [
            {
                "name": a.name,
                "role": a.role,
                "tools": len(a.allowed_tools),
                "max_steps": a.max_steps,
                "tier": a.model_tier,
                "builtin": a.name in BUILTIN_TEMPLATES,
            }
            for a in self._agents.values()
        ]

    def register(self, definition: AgentDefinition, persist: bool = True) -> str:
        """Register a new agent definition. Optionally persist to disk."""
        self._agents[definition.name] = definition

        if persist:
            self._save_to_disk(definition)

        self.logger.info(f"Agent '{definition.name}' registered (persist={persist}).")
        return f"Agent '{definition.name}' registered successfully."

    def remove(self, name: str) -> str:
        """Remove a custom agent definition."""
        if name in BUILTIN_TEMPLATES:
            return f"Cannot remove built-in agent '{name}'."
        if name not in self._agents:
            return f"Agent '{name}' not found."

        del self._agents[name]
        # Remove from disk
        path = os.path.join(self.AGENTS_DIR, f"{name}.json")
        if os.path.exists(path):
            os.remove(path)

        return f"Agent '{name}' removed."

    def _save_to_disk(self, definition: AgentDefinition):
        """Persist an agent definition to config/agents/{name}.json."""
        path = os.path.join(self.AGENTS_DIR, f"{definition.name}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(definition.to_dict(), f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save agent definition: {e}")


class AgentFactory:
    """
    Spawns configured Orchestrator instances from AgentDefinitions.

    Uses the base Orchestrator class but pre-configures it with the
    definition's system prompt, tool whitelist, and step budget.
    """

    def __init__(self, registry: AgentRegistry, orchestrator_factory=None):
        """
        Args:
            registry: The AgentRegistry to look up definitions from.
            orchestrator_factory: A callable that returns a fresh base Orchestrator.
                                  If None, agents cannot be spawned (registry-only mode).
        """
        self.logger = get_logging_system()
        self.registry = registry
        self._orchestrator_factory = orchestrator_factory
        self.logger.info("AgentFactory initialized.")

    def create(self, name: str) -> Any:
        """
        Create a configured Orchestrator from a named agent definition.

        Args:
            name: The agent definition name to instantiate.

        Returns:
            A configured Orchestrator instance.

        Raises:
            ValueError: If the agent name is not found or no factory is set.
        """
        defn = self.registry.get(name)
        if not defn:
            raise ValueError(f"Agent definition '{name}' not found in registry.")

        if not self._orchestrator_factory:
            raise ValueError("No orchestrator_factory set. Cannot spawn agents.")

        # Create base orchestrator
        orchestrator = self._orchestrator_factory()

        # Apply definition overrides
        orchestrator.max_reasoning_steps = defn.max_steps
        orchestrator._initial_budget = defn.max_steps

        # Inject custom system prompt by overriding the prompt manager's context
        if defn.system_prompt and hasattr(orchestrator, 'prompt_manager'):
            orchestrator.prompt_manager.override_system_prompt = defn.system_prompt

        # Apply tool whitelist if specified
        if defn.allowed_tools and hasattr(orchestrator, 'toolset_distributor'):
            orchestrator._agent_allowed_tools = defn.allowed_tools

        # Apply constraints as TELOS-like injection
        if defn.constraints:
            constraint_text = "\n".join(f"- {c}" for c in defn.constraints)
            orchestrator._agent_constraints = constraint_text

        self.logger.info(f"Spawned agent '{name}' (role={defn.role}, steps={defn.max_steps}).")
        return orchestrator

    def run_agent(self, name: str, task: str) -> str:
        """
        Convenience method: create an agent and immediately run a task.

        Args:
            name: Agent definition name.
            task: The task/query to execute.

        Returns:
            The agent's response string.
        """
        try:
            orchestrator = self.create(name)
            return orchestrator.process_user_message(task)
        except Exception as e:
            self.logger.error(f"Agent '{name}' execution failed: {e}")
            return f"Agent execution failed: {e}"
