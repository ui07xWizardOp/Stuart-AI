# Skills Marketplace & Sub-Agents

Stuart AI is extensible. Rather than hardcoding every capability into the core orchestrator, functionality is distributed via dynamically loaded **Plugins** and **Sub-Agents**.

## 1. The Skills Marketplace (Plugin System)

The `PluginManager` allows Stuart to load Python code at runtime. This modular approach keeps the core lightweight while allowing endless customization.

### How it Works
1. When Stuart boots, it reads `config/skills_registry.json`.
2. This JSON file acts as the "Marketplace". It contains metadata (Name, Version) and the raw Python code for various plugins.
3. The `PluginManager` uses `exec()` to compile the Python code into a dynamic module and instantiates the class.
4. The plugin is injected into the Orchestrator, automatically mapping its internal functions to Slash Commands or LLM Tools.

### Adding a New Skill
You do not need to reboot the system to add simple skills.
1. Open `config/skills_registry.json`.
2. Append a new JSON object following the existing schema.
3. Ensure your Python code extends `StuartPlugin` and implements the `on_load()` method to register commands.
4. (If running via CLI, restart to reload the registry. If dynamic reloading is built, use `/reload_skills`).

For deep development, write standard Python files in the `plugins/` directory. See the [Tool Development Guide](TOOL_DEVELOPMENT_GUIDE.md) for more details.

---

## 2. The Sub-Agent Pool

For complex, multi-step reasoning tasks that would exhaust the context window of the primary Orchestrator, Stuart employs a **Sub-Agent Pool**.

### The Deep Research Plugin Example
The primary implementation of this architecture is the `DeepResearchPlugin`. 

When a user asks: *"Research the financial implications of solid-state batteries and write a report."*
1. The primary Stuart agent recognizes this is a heavy task.
2. It delegates the task to the `DeepResearchPlugin`.
3. The plugin spawns an entirely independent **Sub-Agent** (a fresh instance of the ReAct loop with its own context window and API access).
4. This Sub-Agent operates asynchronously in the background. It searches Wikipedia, reads RSS feeds, and synthesizes data.
5. Once complete, the Sub-Agent returns the final dense report to the main Orchestrator, which presents it to the user.

> [!TIP]  
> Sub-agents are inherently safer. Because they operate in a segregated sandbox, if a Sub-Agent hallucinates or crashes, it does not bring down your main Stuart interface.
