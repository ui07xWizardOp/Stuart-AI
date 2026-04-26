# Stuart Scheduling & Automation: Proactive Intelligence

Stuart-AI isn't just a reactive assistant; it is built for **Proactive Intelligence**. Using the `CronManager` and the underlying `AutomationScheduler`, Stuart can execute natural-language tasks on a schedule without manual intervention.

## 📅 Cron Manager
The `CronManager` handles high-level scheduling and job persistence. It allows you to define tasks that fire prompts through the Orchestrator's ReAct loop.

### Features
- **Disk Persistence**: Jobs survive agent restarts via `data/cron_jobs.json`.
- **Natural Language Prompts**: Schedule commands like "Summarize my emails" or "Check the weather in Tokyo".
- **Dynamic Management**: Add, remove, or list jobs via the CLI or Web Interface.

### Example Usage
To add a daily job:
```python
cron_manager.add(time_str="08:00", prompt="Generate a daily plan based on my Obsidian notes.")
```

To add an interval job:
```python
cron_manager.add(job_type="interval", interval_minutes=60, prompt="Check my urgent Jira tickets.")
```

## ⏱️ Automation Scheduler
The `AutomationScheduler` is the underlying engine that manages the precise timing of task execution.

### Capabilities
- **Daily Recurrence**: Executes at a specific time every day.
- **Interval Recurrence**: Executes every N minutes.
- **Async Execution**: Jobs run in background threads to avoid blocking the main overlay interaction.

## 🛠️ Implementation & Data Specs
- **CronManager**: `automation/cron_manager.py`
- **Scheduler**: `automation/scheduler.py`
- **Persistence**: `data/cron_jobs.json`

For granular data schemas and job definitions, see the **[DATA_SCHEMA_SPECIFICATION.md](DATA_SCHEMA_SPECIFICATION.md)**.

## 🧠 Cognitive Maintenance
Automation isn't just for user tasks. Stuart also schedules its own **Cognitive Maintenance** routines:
- **Daily Distillation**: Midnight cleanup of raw conversational logs into dense long-term insights.
- **TTL Pruning**: Automatic removal of expired memory nodes to prevent "memory bloat".

---

> [!TIP]
> You can view all active jobs by using the `/plan` or `/status` command in the Stuart interface (if implemented) or by checking the "Automation" tab in the Web Dashboard.
