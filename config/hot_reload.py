"""
Configuration Hot-Reloading System

Monitors configuration file changes and automatically reloads configuration
without requiring system restart.
"""

import time
import threading
from pathlib import Path
from typing import Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from .system_config import reload_config, get_config, SystemConfig


class ConfigFileHandler(FileSystemEventHandler):
    """Handler for configuration file changes"""
    
    def __init__(self, config_path: Path, callback: Optional[Callable[[SystemConfig], None]] = None):
        """
        Initialize configuration file handler
        
        Args:
            config_path: Path to configuration file to monitor
            callback: Optional callback function to call after successful reload
        """
        self.config_path = config_path
        self.callback = callback
        self.last_reload_time = 0
        self.reload_debounce_seconds = 1.0  # Prevent multiple reloads in quick succession
    
    def on_modified(self, event):
        """Handle file modification events"""
        if isinstance(event, FileModifiedEvent) and Path(event.src_path) == self.config_path:
            current_time = time.time()
            
            # Debounce: only reload if enough time has passed since last reload
            if current_time - self.last_reload_time < self.reload_debounce_seconds:
                return
            
            self.last_reload_time = current_time
            
            try:
                print(f"Configuration file changed: {self.config_path}")
                new_config = reload_config()
                print("Configuration reloaded successfully")
                
                if self.callback:
                    self.callback(new_config)
            
            except Exception as e:
                print(f"Error reloading configuration: {e}")


class ConfigHotReloader:
    """
    Configuration hot-reloader that monitors file changes
    
    Usage:
        reloader = ConfigHotReloader("config/pca_config.json")
        reloader.start()
        # ... system runs ...
        reloader.stop()
    """
    
    def __init__(
        self,
        config_path: str,
        callback: Optional[Callable[[SystemConfig], None]] = None
    ):
        """
        Initialize hot-reloader
        
        Args:
            config_path: Path to configuration file to monitor
            callback: Optional callback function to call after successful reload
        """
        self.config_path = Path(config_path)
        self.callback = callback
        self.observer: Optional[Observer] = None
        self.is_running = False
    
    def start(self) -> None:
        """Start monitoring configuration file for changes"""
        if self.is_running:
            print("Hot-reloader is already running")
            return
        
        if not self.config_path.exists():
            print(f"Warning: Configuration file {self.config_path} does not exist. Hot-reloader will not start.")
            return
        
        # Create observer and event handler
        self.observer = Observer()
        event_handler = ConfigFileHandler(self.config_path, self.callback)
        
        # Watch the directory containing the config file
        watch_dir = self.config_path.parent
        self.observer.schedule(event_handler, str(watch_dir), recursive=False)
        
        # Start observer
        self.observer.start()
        self.is_running = True
        print(f"Configuration hot-reloader started, monitoring: {self.config_path}")
    
    def stop(self) -> None:
        """Stop monitoring configuration file"""
        if not self.is_running:
            return
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        self.is_running = False
        print("Configuration hot-reloader stopped")
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()


class PeriodicConfigReloader:
    """
    Periodic configuration reloader that checks for changes at regular intervals
    
    Alternative to file watching for environments where file system events are not available
    """
    
    def __init__(
        self,
        interval_seconds: int = 60,
        callback: Optional[Callable[[SystemConfig], None]] = None
    ):
        """
        Initialize periodic reloader
        
        Args:
            interval_seconds: How often to check for configuration changes
            callback: Optional callback function to call after successful reload
        """
        self.interval_seconds = interval_seconds
        self.callback = callback
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_running = False
    
    def _reload_loop(self) -> None:
        """Background thread that periodically reloads configuration"""
        while not self.stop_event.wait(self.interval_seconds):
            try:
                new_config = reload_config()
                print(f"Configuration reloaded (periodic check every {self.interval_seconds}s)")
                
                if self.callback:
                    self.callback(new_config)
            
            except Exception as e:
                print(f"Error during periodic configuration reload: {e}")
    
    def start(self) -> None:
        """Start periodic configuration reloading"""
        if self.is_running:
            print("Periodic reloader is already running")
            return
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._reload_loop, daemon=True)
        self.thread.start()
        self.is_running = True
        print(f"Periodic configuration reloader started (interval: {self.interval_seconds}s)")
    
    def stop(self) -> None:
        """Stop periodic configuration reloading"""
        if not self.is_running:
            return
        
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        
        self.is_running = False
        print("Periodic configuration reloader stopped")
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()


def on_config_reload(new_config: SystemConfig) -> None:
    """
    Default callback for configuration reload events
    
    This can be customized to perform specific actions when configuration changes
    """
    print("Configuration reloaded:")
    print(f"  - System mode: {new_config.system_mode}")
    print(f"  - Dev mode: {new_config.enable_dev_mode}")
    print(f"  - Log level: {new_config.logging.log_level}")
    print(f"  - Max iterations per task: {new_config.agent_runtime.max_iterations_per_task}")
