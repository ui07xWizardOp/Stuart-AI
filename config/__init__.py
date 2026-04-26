"""
Configuration Management System for Personal Cognitive Agent (PCA)

This module provides centralized configuration loading, validation, and hot-reloading
capabilities for all PCA components.
"""

from .system_config import SystemConfig, load_config, reload_config, get_config

__all__ = [
    'SystemConfig',
    'load_config',
    'reload_config',
    'get_config',
]

# Optional hot-reload functionality (requires watchdog package)
try:
    from .hot_reload import ConfigHotReloader, PeriodicConfigReloader, on_config_reload
    __all__.extend(['ConfigHotReloader', 'PeriodicConfigReloader', 'on_config_reload'])
except ImportError:
    # Watchdog not installed, hot-reload functionality not available
    pass
