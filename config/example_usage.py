"""
Example usage of the Configuration Management System

This script demonstrates how to use the configuration system in your application.
"""

import os
from config import (
    load_config,
    get_config,
    reload_config,
    ConfigHotReloader,
    PeriodicConfigReloader,
    SystemConfig
)


def example_basic_usage():
    """Example: Basic configuration loading"""
    print("=" * 60)
    print("Example 1: Basic Configuration Loading")
    print("=" * 60)
    
    # Load configuration from JSON file
    config = load_config("config/pca_config.json")
    
    print(f"System Mode: {config.system_mode}")
    print(f"Dev Mode: {config.enable_dev_mode}")
    print(f"Database Host: {config.database.host}")
    print(f"Database Port: {config.database.port}")
    print(f"Max Iterations: {config.agent_runtime.max_iterations_per_task}")
    print(f"Log Level: {config.logging.log_level}")
    print()


def example_get_config():
    """Example: Getting configuration from anywhere in the application"""
    print("=" * 60)
    print("Example 2: Getting Configuration")
    print("=" * 60)
    
    # After load_config() has been called, you can get config anywhere
    config = get_config()
    
    print(f"Vector DB Provider: {config.vector_db.provider}")
    print(f"Vector DB Host: {config.vector_db.host}")
    print(f"Context Max Tokens: {config.context_manager.max_tokens}")
    print(f"Rate Limit (LLM calls/min): {config.rate_limiter.llm_calls_per_minute}")
    print()


def example_environment_override():
    """Example: Environment variable override"""
    print("=" * 60)
    print("Example 3: Environment Variable Override")
    print("=" * 60)
    
    # Set environment variables
    os.environ["PCA_DB_HOST"] = "production-db.example.com"
    os.environ["PCA_AGENT_MAX_ITERATIONS"] = "30"
    os.environ["PCA_LOG_LEVEL"] = "DEBUG"
    
    # Reload configuration to pick up environment changes
    config = reload_config()
    
    print(f"Database Host (from env): {config.database.host}")
    print(f"Max Iterations (from env): {config.agent_runtime.max_iterations_per_task}")
    print(f"Log Level (from env): {config.logging.log_level}")
    print()
    
    # Clean up
    del os.environ["PCA_DB_HOST"]
    del os.environ["PCA_AGENT_MAX_ITERATIONS"]
    del os.environ["PCA_LOG_LEVEL"]


def example_hot_reload_with_callback():
    """Example: Hot-reloading with custom callback"""
    print("=" * 60)
    print("Example 4: Hot-Reloading with Callback")
    print("=" * 60)
    
    def on_config_change(new_config: SystemConfig):
        """Custom callback when configuration changes"""
        print(f"? Configuration reloaded!")
        print(f"   New log level: {new_config.logging.log_level}")
        print(f"   New max iterations: {new_config.agent_runtime.max_iterations_per_task}")
        
        # You could update running components here
        # For example:
        # - Update logger level
        # - Adjust rate limiter settings
        # - Reconfigure connection pools
    
    # Start hot-reloader with callback
    reloader = ConfigHotReloader(
        "config/pca_config.json",
        callback=on_config_change
    )
    reloader.start()
    
    print("Hot-reloader started. Edit config/pca_config.json to see it reload.")
    print("Press Ctrl+C to stop...")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping hot-reloader...")
        reloader.stop()
        print("Hot-reloader stopped.")


def example_periodic_reload():
    """Example: Periodic configuration reloading"""
    print("=" * 60)
    print("Example 5: Periodic Configuration Reloading")
    print("=" * 60)
    
    # Start periodic reloader (checks every 30 seconds)
    reloader = PeriodicConfigReloader(interval_seconds=30)
    reloader.start()
    
    print("Periodic reloader started (checks every 30 seconds).")
    print("Configuration will automatically reload every 30 seconds.")
    print("Press Ctrl+C to stop...")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping periodic reloader...")
        reloader.stop()
        print("Periodic reloader stopped.")


def example_validation():
    """Example: Configuration validation"""
    print("=" * 60)
    print("Example 6: Configuration Validation")
    print("=" * 60)
    
    # Create a config with invalid values
    config = SystemConfig()
    config.database.port = 99999  # Invalid port
    config.database.max_connections = 5
    config.database.min_connections = 10  # Invalid: min > max
    
    # Validate
    errors = config.validate()
    
    if errors:
        print("Validation errors found:")
        for error in errors:
            print(f"  ? {error}")
    else:
        print("? Configuration is valid!")
    print()


def example_accessing_nested_config():
    """Example: Accessing nested configuration"""
    print("=" * 60)
    print("Example 7: Accessing Nested Configuration")
    print("=" * 60)
    
    config = get_config()
    
    # Database configuration
    print("Database Configuration:")
    print(f"  Host: {config.database.host}")
    print(f"  Port: {config.database.port}")
    print(f"  Name: {config.database.name}")
    print(f"  Connection Pool: {config.database.min_connections}-{config.database.max_connections}")
    print()
    
    # Agent Runtime configuration
    print("Agent Runtime Configuration:")
    print(f"  Max Iterations: {config.agent_runtime.max_iterations_per_task}")
    print(f"  Max Tool Calls: {config.agent_runtime.max_tool_calls_per_task}")
    print(f"  Max LLM Calls: {config.agent_runtime.max_llm_calls_per_task}")
    print(f"  Max Execution Time: {config.agent_runtime.max_execution_time_per_task}s")
    print(f"  Reflection Enabled: {config.agent_runtime.enable_reflection}")
    print()
    
    # Rate Limiter configuration
    print("Rate Limiter Configuration:")
    print(f"  LLM Calls/Minute: {config.rate_limiter.llm_calls_per_minute}")
    print(f"  Cost Limit/Hour: ${config.rate_limiter.cost_limit_per_hour}")
    print(f"  Cost Limit/Day: ${config.rate_limiter.cost_limit_per_day}")
    print()


def example_config_to_dict():
    """Example: Converting configuration to dictionary"""
    print("=" * 60)
    print("Example 8: Converting Configuration to Dictionary")
    print("=" * 60)
    
    config = get_config()
    config_dict = config.to_dict()
    
    print("Configuration as dictionary:")
    import json
    print(json.dumps(config_dict, indent=2, default=str))
    print()


def main():
    """Run all examples"""
    print("\n")
    print("?" + "=" * 58 + "?")
    print("?" + " " * 10 + "Configuration Management System Examples" + " " * 7 + "?")
    print("?" + "=" * 58 + "?")
    print()
    
    # Make sure we have a config file
    import os
    if not os.path.exists("config/pca_config.json"):
        print("??  Warning: config/pca_config.json not found.")
        print("   Creating from example file...")
        import shutil
        shutil.copy("config/pca_config.example.json", "config/pca_config.json")
        print("   ? Created config/pca_config.json")
        print()
    
    try:
        # Run examples
        example_basic_usage()
        example_get_config()
        example_environment_override()
        example_validation()
        example_accessing_nested_config()
        example_config_to_dict()
        
        # Interactive examples (commented out by default)
        # Uncomment to try hot-reloading:
        # example_hot_reload_with_callback()
        # example_periodic_reload()
        
        print("=" * 60)
        print("All examples completed successfully! ?")
        print("=" * 60)
    
    except Exception as e:
        print(f"? Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
