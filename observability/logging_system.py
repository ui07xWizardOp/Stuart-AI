"""
LoggingSystem: Structured logging infrastructure for PCA

Implements:
- Structured logging with JSON format
- Log level management (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Log rotation and retention policies
- Query interface for recent logs
- Trace ID and correlation ID tracking
"""

import json
import logging
import logging.handlers
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import uuid4


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: str  # ISO 8601 format
    level: str
    component: str
    message: str
    trace_id: str
    correlation_id: str
    context: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert log entry to JSON string"""
        return json.dumps(self.to_dict())


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def __init__(self, component: str = "unknown"):
        super().__init__()
        self.component = component
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        # Extract trace_id and correlation_id from record if available
        trace_id = getattr(record, 'trace_id', 'no-trace')
        correlation_id = getattr(record, 'correlation_id', 'no-correlation')
        
        # Extract additional context
        context = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'pathname', 'process', 'processName', 'relativeCreated',
                          'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
                          'trace_id', 'correlation_id', 'component']:
                try:
                    # Only include JSON-serializable values
                    json.dumps(value)
                    context[key] = value
                except (TypeError, ValueError):
                    context[key] = str(value)
        
        # Add exception info if present
        if record.exc_info:
            context['exception'] = self.formatException(record.exc_info)
        
        log_entry = LogEntry(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            level=record.levelname,
            component=getattr(record, 'component', self.component),
            message=record.getMessage(),
            trace_id=trace_id,
            correlation_id=correlation_id,
            context=context
        )
        
        return log_entry.to_json()


class LoggingSystem:
    """
    Centralized logging system for PCA
    
    Features:
    - Structured logging with JSON format
    - Log level management per component
    - Log rotation and retention
    - Console and file output
    - Trace ID and correlation ID propagation
    """
    
    def __init__(
        self,
        log_level: str = LogLevel.INFO.value,
        log_file_path: str = "logs/pca.log",
        enable_log_rotation: bool = True,
        log_rotation_max_bytes: int = 10 * 1024 * 1024,  # 10MB
        log_rotation_backup_count: int = 5,
        enable_console_output: bool = True,
        enable_structured_logging: bool = True,
        log_format: str = "json"
    ):
        """
        Initialize logging system
        
        Args:
            log_level: Default log level
            log_file_path: Path to log file
            enable_log_rotation: Enable log rotation
            log_rotation_max_bytes: Max size before rotation
            log_rotation_backup_count: Number of backup files to keep
            enable_console_output: Enable console logging
            enable_structured_logging: Use structured JSON logging
            log_format: Log format (json or text)
        """
        self.log_level = log_level
        self.log_file_path = Path(log_file_path)
        self.enable_log_rotation = enable_log_rotation
        self.log_rotation_max_bytes = log_rotation_max_bytes
        self.log_rotation_backup_count = log_rotation_backup_count
        self.enable_console_output = enable_console_output
        self.enable_structured_logging = enable_structured_logging
        self.log_format = log_format
        
        # Component-specific loggers
        self._loggers: Dict[str, logging.Logger] = {}
        
        # Component-specific log levels
        self._component_log_levels: Dict[str, str] = {}
        
        # In-memory log buffer for queries (limited size)
        self._log_buffer: List[LogEntry] = []
        self._max_buffer_size = 1000
        
        # Initialize root logger
        self._setup_root_logger()
    
    def _setup_root_logger(self) -> None:
        """Set up root logger configuration"""
        # Create logs directory if it doesn't exist
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.log_level))
        
        # Remove existing handlers
        root_logger.handlers.clear()
        
        # Add file handler with rotation
        if self.enable_log_rotation:
            file_handler = logging.handlers.RotatingFileHandler(
                self.log_file_path,
                maxBytes=self.log_rotation_max_bytes,
                backupCount=self.log_rotation_backup_count
            )
        else:
            file_handler = logging.FileHandler(self.log_file_path)
        
        if self.enable_structured_logging and self.log_format == "json":
            file_handler.setFormatter(JSONFormatter(component="root"))
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
            )
        
        root_logger.addHandler(file_handler)
        
        # Add console handler if enabled
        if self.enable_console_output:
            console_handler = logging.StreamHandler()
            if self.enable_structured_logging and self.log_format == "json":
                console_handler.setFormatter(JSONFormatter(component="root"))
            else:
                console_handler.setFormatter(
                    logging.Formatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                    )
                )
            root_logger.addHandler(console_handler)
    
    def get_logger(self, component: str) -> logging.Logger:
        """
        Get or create logger for component
        
        Args:
            component: Component name
        
        Returns:
            Logger instance for component
        """
        if component not in self._loggers:
            logger = logging.getLogger(component)
            
            # Set component-specific log level if configured
            if component in self._component_log_levels:
                logger.setLevel(getattr(logging, self._component_log_levels[component]))
            else:
                logger.setLevel(getattr(logging, self.log_level))
            
            # Add custom formatter with component name
            for handler in logger.handlers:
                if self.enable_structured_logging and self.log_format == "json":
                    handler.setFormatter(JSONFormatter(component=component))
            
            self._loggers[component] = logger
        
        return self._loggers[component]
    
    def log(
        self,
        level: str,
        component: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Log structured message with context
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            component: Component name
            message: Log message
            context: Additional context dictionary
            trace_id: Distributed trace ID
            correlation_id: Request correlation ID
        """
        logger = self.get_logger(component)
        
        # Create log entry
        log_entry = LogEntry(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            level=level,
            component=component,
            message=message,
            trace_id=trace_id or 'no-trace',
            correlation_id=correlation_id or 'no-correlation',
            context=context or {}
        )
        
        # Add to in-memory buffer
        self._add_to_buffer(log_entry)
        
        # Log using standard logger with extra fields
        extra = {
            'component': component,
            'trace_id': trace_id or 'no-trace',
            'correlation_id': correlation_id or 'no-correlation'
        }
        if context:
            extra.update(context)
        
        log_level = getattr(logging, level)
        logger.log(log_level, message, extra=extra)
    
    def _add_to_buffer(self, log_entry: LogEntry) -> None:
        """Add log entry to in-memory buffer"""
        self._log_buffer.append(log_entry)
        
        # Trim buffer if it exceeds max size
        if len(self._log_buffer) > self._max_buffer_size:
            self._log_buffer = self._log_buffer[-self._max_buffer_size:]
    
    def debug(
        self,
        component_or_msg: str,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log debug message"""
        if context is None and 'extra' in kwargs:
            context = kwargs['extra']
            
        if message is None:
            msg = component_or_msg
            comp = getattr(self, "default_component", "root")
        else:
            comp = component_or_msg
            msg = message
        self.log(LogLevel.DEBUG.value, comp, msg, context, trace_id, correlation_id)
    
    def info(
        self,
        component_or_msg: str,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log info message"""
        if context is None and 'extra' in kwargs:
            context = kwargs['extra']
            
        if message is None:
            msg = component_or_msg
            comp = getattr(self, "default_component", "root")
        else:
            comp = component_or_msg
            msg = message
        self.log(LogLevel.INFO.value, comp, msg, context, trace_id, correlation_id)
        
    def warning(
        self,
        component_or_msg: str,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log warning message"""
        if context is None and 'extra' in kwargs:
            context = kwargs['extra']
            
        if message is None:
            msg = component_or_msg
            comp = getattr(self, "default_component", "root")
        else:
            comp = component_or_msg
            msg = message
        self.log(LogLevel.WARNING.value, comp, msg, context, trace_id, correlation_id)
        
    def error(
        self,
        component_or_msg: str,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log error message"""
        if context is None and 'extra' in kwargs:
            context = kwargs['extra']
            
        if message is None:
            msg = component_or_msg
            comp = getattr(self, "default_component", "root")
        else:
            comp = component_or_msg
            msg = message
        self.log(LogLevel.ERROR.value, comp, msg, context, trace_id, correlation_id)
        
    def critical(
        self,
        component_or_msg: str,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log critical message"""
        if context is None and 'extra' in kwargs:
            context = kwargs['extra']
            
        if message is None:
            msg = component_or_msg
            comp = getattr(self, "default_component", "root")
        else:
            comp = component_or_msg
            msg = message
        self.log(LogLevel.CRITICAL.value, comp, msg, context, trace_id, correlation_id)
    
    def set_log_level(self, component: str, level: str) -> None:
        """
        Set log level for specific component
        
        Args:
            component: Component name
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self._component_log_levels[component] = level
        
        # Update existing logger if it exists
        if component in self._loggers:
            self._loggers[component].setLevel(getattr(logging, level))
    
    def query_logs(
        self,
        component: Optional[str] = None,
        level: Optional[str] = None,
        trace_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100
    ) -> List[LogEntry]:
        """
        Query recent logs from in-memory buffer
        
        Args:
            component: Filter by component name
            level: Filter by log level
            trace_id: Filter by trace ID
            correlation_id: Filter by correlation ID
            limit: Maximum number of entries to return
        
        Returns:
            List of matching log entries
        """
        filtered_logs = self._log_buffer
        
        # Apply filters
        if component:
            filtered_logs = [log for log in filtered_logs if log.component == component]
        
        if level:
            filtered_logs = [log for log in filtered_logs if log.level == level]
        
        if trace_id:
            filtered_logs = [log for log in filtered_logs if log.trace_id == trace_id]
        
        if correlation_id:
            filtered_logs = [log for log in filtered_logs if log.correlation_id == correlation_id]
        
        # Return most recent entries up to limit
        return filtered_logs[-limit:]
    
    def get_log_stats(self) -> Dict[str, Any]:
        """
        Get logging statistics
        
        Returns:
            Dictionary with logging statistics
        """
        level_counts = {}
        component_counts = {}
        
        for log_entry in self._log_buffer:
            # Count by level
            level_counts[log_entry.level] = level_counts.get(log_entry.level, 0) + 1
            
            # Count by component
            component_counts[log_entry.component] = component_counts.get(log_entry.component, 0) + 1
        
        return {
            'total_logs': len(self._log_buffer),
            'buffer_size': self._max_buffer_size,
            'level_counts': level_counts,
            'component_counts': component_counts,
            'log_file_path': str(self.log_file_path),
            'log_level': self.log_level
        }


# Global logging system instance
_logging_system: Optional[LoggingSystem] = None


def initialize_logging(
    log_level: str = LogLevel.INFO.value,
    log_file_path: str = "logs/pca.log",
    enable_log_rotation: bool = True,
    log_rotation_max_bytes: int = 10 * 1024 * 1024,
    log_rotation_backup_count: int = 5,
    enable_console_output: bool = True,
    enable_structured_logging: bool = True,
    log_format: str = "json"
) -> LoggingSystem:
    """
    Initialize global logging system
    
    Args:
        log_level: Default log level
        log_file_path: Path to log file
        enable_log_rotation: Enable log rotation
        log_rotation_max_bytes: Max size before rotation
        log_rotation_backup_count: Number of backup files to keep
        enable_console_output: Enable console logging
        enable_structured_logging: Use structured JSON logging
        log_format: Log format (json or text)
    
    Returns:
        LoggingSystem instance
    """
    global _logging_system
    
    _logging_system = LoggingSystem(
        log_level=log_level,
        log_file_path=log_file_path,
        enable_log_rotation=enable_log_rotation,
        log_rotation_max_bytes=log_rotation_max_bytes,
        log_rotation_backup_count=log_rotation_backup_count,
        enable_console_output=enable_console_output,
        enable_structured_logging=enable_structured_logging,
        log_format=log_format
    )
    
    return _logging_system


def get_logging_system() -> LoggingSystem:
    """
    Get global logging system instance
    
    Returns:
        LoggingSystem instance
    
    Raises:
        RuntimeError: If logging system has not been initialized
    """
    global _logging_system
    
    if _logging_system is None:
        raise RuntimeError("Logging system has not been initialized. Call initialize_logging() first.")
    
    return _logging_system
