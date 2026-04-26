"""
SystemConfig: Centralized configuration dataclass for PCA

Implements comprehensive configuration management with:
- Environment variable loading with validation
- JSON configuration file support
- Configuration hot-reloading
- Clear validation error messages
- Configuration defaults and override hierarchy
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from pathlib import Path
from enum import Enum


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SystemMode(str, Enum):
    """System operational modes"""
    FULL = "FULL"
    DEGRADED = "DEGRADED"
    READ_ONLY = "READ_ONLY"
    SAFE_MODE = "SAFE_MODE"


class SandboxIsolation(str, Enum):
    """Tool execution sandbox isolation levels"""
    CONTAINER = "CONTAINER"
    PROCESS = "PROCESS"
    RESTRICTED_RUNTIME = "RESTRICTED_RUNTIME"


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration"""
    host: str = "localhost"
    port: int = 5432
    name: str = "pca_db"
    user: str = "pca_user"
    password: str = ""
    min_connections: int = 2
    max_connections: int = 10
    connection_timeout: int = 30
    command_timeout: int = 60


@dataclass
class VectorDBConfig:
    """Vector database configuration (Qdrant/Weaviate/Chroma)"""
    provider: str = "qdrant"  # qdrant, weaviate, chroma
    host: str = "localhost"
    port: int = 6333
    api_key: str = ""
    collection_prefix: str = "pca"
    embedding_dimension: int = 1536


@dataclass
class AgentRuntimeConfig:
    """Agent Runtime Controller configuration"""
    max_iterations_per_task: int = 20
    max_tool_calls_per_task: int = 50
    max_llm_calls_per_task: int = 30
    max_execution_time_per_task: int = 300  # seconds
    state_persistence_interval: int = 1  # persist after every N iterations
    enable_reflection: bool = True
    reflection_trigger_on_failure: bool = True
    reflection_trigger_every_n_iterations: int = 5


@dataclass
class ModelRouterConfig:
    """Model routing configuration"""
    default_provider: str = "openai"
    enable_failover: bool = True
    enable_cost_prediction: bool = True
    warm_up_strategy: str = "lazy"  # eager, lazy, predictive
    warm_up_models: List[str] = field(default_factory=list)
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: float = 0.5
    circuit_breaker_timeout: int = 60


@dataclass
class PromptManagerConfig:
    """Prompt management configuration"""
    prompt_repository_path: str = "prompts"
    enable_versioning: bool = True
    enable_ab_testing: bool = False
    enable_hot_reload: bool = True
    hot_reload_interval: int = 60  # seconds


@dataclass
class TaskQueueConfig:
    """Task queue configuration"""
    backend: str = "redis"  # redis, rabbitmq
    max_queue_depth: int = 1000
    worker_count: int = 10
    backpressure_threshold: int = 800
    task_timeout: int = 600  # seconds
    enable_priority: bool = True


@dataclass
class ContextManagerConfig:
    """Context window management configuration"""
    max_tokens: int = 8000
    system_instructions_budget: int = 500
    current_task_budget: int = 1000
    conversation_history_budget: int = 2000
    tool_results_budget: int = 1500
    knowledge_budget: int = 2000
    memory_budget: int = 1000
    freshness_decay_function: str = "exponential"  # linear, exponential, step
    freshness_half_life_hours: float = 24.0
    enable_deduplication: bool = True
    deduplication_similarity_threshold: float = 0.9


@dataclass
class RateLimiterConfig:
    """Rate limiting and cost budget configuration"""
    llm_calls_per_minute: int = 60
    llm_calls_per_hour: int = 1000
    tool_executions_per_minute: int = 30
    workflow_executions_per_hour: int = 100
    api_calls_per_minute: int = 100
    cost_limit_per_hour: float = 10.0
    cost_limit_per_day: float = 100.0
    cost_limit_per_workflow: float = 5.0
    enable_circuit_breakers: bool = True
    circuit_breaker_failure_rate: float = 0.5
    circuit_breaker_recovery_timeout: int = 60


@dataclass
class ApprovalSystemConfig:
    """Approval system configuration"""
    enable_approvals: bool = True
    approval_timeout: int = 300  # seconds
    enable_escalation: bool = True
    escalation_timeout: int = 600  # seconds
    enable_bulk_approval: bool = True
    auto_approve_low_risk: bool = False


@dataclass
class ToolExecutorConfig:
    """Tool execution configuration"""
    default_sandbox_isolation: str = SandboxIsolation.PROCESS.value
    enable_capability_tokens: bool = True
    enable_network_isolation: bool = True
    enable_dlp_scanning: bool = True
    execution_timeout: int = 60  # seconds
    cpu_quota_ms: int = 10000
    memory_quota_bytes: int = 512 * 1024 * 1024  # 512MB
    network_bandwidth_bps: int = 10 * 1024 * 1024  # 10MB/s
    disk_write_quota_bytes: int = 100 * 1024 * 1024  # 100MB
    enable_execution_recording: bool = True


@dataclass
class WorkflowEngineConfig:
    """Workflow engine configuration"""
    enable_trust_levels: bool = True
    enable_compensating_actions: bool = True
    enable_idempotency: bool = True
    idempotency_token_ttl: int = 86400  # seconds (24 hours)
    max_workflow_steps: int = 100
    enable_versioning: bool = True


@dataclass
class MemorySystemConfig:
    """Memory system configuration"""
    short_term_memory_size: int = 100
    enable_memory_consolidation: bool = True
    consolidation_interval: int = 3600  # seconds (1 hour)
    memory_importance_threshold: float = 0.5
    enable_memory_distillation: bool = True
    distillation_interval: int = 86400  # seconds (24 hours)
    retention_policy_days: int = 90


@dataclass
class KnowledgeManagerConfig:
    """Knowledge management configuration"""
    chunk_size: int = 512
    chunk_overlap: int = 50
    enable_versioning: bool = True
    enable_source_trust_ranking: bool = True
    enable_knowledge_aging: bool = True
    knowledge_ttl_days: int = 365
    daily_ingestion_enabled: bool = True
    daily_ingestion_time: str = "02:00"  # HH:MM format


@dataclass
class EventBusConfig:
    """Event bus configuration"""
    enable_persistence: bool = True
    enable_event_ordering: bool = True
    ordering_guarantee: str = "per-workflow"  # per-workflow, per-partition, best-effort
    event_retention_days: int = 30
    enable_dead_letter_queue: bool = True
    enable_event_replay: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration"""
    log_level: str = LogLevel.INFO.value
    enable_structured_logging: bool = True
    log_format: str = "json"  # json, text
    log_file_path: str = "logs/pca.log"
    enable_log_rotation: bool = True
    log_rotation_max_bytes: int = 10 * 1024 * 1024  # 10MB
    log_rotation_backup_count: int = 5
    enable_console_output: bool = True


@dataclass
class TracingConfig:
    """Distributed tracing configuration"""
    enable_tracing: bool = True
    tracing_backend: str = "jaeger"  # jaeger, zipkin, opentelemetry
    tracing_endpoint: str = "http://localhost:14268/api/traces"
    sampling_rate: float = 1.0  # 0.0 to 1.0
    enable_trace_id_propagation: bool = True


@dataclass
class CognitiveMaintenanceConfig:
    """Cognitive maintenance configuration"""
    enable_memory_distillation: bool = True
    enable_knowledge_aging: bool = True
    enable_context_entropy_control: bool = True
    enable_plan_library_learning: bool = True
    maintenance_schedule: str = "0 2 * * *"  # cron format
    enable_automatic_gc: bool = True


@dataclass
class SecurityConfig:
    """Security configuration"""
    enable_capability_tokens: bool = True
    enable_network_isolation: bool = True
    enable_dlp_scanning: bool = True
    enable_prompt_injection_defense: bool = True
    enable_data_exfiltration_detection: bool = True
    allowed_filesystem_paths: List[str] = field(default_factory=lambda: ["/tmp", "/workspace"])
    blocked_network_domains: List[str] = field(default_factory=list)


@dataclass
class SystemConfig:
    """
    Centralized system configuration for Personal Cognitive Agent
    
    Supports:
    - Environment variable loading with validation
    - JSON configuration file support
    - Configuration hot-reloading
    - Clear validation error messages
    - Configuration defaults and override hierarchy
    
    Override hierarchy (highest to lowest priority):
    1. Environment variables
    2. JSON configuration file
    3. Default values
    """
    
    # Core settings
    system_mode: str = SystemMode.FULL.value
    enable_dev_mode: bool = False
    
    # Component configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    vector_db: VectorDBConfig = field(default_factory=VectorDBConfig)
    agent_runtime: AgentRuntimeConfig = field(default_factory=AgentRuntimeConfig)
    model_router: ModelRouterConfig = field(default_factory=ModelRouterConfig)
    prompt_manager: PromptManagerConfig = field(default_factory=PromptManagerConfig)
    task_queue: TaskQueueConfig = field(default_factory=TaskQueueConfig)
    context_manager: ContextManagerConfig = field(default_factory=ContextManagerConfig)
    rate_limiter: RateLimiterConfig = field(default_factory=RateLimiterConfig)
    approval_system: ApprovalSystemConfig = field(default_factory=ApprovalSystemConfig)
    tool_executor: ToolExecutorConfig = field(default_factory=ToolExecutorConfig)
    workflow_engine: WorkflowEngineConfig = field(default_factory=WorkflowEngineConfig)
    memory_system: MemorySystemConfig = field(default_factory=MemorySystemConfig)
    knowledge_manager: KnowledgeManagerConfig = field(default_factory=KnowledgeManagerConfig)
    event_bus: EventBusConfig = field(default_factory=EventBusConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    tracing: TracingConfig = field(default_factory=TracingConfig)
    cognitive_maintenance: CognitiveMaintenanceConfig = field(default_factory=CognitiveMaintenanceConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """
        Validate configuration and return list of error messages
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Validate database configuration
        if not self.database.host:
            errors.append("Database host cannot be empty")
        if self.database.port < 1 or self.database.port > 65535:
            errors.append(f"Database port must be between 1 and 65535, got {self.database.port}")
        if not self.database.name:
            errors.append("Database name cannot be empty")
        if not self.database.user:
            errors.append("Database user cannot be empty")
        if self.database.min_connections < 1:
            errors.append(f"Database min_connections must be at least 1, got {self.database.min_connections}")
        if self.database.max_connections < self.database.min_connections:
            errors.append(f"Database max_connections ({self.database.max_connections}) must be >= min_connections ({self.database.min_connections})")
        
        # Validate vector DB configuration
        if not self.vector_db.host:
            errors.append("Vector DB host cannot be empty")
        if self.vector_db.port < 1 or self.vector_db.port > 65535:
            errors.append(f"Vector DB port must be between 1 and 65535, got {self.vector_db.port}")
        if self.vector_db.embedding_dimension < 1:
            errors.append(f"Vector DB embedding_dimension must be positive, got {self.vector_db.embedding_dimension}")
        
        # Validate agent runtime configuration
        if self.agent_runtime.max_iterations_per_task < 1:
            errors.append(f"Agent runtime max_iterations_per_task must be positive, got {self.agent_runtime.max_iterations_per_task}")
        if self.agent_runtime.max_tool_calls_per_task < 1:
            errors.append(f"Agent runtime max_tool_calls_per_task must be positive, got {self.agent_runtime.max_tool_calls_per_task}")
        if self.agent_runtime.max_llm_calls_per_task < 1:
            errors.append(f"Agent runtime max_llm_calls_per_task must be positive, got {self.agent_runtime.max_llm_calls_per_task}")
        if self.agent_runtime.max_execution_time_per_task < 1:
            errors.append(f"Agent runtime max_execution_time_per_task must be positive, got {self.agent_runtime.max_execution_time_per_task}")
        
        # Validate context manager configuration
        if self.context_manager.max_tokens < 100:
            errors.append(f"Context manager max_tokens must be at least 100, got {self.context_manager.max_tokens}")
        total_budget = (
            self.context_manager.system_instructions_budget +
            self.context_manager.current_task_budget +
            self.context_manager.conversation_history_budget +
            self.context_manager.tool_results_budget +
            self.context_manager.knowledge_budget +
            self.context_manager.memory_budget
        )
        if total_budget > self.context_manager.max_tokens:
            errors.append(f"Context manager total budget ({total_budget}) exceeds max_tokens ({self.context_manager.max_tokens})")
        
        # Validate rate limiter configuration
        if self.rate_limiter.cost_limit_per_hour < 0:
            errors.append(f"Rate limiter cost_limit_per_hour must be non-negative, got {self.rate_limiter.cost_limit_per_hour}")
        if self.rate_limiter.cost_limit_per_day < self.rate_limiter.cost_limit_per_hour:
            errors.append(f"Rate limiter cost_limit_per_day ({self.rate_limiter.cost_limit_per_day}) must be >= cost_limit_per_hour ({self.rate_limiter.cost_limit_per_hour})")
        
        # Validate tool executor configuration
        if self.tool_executor.execution_timeout < 1:
            errors.append(f"Tool executor execution_timeout must be positive, got {self.tool_executor.execution_timeout}")
        if self.tool_executor.memory_quota_bytes < 1024 * 1024:  # 1MB minimum
            errors.append(f"Tool executor memory_quota_bytes must be at least 1MB, got {self.tool_executor.memory_quota_bytes}")
        
        # Validate logging configuration
        valid_log_levels = [level.value for level in LogLevel]
        if self.logging.log_level not in valid_log_levels:
            errors.append(f"Logging log_level must be one of {valid_log_levels}, got {self.logging.log_level}")
        
        # Validate tracing configuration
        if self.tracing.sampling_rate < 0.0 or self.tracing.sampling_rate > 1.0:
            errors.append(f"Tracing sampling_rate must be between 0.0 and 1.0, got {self.tracing.sampling_rate}")
        
        return errors


# Global configuration instance
_config: Optional[SystemConfig] = None
_config_file_path: Optional[Path] = None


def _load_from_env(config: SystemConfig) -> None:
    """
    Load configuration from environment variables
    
    Environment variables follow the pattern: PCA_<SECTION>_<KEY>
    Example: PCA_DATABASE_HOST, PCA_AGENT_RUNTIME_MAX_ITERATIONS_PER_TASK
    """
    # Database configuration
    if os.getenv("PCA_DB_HOST"):
        config.database.host = os.getenv("PCA_DB_HOST")
    if os.getenv("PCA_DB_PORT"):
        config.database.port = int(os.getenv("PCA_DB_PORT"))
    if os.getenv("PCA_DB_NAME"):
        config.database.name = os.getenv("PCA_DB_NAME")
    if os.getenv("PCA_DB_USER"):
        config.database.user = os.getenv("PCA_DB_USER")
    if os.getenv("PCA_DB_PASSWORD"):
        config.database.password = os.getenv("PCA_DB_PASSWORD")
    if os.getenv("PCA_DB_MIN_CONNECTIONS"):
        config.database.min_connections = int(os.getenv("PCA_DB_MIN_CONNECTIONS"))
    if os.getenv("PCA_DB_MAX_CONNECTIONS"):
        config.database.max_connections = int(os.getenv("PCA_DB_MAX_CONNECTIONS"))
    
    # Vector DB configuration
    if os.getenv("PCA_VECTOR_DB_HOST"):
        config.vector_db.host = os.getenv("PCA_VECTOR_DB_HOST")
    if os.getenv("PCA_VECTOR_DB_PORT"):
        config.vector_db.port = int(os.getenv("PCA_VECTOR_DB_PORT"))
    if os.getenv("PCA_VECTOR_DB_API_KEY"):
        config.vector_db.api_key = os.getenv("PCA_VECTOR_DB_API_KEY")
    if os.getenv("PCA_VECTOR_DB_PROVIDER"):
        config.vector_db.provider = os.getenv("PCA_VECTOR_DB_PROVIDER")
    
    # Agent Runtime configuration
    if os.getenv("PCA_AGENT_MAX_ITERATIONS"):
        config.agent_runtime.max_iterations_per_task = int(os.getenv("PCA_AGENT_MAX_ITERATIONS"))
    if os.getenv("PCA_AGENT_MAX_TOOL_CALLS"):
        config.agent_runtime.max_tool_calls_per_task = int(os.getenv("PCA_AGENT_MAX_TOOL_CALLS"))
    if os.getenv("PCA_AGENT_MAX_LLM_CALLS"):
        config.agent_runtime.max_llm_calls_per_task = int(os.getenv("PCA_AGENT_MAX_LLM_CALLS"))
    if os.getenv("PCA_AGENT_MAX_EXECUTION_TIME"):
        config.agent_runtime.max_execution_time_per_task = int(os.getenv("PCA_AGENT_MAX_EXECUTION_TIME"))
    
    # Model Router configuration
    if os.getenv("PCA_MODEL_DEFAULT_PROVIDER"):
        config.model_router.default_provider = os.getenv("PCA_MODEL_DEFAULT_PROVIDER")
    if os.getenv("PCA_MODEL_ENABLE_FAILOVER"):
        config.model_router.enable_failover = os.getenv("PCA_MODEL_ENABLE_FAILOVER").lower() == "true"
    
    # Context Manager configuration
    if os.getenv("PCA_CONTEXT_MAX_TOKENS"):
        config.context_manager.max_tokens = int(os.getenv("PCA_CONTEXT_MAX_TOKENS"))
    if os.getenv("PCA_CONTEXT_FRESHNESS_HALF_LIFE"):
        config.context_manager.freshness_half_life_hours = float(os.getenv("PCA_CONTEXT_FRESHNESS_HALF_LIFE"))
    
    # Rate Limiter configuration
    if os.getenv("PCA_RATE_LLM_CALLS_PER_MINUTE"):
        config.rate_limiter.llm_calls_per_minute = int(os.getenv("PCA_RATE_LLM_CALLS_PER_MINUTE"))
    if os.getenv("PCA_RATE_COST_LIMIT_PER_HOUR"):
        config.rate_limiter.cost_limit_per_hour = float(os.getenv("PCA_RATE_COST_LIMIT_PER_HOUR"))
    if os.getenv("PCA_RATE_COST_LIMIT_PER_DAY"):
        config.rate_limiter.cost_limit_per_day = float(os.getenv("PCA_RATE_COST_LIMIT_PER_DAY"))
    
    # Logging configuration
    if os.getenv("PCA_LOG_LEVEL"):
        config.logging.log_level = os.getenv("PCA_LOG_LEVEL")
    if os.getenv("PCA_LOG_FILE_PATH"):
        config.logging.log_file_path = os.getenv("PCA_LOG_FILE_PATH")
    
    # System mode
    if os.getenv("PCA_SYSTEM_MODE"):
        config.system_mode = os.getenv("PCA_SYSTEM_MODE")
    if os.getenv("PCA_DEV_MODE"):
        config.enable_dev_mode = os.getenv("PCA_DEV_MODE").lower() == "true"


def _load_from_json(config: SystemConfig, json_path: Path) -> None:
    """
    Load configuration from JSON file
    
    JSON structure should match the SystemConfig dataclass structure
    """
    if not json_path.exists():
        return
    
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Update configuration from JSON data
        if "system_mode" in data:
            config.system_mode = data["system_mode"]
        if "enable_dev_mode" in data:
            config.enable_dev_mode = data["enable_dev_mode"]
        
        # Update nested configurations
        if "database" in data:
            for key, value in data["database"].items():
                if hasattr(config.database, key):
                    setattr(config.database, key, value)
        
        if "vector_db" in data:
            for key, value in data["vector_db"].items():
                if hasattr(config.vector_db, key):
                    setattr(config.vector_db, key, value)
        
        if "agent_runtime" in data:
            for key, value in data["agent_runtime"].items():
                if hasattr(config.agent_runtime, key):
                    setattr(config.agent_runtime, key, value)
        
        if "model_router" in data:
            for key, value in data["model_router"].items():
                if hasattr(config.model_router, key):
                    setattr(config.model_router, key, value)
        
        if "prompt_manager" in data:
            for key, value in data["prompt_manager"].items():
                if hasattr(config.prompt_manager, key):
                    setattr(config.prompt_manager, key, value)
        
        if "task_queue" in data:
            for key, value in data["task_queue"].items():
                if hasattr(config.task_queue, key):
                    setattr(config.task_queue, key, value)
        
        if "context_manager" in data:
            for key, value in data["context_manager"].items():
                if hasattr(config.context_manager, key):
                    setattr(config.context_manager, key, value)
        
        if "rate_limiter" in data:
            for key, value in data["rate_limiter"].items():
                if hasattr(config.rate_limiter, key):
                    setattr(config.rate_limiter, key, value)
        
        if "approval_system" in data:
            for key, value in data["approval_system"].items():
                if hasattr(config.approval_system, key):
                    setattr(config.approval_system, key, value)
        
        if "tool_executor" in data:
            for key, value in data["tool_executor"].items():
                if hasattr(config.tool_executor, key):
                    setattr(config.tool_executor, key, value)
        
        if "workflow_engine" in data:
            for key, value in data["workflow_engine"].items():
                if hasattr(config.workflow_engine, key):
                    setattr(config.workflow_engine, key, value)
        
        if "memory_system" in data:
            for key, value in data["memory_system"].items():
                if hasattr(config.memory_system, key):
                    setattr(config.memory_system, key, value)
        
        if "knowledge_manager" in data:
            for key, value in data["knowledge_manager"].items():
                if hasattr(config.knowledge_manager, key):
                    setattr(config.knowledge_manager, key, value)
        
        if "event_bus" in data:
            for key, value in data["event_bus"].items():
                if hasattr(config.event_bus, key):
                    setattr(config.event_bus, key, value)
        
        if "logging" in data:
            for key, value in data["logging"].items():
                if hasattr(config.logging, key):
                    setattr(config.logging, key, value)
        
        if "tracing" in data:
            for key, value in data["tracing"].items():
                if hasattr(config.tracing, key):
                    setattr(config.tracing, key, value)
        
        if "cognitive_maintenance" in data:
            for key, value in data["cognitive_maintenance"].items():
                if hasattr(config.cognitive_maintenance, key):
                    setattr(config.cognitive_maintenance, key, value)
        
        if "security" in data:
            for key, value in data["security"].items():
                if hasattr(config.security, key):
                    setattr(config.security, key, value)
    
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file {json_path}: {e}")
    except Exception as e:
        raise ValueError(f"Error loading configuration from {json_path}: {e}")


def load_config(json_path: Optional[str] = None) -> SystemConfig:
    """
    Load system configuration with override hierarchy:
    1. Default values (lowest priority)
    2. JSON configuration file
    3. Environment variables (highest priority)
    
    Args:
        json_path: Optional path to JSON configuration file
                  Defaults to "config/pca_config.json"
    
    Returns:
        SystemConfig instance
    
    Raises:
        ValueError: If configuration validation fails
    """
    global _config, _config_file_path
    
    # Create config with defaults
    config = SystemConfig()
    
    # Load from JSON file if provided
    if json_path is None:
        json_path = "config/pca_config.json"
    
    config_path = Path(json_path)
    _config_file_path = config_path
    
    if config_path.exists():
        _load_from_json(config, config_path)
    
    # Load from environment variables (highest priority)
    _load_from_env(config)
    
    # Validate configuration
    errors = config.validate()
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
        raise ValueError(error_msg)
    
    _config = config
    return config


def reload_config() -> SystemConfig:
    """
    Reload configuration from the same sources
    
    Useful for hot-reloading configuration changes without restarting the system
    
    Returns:
        Updated SystemConfig instance
    
    Raises:
        ValueError: If configuration validation fails
        RuntimeError: If config has not been loaded yet
    """
    global _config, _config_file_path
    
    if _config is None:
        raise RuntimeError("Configuration has not been loaded yet. Call load_config() first.")
    
    # Reload from the same JSON path
    json_path = str(_config_file_path) if _config_file_path else None
    return load_config(json_path)


def get_config() -> SystemConfig:
    """
    Get the current system configuration
    
    Returns:
        Current SystemConfig instance
    
    Raises:
        RuntimeError: If configuration has not been loaded yet
    """
    global _config
    
    if _config is None:
        raise RuntimeError("Configuration has not been loaded yet. Call load_config() first.")
    
    return _config
