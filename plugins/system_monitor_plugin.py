import os
import platform
from core.plugin_manager import StuartPlugin
from typing import Dict, Any

class SystemMonitorPlugin(StuartPlugin):
    name = "SystemMonitor"
    version = "1.0.0"
    description = "Reports system CPU, memory, and disk stats."

    def on_load(self, context: Dict[str, Any]):
        slash = context.get('slash_router')
        if slash:
            slash.register_command('/sysmon', self._cmd_sysmon, 'Show system resource usage')
        logger = context.get('logger')
        if logger:
            logger.info('SystemMonitorPlugin loaded.')

    def _cmd_sysmon(self, args: str) -> str:
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            lines = [
                '\U0001f4bb **System Monitor**',
                f'  OS: {platform.system()} {platform.release()}',
                f'  Python: {platform.python_version()}',
                f'  Disk Total: {total // (1024**3)} GB',
                f'  Disk Used:  {used // (1024**3)} GB',
                f'  Disk Free:  {free // (1024**3)} GB',
            ]
            return '\n'.join(lines)
        except Exception as e:
            return f'Error: {e}'
