from core.plugin_manager import StuartPlugin
from tools.base import BaseTool, ToolRiskLevel
from typing import Dict, Any

class HelloPluginTool(BaseTool):
    name = "hello_plugin_world"
    description = "A simple tool added via a plugin to say hello."
    risk_level = ToolRiskLevel.LOW
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name to say hello to"}
            },
            "required": ["name"]
        }
        
    def execute(self, params: Dict[str, Any]) -> str:
        return f"Hello, {params.get('name', 'World')}! This is a plugin-provided tool."

class MyExamplePlugin(StuartPlugin):
    name = "ExamplePlugin"
    version = "1.0.0"
    description = "An example showing how to add tools and slash commands via plugins."
    
    def on_load(self, context: Dict[str, Any]):
        # 1. Register a new tool
        registry = context.get('tool_registry')
        if registry:
            registry.register_tool(HelloPluginTool())
            
        # 2. Register a slash command
        slash = context.get('slash_router')
        if slash:
            slash.register_command("/hello_plugin", self._cmd_hello, "Test command from example plugin")
            
        logger = context.get('logger')
        if logger:
            logger.info("ExamplePlugin loaded successfully!")
            
    def _cmd_hello(self, args: str) -> str:
        return f"✨ Hello from the plugin system! You said: {args}"
