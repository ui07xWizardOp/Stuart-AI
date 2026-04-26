"""
Automation Hook Tool

Grants the LLM the self-awareness to schedule events and drop processes into Background threads.
"""

from typing import Dict, Any, Optional

from tools.base import BaseTool, CapabilityDescriptor, ToolRiskLevel, ToolResult
from automation.scheduler import AutomationScheduler
from automation.task_queue import TaskQueue


class AutomationTool(BaseTool):
    
    name = "automation_engine"
    description = "Schedules tasks for the future or runs heavy tasks asynchronously in the background."
    version = "1.0.0"
    category = "workflow"
    risk_level = ToolRiskLevel.LOW
    
    parameter_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "The exact natural language task to run."},
            "schedule_type": {"type": "string", "enum": ["interval", "daily", "background_now"], "description": "Type of timing."},
            "interval_minutes": {"type": "integer", "description": "If interval, how many minutes between runs."},
            "daily_time": {"type": "string", "description": "If daily, the 24hr HH:MM code."},
            "job_id": {"type": "string", "description": "Used only for cancel_job."}
        }
    }
    
    capabilities = [
        CapabilityDescriptor("schedule_task", "Schedules a task to run later.", ["prompt", "schedule_type"]),
        CapabilityDescriptor("run_in_background", "Runs a task instantly but detached from chat.", ["prompt"]),
        CapabilityDescriptor("list_jobs", "Shows all scheduled automations.", []),
        CapabilityDescriptor("cancel_job", "Deletes a scheduled automation.", ["job_id"])
    ]

    def __init__(self, scheduler: AutomationScheduler, queue: TaskQueue):
        self.scheduler = scheduler
        self.queue = queue

    def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> ToolResult:
        if action == "run_in_background":
            prompt = parameters.get("prompt")
            if not prompt:
                return ToolResult(success=False, error="Requires 'prompt'", output=None)
                
            job_id = self.queue.push_background_task(prompt)
            return ToolResult(success=True, output=f"Task pushed to background worker. Background Job ID: {job_id}")

        elif action == "schedule_task":
            prompt = parameters.get("prompt")
            s_type = parameters.get("schedule_type")
            
            if not prompt or not s_type:
                return ToolResult(success=False, error="Requires 'prompt' and 'schedule_type'", output=None)
                
            if s_type == "interval":
                mins = parameters.get("interval_minutes", 60)
                job_id = self.scheduler.add_interval_job(mins, prompt)
                return ToolResult(success=True, output=f"Scheduled to run every {mins} minutes. Job ID: {job_id}")
                
            elif s_type == "daily":
                t_val = parameters.get("daily_time", "09:00")
                job_id = self.scheduler.add_daily_job(t_val, prompt)
                return ToolResult(success=True, output=f"Scheduled daily runs at {t_val}. Job ID: {job_id}")
                
            else:
                return ToolResult(success=False, error="Invalid schedule_type.", output=None)

        elif action == "list_jobs":
            return ToolResult(success=True, output=self.scheduler.list_jobs())

        elif action == "cancel_job":
            j_id = parameters.get("job_id")
            if not j_id:
                return ToolResult(success=False, error="Requires 'job_id'", output=None)
                
            if self.scheduler.cancel_job(j_id):
                return ToolResult(success=True, output=f"Cancelled {j_id}.")
            return ToolResult(success=False, error=f"Could not find {j_id}.", output=None)

        return ToolResult(success=False, error=f"Unknown capability: {action}", output=None)
