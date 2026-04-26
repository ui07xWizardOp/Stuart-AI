# Configuration System Integration Guide

This guide shows how to integrate the configuration management system into existing and new PCA components.

## Quick Start

### 1. Initialize Configuration at Startup

In your main application entry point (e.g., `main.py`):

```python
from config import load_config

# Load configuration at startup
config = load_config("config/pca_config.json")
print(f"✅ Configuration loaded successfully")
print(f"   System Mode: {config.system_mode}")
print(f"   Database: {config.database.host}:{config.database.port}")
```

### 2. Access Configuration in Components

In any component that needs configuration:

```python
from config import get_config

class AgentRuntime:
    def __init__(self):
        config = get_config()
        self.max_iterations = config.agent_runtime.max_iterations_per_task
        self.max_tool_calls = config.agent_runtime.max_tool_calls_per_task
        self.max_llm_calls = config.agent_runtime.max_llm_calls_per_task
        
    def execute_task(self, task):
        config = get_config()
        # Use configuration values
        if self.iteration_count >= config.agent_runtime.max_iterations_per_task:
            raise RuntimeError("Max iterations exceeded")
```

### 3. Enable Hot-Reloading (Optional)

For production systems that need configuration updates without restart:

```python
from config import load_config, ConfigHotReloader

# Load initial configuration
config = load_config("config/pca_config.json")

# Start hot-reloader
reloader = ConfigHotReloader("config/pca_config.json")
reloader.start()

# Your application runs...

# Stop reloader on shutdown
reloader.stop()
```

## Integration Examples

### Database Connection

```python
from config import get_config
import psycopg2
from psycopg2 import pool

class DatabaseConnection:
    def __init__(self):
        config = get_config()
        db_config = config.database
        
        self.connection_pool = pool.SimpleConnectionPool(
            db_config.min_connections,
            db_config.max_connections,
            host=db_config.host,
            port=db_config.port,
            database=db_config.name,
            user=db_config.user,
            password=db_config.password
        )
```

### Vector Database

```python
from config import get_config
from qdrant_client import QdrantClient

class VectorDatabase:
    def __init__(self):
        config = get_config()
        vdb_config = config.vector_db
        
        self.client = QdrantClient(
            host=vdb_config.host,
            port=vdb_config.port,
            api_key=vdb_config.api_key if vdb_config.api_key else None
        )
        self.collection_prefix = vdb_config.collection_prefix
```

### Logging System

```python
from config import get_config
import logging
import json

class LoggingSystem:
    def __init__(self):
        config = get_config()
        log_config = config.logging
        
        # Configure logging based on config
        logging.basicConfig(
            level=getattr(logging, log_config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        if log_config.enable_structured_logging:
            # Set up structured logging
            pass
```

### Rate Limiter

```python
from config import get_config
import time
from collections import deque

class RateLimiter:
    def __init__(self):
        config = get_config()
        self.config = config.rate_limiter
        self.llm_calls = deque()
        
    def check_llm_rate_limit(self):
        config = get_config()  # Get fresh config
        now = time.time()
        
        # Remove old calls outside the window
        cutoff = now - 60  # 1 minute window
        while self.llm_calls and self.llm_calls[0] < cutoff:
            self.llm_calls.popleft()
        
        # Check limit
        if len(self.llm_calls) >= config.rate_limiter.llm_calls_per_minute:
            raise RuntimeError("LLM rate limit exceeded")
        
        self.llm_calls.append(now)
```

### Agent Runtime with Configuration

```python
from config import get_config

class AgentRuntime:
    def __init__(self):
        self.reload_config()
    
    def reload_config(self):
        """Reload configuration (can be called when config changes)"""
        config = get_config()
        runtime_config = config.agent_runtime
        
        self.max_iterations = runtime_config.max_iterations_per_task
        self.max_tool_calls = runtime_config.max_tool_calls_per_task
        self.max_llm_calls = runtime_config.max_llm_calls_per_task
        self.max_execution_time = runtime_config.max_execution_time_per_task
        self.enable_reflection = runtime_config.enable_reflection
    
    def execute_command(self, command):
        # Use configuration values
        for iteration in range(self.max_iterations):
            # Execute reasoning loop
            pass
```

## Hot-Reloading with Component Updates

When configuration changes, you may want to update running components:

```python
from config import load_config, ConfigHotReloader, SystemConfig

# Global references to components
agent_runtime = None
rate_limiter = None
logger = None

def on_config_reload(new_config: SystemConfig):
    """Called when configuration is reloaded"""
    print("🔄 Configuration reloaded, updating components...")
    
    # Update agent runtime
    if agent_runtime:
        agent_runtime.reload_config()
    
    # Update rate limiter
    if rate_limiter:
        rate_limiter.reload_config()
    
    # Update logger level
    if logger:
        import logging
        logging.getLogger().setLevel(new_config.logging.log_level)
    
    print("✅ Components updated successfully")

# Initialize
config = load_config("config/pca_config.json")
agent_runtime = AgentRuntime()
rate_limiter = RateLimiter()

# Start hot-reloader with callback
reloader = ConfigHotReloader(
    "config/pca_config.json",
    callback=on_config_reload
)
reloader.start()
```

## Environment-Specific Configuration

### Development

```bash
# .env.development
PCA_DEV_MODE=true
PCA_LOG_LEVEL=DEBUG
PCA_DB_HOST=localhost
PCA_AGENT_MAX_ITERATIONS=10
```

### Production

```bash
# .env.production
PCA_DEV_MODE=false
PCA_LOG_LEVEL=INFO
PCA_DB_HOST=production-db.example.com
PCA_AGENT_MAX_ITERATIONS=20
```

Load environment-specific config:

```python
import os
from dotenv import load_dotenv
from config import load_config

# Load environment-specific .env file
env = os.getenv("ENVIRONMENT", "development")
load_dotenv(f".env.{env}")

# Load configuration (env vars will override JSON)
config = load_config("config/pca_config.json")
```

## Testing with Configuration

### Unit Tests

```python
import tempfile
import json
from config import load_config

def test_my_component():
    # Create test configuration
    test_config = {
        "agent_runtime": {
            "max_iterations_per_task": 5
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f)
        config_path = f.name
    
    try:
        # Load test configuration
        config = load_config(config_path)
        
        # Test your component
        runtime = AgentRuntime()
        assert runtime.max_iterations == 5
    
    finally:
        import os
        os.unlink(config_path)
```

### Integration Tests

```python
import os
from config import load_config

def test_integration():
    # Set test environment variables
    os.environ["PCA_DB_HOST"] = "test-db"
    os.environ["PCA_DB_NAME"] = "test_pca_db"
    
    try:
        config = load_config("config/pca_config.test.json")
        
        # Run integration tests
        # ...
    
    finally:
        del os.environ["PCA_DB_HOST"]
        del os.environ["PCA_DB_NAME"]
```

## Best Practices

1. **Load Once**: Call `load_config()` once at application startup
2. **Get Anywhere**: Use `get_config()` to access configuration in any component
3. **Reload Carefully**: Only use `reload_config()` when you need to pick up changes
4. **Environment Variables for Secrets**: Store sensitive data in environment variables
5. **JSON for Structure**: Use JSON files for complex nested configuration
6. **Validate Early**: Configuration is validated on load, so errors are caught early
7. **Hot-Reload in Production**: Use file-based hot-reloading for production systems
8. **Document Changes**: Update `pca_config.example.json` when adding new parameters

## Troubleshooting

### Configuration Not Found

```python
try:
    config = load_config("config/pca_config.json")
except FileNotFoundError:
    print("Configuration file not found, using defaults")
    config = load_config()  # Uses defaults
```

### Validation Errors

```python
try:
    config = load_config("config/pca_config.json")
except ValueError as e:
    print(f"Configuration validation failed: {e}")
    # Fix configuration and try again
```

### Hot-Reload Not Working

If hot-reload isn't working, try periodic reload instead:

```python
from config import PeriodicConfigReloader

# Check for changes every 60 seconds
reloader = PeriodicConfigReloader(interval_seconds=60)
reloader.start()
```

## Migration from Old Config System

If you have an existing configuration system, here's how to migrate:

### Old System

```python
# Old way
import os
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
```

### New System

```python
# New way
from config import get_config

config = get_config()
DB_HOST = config.database.host
DB_PORT = config.database.port
```

### Migration Steps

1. Create `config/pca_config.json` from `pca_config.example.json`
2. Map old environment variables to new PCA_ prefixed variables
3. Update components to use `get_config()` instead of `os.getenv()`
4. Test thoroughly
5. Remove old configuration code

## Summary

The configuration management system provides:

- ✅ Centralized configuration for all components
- ✅ Multiple configuration sources (env vars, JSON, defaults)
- ✅ Clear override hierarchy
- ✅ Comprehensive validation
- ✅ Hot-reloading support
- ✅ Type safety with dataclasses
- ✅ Easy testing

For more information, see `README.md` and `example_usage.py`.
