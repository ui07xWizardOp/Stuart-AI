# CLI & Commands Reference

Stuart AI provides a robust Command Line Interface (CLI) for headless interaction, power users, and programmatic automation. The CLI handles both natural language reasoning and instant, zero-shot **Slash Commands**.

## Launching the CLI

To boot the agent without the Desktop GUI overlay, use the `cli_agent.py` script:

```bash
# Ensure your virtual environment is active
.\venv\Scripts\activate

# Boot the CLI
python cli_agent.py
```

You will be greeted with the `[STUART]:` prompt. From here, you can type natural language requests just as you would in the GUI.

## The Slash Command Architecture

Slash commands bypass the standard LLM ReAct loop. They are executed instantly by mapped Python functions. This is ideal for systemic queries, debugging, and rapid actions.

### Core Commands

| Command | Description | Example |
|---|---|---|
| `/status` | Returns the current health of the Orchestrator, Token Quotas, and active Models. | `/status` |
| `/skills` | Lists all loaded plugins and tools available to the Orchestrator. | `/skills` |
| `/traces` | Fetches the latest OpenTelemetry trace logs for observability and debugging. | `/traces` |

### Plugin Commands

Plugins loaded dynamically via the `skills_registry.json` often expose their own slash commands. By default, the following are available:

| Command | Description | Example |
|---|---|---|
| `/sysmon` | Outputs current CPU, Memory, and Disk usage via the SystemMonitor plugin. | `/sysmon` |
| `/note` | Appends a quick markdown note to `data/notes.md`. | `/note Remember to buy milk` |
| `/pomodoro` | Starts a silent background focus timer (default 25 minutes). | `/pomodoro 45` |
| `/research` | Triggers the Deep Research plugin to spawn a sub-agent. | `/research AI advancements` |

## Interactive Shortcuts

While in the `cli_agent.py` terminal:
- Type `exit` or `quit` to cleanly shutdown the agent and save memory checkpoints.
- Use `Ctrl+C` to force an emergency exit (this triggers the `KeyboardInterrupt` handler for safe closure).

> [!NOTE]  
> All slash commands available in the CLI are also fully accessible via the **Telegram Bot Integration**. Sending `/sysmon` to your Telegram bot will return the exact same system statistics.
