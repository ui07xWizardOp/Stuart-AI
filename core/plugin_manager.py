"""
Plugin Manager (Phase 11: Ecosystem & Extensibility)

Provides a hot-pluggable architecture to load external Python modules
from the `plugins/` directory at startup.

Allows plugins to:
1. Register custom BaseTools to the ToolRegistry
2. Register custom Slash Commands
3. Subscribe or publish to the EventBus
"""

import os
import sys
import importlib.util
import inspect
from typing import Dict, List, Any, Type

from observability import get_logging_system
from tools.base import BaseTool
from tools.registry import ToolRegistry
from events.event_bus import EventBus
from core.slash_commands import SlashCommandRouter


class StuartPlugin:
    """
    Base interface for all Stuart plugins.
    Custom plugins in `plugins/` should subclass this and implement `on_load`.
    """
    name: str = "UnnamedPlugin"
    version: str = "1.0.0"
    description: str = "No description provided."

    def on_load(self, context: Dict[str, Any]) -> None:
        """
        Called when the plugin is loaded.
        
        Args:
            context: A dictionary containing core references:
                - 'tool_registry': ToolRegistry instance
                - 'event_bus': EventBus instance
                - 'slash_router': SlashCommandRouter instance
                - 'logger': Logger instance
        """
        pass

    def on_unload(self) -> None:
        """Called if the plugin is unloaded (for future hot-reloading support)."""
        pass


import threading

class PluginManager:
    """Scans and loads StuartPlugins from a specified directory."""

    def __init__(self, 
                 tool_registry: ToolRegistry, 
                 event_bus: EventBus, 
                 slash_router: SlashCommandRouter,
                 plugins_dir: str = "plugins"):
        self.logger = get_logging_system()
        self.tool_registry = tool_registry
        self.event_bus = event_bus
        self.slash_router = slash_router
        self.plugins_dir = plugins_dir
        
        self._lock = threading.Lock()
        self.loaded_plugins: Dict[str, StuartPlugin] = {}
        
        # Ensure plugins directory exists
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir, exist_ok=True)
            self._create_example_plugin()

    def _create_example_plugin(self):
        """Creates an example plugin to guide the user."""
        example_path = os.path.join(self.plugins_dir, "example_plugin.py")
        content = '''\
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
            registry.register(HelloPluginTool())
            
        # 2. Register a slash command
        slash = context.get('slash_router')
        if slash:
            slash.register_command("/hello_plugin", self._cmd_hello, "Test command from example plugin")
            
        logger = context.get('logger')
        if logger:
            logger.info("ExamplePlugin loaded successfully!")
            
    def _cmd_hello(self, args: str) -> str:
        return f"? Hello from the plugin system! You said: {args}"
'''
        with open(example_path, "w", encoding="utf-8") as f:
            f.write(content)
        self.logger.info(f"Created example plugin template at {example_path}")

    def load_all(self):
        """Discovers and loads all valid plugins in the plugins directory."""
        if self.plugins_dir not in sys.path:
            sys.path.insert(0, self.plugins_dir)

        context = {
            'tool_registry': self.tool_registry,
            'event_bus': self.event_bus,
            'slash_router': self.slash_router,
            'logger': self.logger
        }

        loaded_count = 0
        for filename in os.listdir(self.plugins_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]
                try:
                    self._load_plugin_module(module_name, context)
                    loaded_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to load plugin '{filename}': {e}")
                    
        self.logger.info(f"PluginManager loaded {len(self.loaded_plugins)} plugins (Phase 11).")

    def _load_plugin_module(self, module_name: str, context: Dict[str, Any]):
        """Dynamically imports a module and instantiates any StuartPlugin classes inside it."""
        file_path = os.path.join(self.plugins_dir, f"{module_name}.py")
        
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for {module_name}")
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Scan for StuartPlugin subclasses
        found_plugin = False
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if inspect.isclass(attr) and issubclass(attr, StuartPlugin) and attr is not StuartPlugin:
                plugin_instance = attr()
                plugin_instance.on_load(context)
                with self._lock:
                    self.loaded_plugins[plugin_instance.name] = plugin_instance
                self.logger.info(f"Loaded plugin: {plugin_instance.name} v{plugin_instance.version}")
                found_plugin = True
                
        if not found_plugin:
            self.logger.debug(f"No StuartPlugin subclass found in {module_name}.py")

    def list_plugins(self) -> List[Dict[str, str]]:
        """Returns metadata about loaded plugins."""
        with self._lock:
            return [
                {
                    "name": p.name,
                    "version": p.version,
                    "description": p.description
                }
                for p in self.loaded_plugins.values()
            ]
