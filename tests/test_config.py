"""
Simple tests for configuration management system

Run with: python -m pytest config/test_config.py
"""

import os
import json
import tempfile
from pathlib import Path
import pytest

from .system_config import (
    SystemConfig,
    DatabaseConfig,
    load_config,
    reload_config,
    get_config,
    _config,
    _config_file_path
)


def test_default_config():
    """Test that default configuration is valid"""
    config = SystemConfig()
    errors = config.validate()
    assert len(errors) == 0, f"Default configuration has validation errors: {errors}"


def test_database_config_defaults():
    """Test database configuration defaults"""
    config = DatabaseConfig()
    assert config.host == "localhost"
    assert config.port == 5432
    assert config.name == "pca_db"
    assert config.min_connections == 2
    assert config.max_connections == 10


def test_config_validation_database_port():
    """Test database port validation"""
    config = SystemConfig()
    config.database.port = 99999
    errors = config.validate()
    assert any("port must be between 1 and 65535" in error for error in errors)


def test_config_validation_min_max_connections():
    """Test database connection pool validation"""
    config = SystemConfig()
    config.database.min_connections = 10
    config.database.max_connections = 5
    errors = config.validate()
    assert any("max_connections" in error and "min_connections" in error for error in errors)


def test_config_validation_context_budget():
    """Test context manager budget validation"""
    config = SystemConfig()
    config.context_manager.max_tokens = 1000
    config.context_manager.system_instructions_budget = 500
    config.context_manager.current_task_budget = 1000
    errors = config.validate()
    assert any("total budget" in error and "exceeds max_tokens" in error for error in errors)


def test_load_config_from_json():
    """Test loading configuration from JSON file"""
    # Create temporary JSON config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_data = {
            "system_mode": "DEGRADED",
            "enable_dev_mode": True,
            "database": {
                "host": "testhost",
                "port": 5433,
                "name": "test_db"
            },
            "agent_runtime": {
                "max_iterations_per_task": 15
            }
        }
        json.dump(config_data, f)
        temp_path = f.name
    
    try:
        # Load config from temporary file
        config = load_config(temp_path)
        
        # Verify values were loaded
        assert config.system_mode == "DEGRADED"
        assert config.enable_dev_mode == True
        assert config.database.host == "testhost"
        assert config.database.port == 5433
        assert config.database.name == "test_db"
        assert config.agent_runtime.max_iterations_per_task == 15
    
    finally:
        # Clean up
        os.unlink(temp_path)


def test_load_config_from_env():
    """Test loading configuration from environment variables"""
    # Set environment variables
    os.environ["PCA_DB_HOST"] = "envhost"
    os.environ["PCA_DB_PORT"] = "5434"
    os.environ["PCA_AGENT_MAX_ITERATIONS"] = "25"
    os.environ["PCA_DEV_MODE"] = "true"
    
    try:
        # Create temporary empty JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = f.name
        
        try:
            # Load config (should use env vars)
            config = load_config(temp_path)
            
            # Verify environment variables were loaded
            assert config.database.host == "envhost"
            assert config.database.port == 5434
            assert config.agent_runtime.max_iterations_per_task == 25
            assert config.enable_dev_mode == True
        
        finally:
            os.unlink(temp_path)
    
    finally:
        # Clean up environment variables
        del os.environ["PCA_DB_HOST"]
        del os.environ["PCA_DB_PORT"]
        del os.environ["PCA_AGENT_MAX_ITERATIONS"]
        del os.environ["PCA_DEV_MODE"]


def test_config_override_hierarchy():
    """Test that environment variables override JSON configuration"""
    # Create JSON config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_data = {
            "database": {
                "host": "jsonhost",
                "port": 5432
            }
        }
        json.dump(config_data, f)
        temp_path = f.name
    
    # Set environment variable (should override JSON)
    os.environ["PCA_DB_HOST"] = "envhost"
    
    try:
        config = load_config(temp_path)
        
        # Environment variable should override JSON
        assert config.database.host == "envhost"
        # JSON value should be used for port (no env var)
        assert config.database.port == 5432
    
    finally:
        os.unlink(temp_path)
        del os.environ["PCA_DB_HOST"]


def test_config_to_dict():
    """Test converting configuration to dictionary"""
    config = SystemConfig()
    config_dict = config.to_dict()
    
    assert isinstance(config_dict, dict)
    assert "database" in config_dict
    assert "agent_runtime" in config_dict
    assert isinstance(config_dict["database"], dict)
    assert "host" in config_dict["database"]


def test_invalid_json_raises_error():
    """Test that invalid JSON raises appropriate error"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json }")
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_config(temp_path)
    finally:
        os.unlink(temp_path)


def test_get_config_before_load_raises_error():
    """Test that get_config raises error if config not loaded"""
    # Reset global config
    import config.system_config as sc
    sc._config = None
    
    with pytest.raises(RuntimeError, match="Configuration has not been loaded"):
        get_config()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
