# Configuration Management System

Centralized configuration management for the Personal Cognitive Agent (PCA) system.

## Features

- **Comprehensive Configuration**: All PCA components configured through a single system
- **Multiple Sources**: Load from environment variables, JSON files, or defaults
- **Override Hierarchy**: Clear precedence rules for configuration sources
- **Validation**: Comprehensive validation with clear error messages
- **Hot-Reloading**: Automatic configuration reload without system restart
- **Type Safety**: Strongly typed configuration with dataclasses

## Configuration Override Hierarchy

Configuration values are loaded with the following priority (highest to lowest):

1. **Environment Variables** (highest priority)
2. **JSON Configuration File**
3. **Default Values** (lowest priority)

This means environment variables will always override JSON file settings, which in turn override defaults.

## Usage

### Basic Usage

```python
from config import load_config, get_config

# Load configuration (call once at startup)
config = load_config("config/pca_config.json")

# Access configuration anywhere in the application
config = get_config()
print(f"Database host: {config.database.host}")
print(f"Max iterations: {config.agent_runtime.max_iterations_per_task}")
```

### Hot-Reloading

#### File-Based Hot-Reloading (Recommended)

```python
from config import load_config, ConfigHotReloader

# Load initial configuration
config = load_config("config/pca_config.json")

# Start hot-reloader
reloader = ConfigHotReloader("config/pca_config.json")
reloader.start()

# Configuration will automatically reload when file changes
# ...

# Stop hot-reloader when shutting down
reloader.stop()
```

#### Periodic Hot-Reloading

```python
from config import load_config, PeriodicConfigReloader

# Load initial configuration
config = load_config("config/pca_config.json")

# Start periodic reloader (checks every 60 seconds)
reloader = PeriodicConfigReloader(interval_seconds=60)
reloader.start()

# Configuration will automatically reload every 60 seconds
# ...

# Stop reloader when shutting down
reloader.stop()
```

#### Custom Reload Callback

```python
from config import ConfigHotReloader, SystemConfig

def on_config_change(new_config: SystemConfig):
    print(f"Configuration changed! New log level: {new_config.logging.log_level}")
    # Perform any necessary updates to running components

reloader = ConfigHotReloader(
    "config/pca_config.json",
    callback=on_config_change
)
reloader.start()
```

### Manual Reload

```python
from config import reload_config

# Manually reload configuration
new_config = reload_config()
print("Configuration reloaded successfully")
```

## Environment Variables

All configuration parameters can be set via environment variables using the prefix `PCA_`.

### Database Configuration

```bash
PCA_DB_HOST=localhost
PCA_DB_PORT=5432
PCA_DB_NAME=pca_db
PCA_DB_USER=pca_user
PCA_DB_PASSWORD=your_secure_password
PCA_DB_MIN_CONNECTIONS=2
PCA_DB_MAX_CONNECTIONS=10
```

### Vector Database Configuration

```bash
PCA_VECTOR_DB_HOST=localhost
PCA_VECTOR_DB_PORT=6333
PCA_VECTOR_DB_API_KEY=your_api_key
PCA_VECTOR_DB_PROVIDER=qdrant
```

### Agent Runtime Configuration

```bash
PCA_AGENT_MAX_ITERATIONS=20
PCA_AGENT_MAX_TOOL_CALLS=50
PCA_AGENT_MAX_LLM_CALLS=30
PCA_AGENT_MAX_EXECUTION_TIME=300
```

### Model Router Configuration

```bash
PCA_MODEL_DEFAULT_PROVIDER=openai
PCA_MODEL_ENABLE_FAILOVER=true
```

### Context Manager Configuration

```bash
PCA_CONTEXT_MAX_TOKENS=8000
PCA_CONTEXT_FRESHNESS_HALF_LIFE=24.0
```

### Rate Limiter Configuration

```bash
PCA_RATE_LLM_CALLS_PER_MINUTE=60
PCA_RATE_COST_LIMIT_PER_HOUR=10.0
PCA_RATE_COST_LIMIT_PER_DAY=100.0
```

### Logging Configuration

```bash
PCA_LOG_LEVEL=INFO
PCA_LOG_FILE_PATH=logs/pca.log
```

### System Configuration

```bash
PCA_SYSTEM_MODE=FULL
PCA_DEV_MODE=false
```

## JSON Configuration File

Create a JSON configuration file based on `pca_config.example.json`:

```bash
cp config/pca_config.example.json config/pca_config.json
```

Edit the file to customize your configuration. The JSON structure mirrors the SystemConfig dataclass structure.

Example:

```json
{
  "system_mode": "FULL",
  "enable_dev_mode": false,
  "database": {
    "host": "localhost",
    "port": 5432,
    "name": "pca_db",
    "user": "pca_user",
    "password": "your_password"
  },
  "agent_runtime": {
    "max_iterations_per_task": 20,
    "max_tool_calls_per_task": 50
  }
}
```

## Configuration Sections

### Core Settings

- `system_mode`: Operational mode (FULL, DEGRADED, READ_ONLY, SAFE_MODE)
- `enable_dev_mode`: Enable development mode features

### Component Configurations

- **database**: PostgreSQL database settings
- **vector_db**: Vector database (Qdrant/Weaviate/Chroma) settings
- **agent_runtime**: Agent Runtime Controller settings
- **model_router**: LLM model routing settings
- **prompt_manager**: Prompt template management settings
- **task_queue**: Asynchronous task queue settings
- **context_manager**: Context window management settings
- **rate_limiter**: Rate limiting and cost budget settings
- **approval_system**: Human-in-the-loop approval settings
- **tool_executor**: Tool execution and sandboxing settings
- **workflow_engine**: Workflow management settings
- **memory_system**: Memory system settings
- **knowledge_manager**: Knowledge management settings
- **event_bus**: Event bus settings
- **logging**: Logging configuration
- **tracing**: Distributed tracing settings
- **cognitive_maintenance**: Cognitive maintenance settings
- **security**: Security settings

## Validation

Configuration is automatically validated when loaded. Validation checks include:

- Required fields are not empty
- Numeric values are within valid ranges
- Port numbers are valid (1-65535)
- Budget allocations don't exceed limits
- Enum values are valid

If validation fails, a `ValueError` is raised with clear error messages:

```python
try:
    config = load_config("config/pca_config.json")
except ValueError as e:
    print(f"Configuration validation failed: {e}")
```

Example validation error:

```
Configuration validation failed:
  - Database port must be between 1 and 65535, got 99999
  - Context manager total budget (10000) exceeds max_tokens (8000)
  - Rate limiter cost_limit_per_day (5.0) must be >= cost_limit_per_hour (10.0)
```

## Best Practices

1. **Use Environment Variables for Secrets**: Store sensitive data like passwords and API keys in environment variables, not in JSON files
2. **Version Control**: Commit `pca_config.example.json` but not `pca_config.json` (add to .gitignore)
3. **Hot-Reloading in Production**: Use file-based hot-reloading for production, periodic reloading for development
4. **Validation**: Always validate configuration after loading to catch errors early
5. **Documentation**: Document any custom configuration parameters you add

## Adding New Configuration Parameters

To add new configuration parameters:

1. Add the parameter to the appropriate dataclass in `system_config.py`
2. Add validation logic in `SystemConfig.validate()` if needed
3. Add environment variable loading in `_load_from_env()`
4. Add JSON loading in `_load_from_json()`
5. Update `pca_config.example.json` with the new parameter
6. Update this README with documentation

## Troubleshooting

### Configuration Not Loading

- Check that the JSON file path is correct
- Verify JSON syntax is valid (use a JSON validator)
- Check file permissions

### Environment Variables Not Working

- Ensure variables use the `PCA_` prefix
- Check variable names match exactly (case-sensitive)
- Verify environment variables are set in the correct shell/process

### Validation Errors

- Read error messages carefully - they indicate exactly what's wrong
- Check that all required fields are set
- Verify numeric values are within valid ranges
- Ensure enum values match allowed options

### Hot-Reloading Not Working

- Verify the configuration file path is correct
- Check that the file system supports file watching (some network filesystems don't)
- Try periodic reloading as an alternative
- Check for error messages in logs
