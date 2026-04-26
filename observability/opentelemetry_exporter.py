"""
OpenTelemetry Exporter for PCA Tracing System

Integrates PCA's tracing system with OpenTelemetry for export to
Jaeger, Zipkin, or other OTLP-compatible backends.
"""

import os
from typing import Optional, Dict, Any
from datetime import datetime

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    trace = None
    TracerProvider = None


class OpenTelemetryExporter:
    """
    Exports PCA spans to OpenTelemetry-compatible backends
    
    Supports:
    - Jaeger (via Thrift or OTLP)
    - Zipkin (via OTLP)
    - Any OTLP-compatible backend
    - Console output for debugging
    """
    
    def __init__(
        self,
        service_name: str = "pca-agent",
        exporter_type: str = "otlp",
        endpoint: Optional[str] = None,
        enable_console: bool = False
    ):
        """
        Initialize OpenTelemetry exporter
        
        Args:
            service_name: Name of the service for tracing
            exporter_type: Type of exporter ("otlp", "jaeger", "console")
            endpoint: Endpoint URL for the exporter
            enable_console: Also export to console for debugging
        """
        if not OPENTELEMETRY_AVAILABLE:
            raise ImportError(
                "OpenTelemetry not installed. "
                "Install with: pip install opentelemetry-api opentelemetry-sdk "
                "opentelemetry-exporter-jaeger opentelemetry-exporter-otlp"
            )
        
        self.service_name = service_name
        self.exporter_type = exporter_type
        self.endpoint = endpoint or self._get_default_endpoint(exporter_type)
        self.enable_console = enable_console
        
        # Create resource with service information
        resource = Resource.create({
            "service.name": service_name,
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development")
        })
        
        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource)
        
        # Add span processors
        self._setup_exporters()
        
        # Set as global tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        
        # Get tracer
        self.tracer = trace.get_tracer(__name__)
    
    def _get_default_endpoint(self, exporter_type: str) -> str:
        """Get default endpoint for exporter type"""
        defaults = {
            "otlp": os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
            "jaeger": os.getenv("JAEGER_ENDPOINT", "localhost:6831"),
        }
        return defaults.get(exporter_type, "http://localhost:4317")
    
    def _setup_exporters(self):
        """Setup span exporters based on configuration"""
        # Main exporter
        if self.exporter_type == "otlp":
            exporter = OTLPSpanExporter(endpoint=self.endpoint)
        elif self.exporter_type == "jaeger":
            exporter = JaegerExporter(
                agent_host_name=self.endpoint.split(":")[0],
                agent_port=int(self.endpoint.split(":")[1]) if ":" in self.endpoint else 6831,
            )
        else:
            exporter = ConsoleSpanExporter()
        
        self.tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        
        # Console exporter for debugging
        if self.enable_console:
            console_exporter = ConsoleSpanExporter()
            self.tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))
    
    def export_span(self, pca_span) -> None:
        """
        Export a PCA span to OpenTelemetry
        
        Args:
            pca_span: Span object from PCA tracing system
        """
        # Convert PCA span to OpenTelemetry span
        with self.tracer.start_as_current_span(
            pca_span.operation_name,
            start_time=int(pca_span.start_time.timestamp() * 1e9)  # Convert to nanoseconds
        ) as otel_span:
            # Set span attributes from tags
            for key, value in pca_span.tags.items():
                otel_span.set_attribute(key, value)
            
            # Add span events from logs
            for log in pca_span.logs:
                timestamp = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00'))
                otel_span.add_event(
                    log['message'],
                    timestamp=int(timestamp.timestamp() * 1e9),
                    attributes={k: v for k, v in log.items() if k != 'message' and k != 'timestamp'}
                )
            
            # Set span status
            if pca_span.status == "error":
                otel_span.set_status(trace.Status(trace.StatusCode.ERROR))
            else:
                otel_span.set_status(trace.Status(trace.StatusCode.OK))
    
    def shutdown(self):
        """Shutdown the exporter and flush remaining spans"""
        self.tracer_provider.shutdown()


def create_opentelemetry_exporter(
    service_name: str = "pca-agent",
    exporter_type: Optional[str] = None,
    endpoint: Optional[str] = None,
    enable_console: bool = False
) -> Optional[OpenTelemetryExporter]:
    """
    Create OpenTelemetry exporter from configuration
    
    Args:
        service_name: Name of the service
        exporter_type: Type of exporter (otlp, jaeger, console)
        endpoint: Endpoint URL
        enable_console: Enable console output
    
    Returns:
        OpenTelemetryExporter instance or None if not available
    """
    if not OPENTELEMETRY_AVAILABLE:
        return None
    
    # Auto-detect exporter type from environment
    if exporter_type is None:
        if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            exporter_type = "otlp"
        elif os.getenv("JAEGER_ENDPOINT"):
            exporter_type = "jaeger"
        else:
            exporter_type = "console"
    
    try:
        return OpenTelemetryExporter(
            service_name=service_name,
            exporter_type=exporter_type,
            endpoint=endpoint,
            enable_console=enable_console
        )
    except Exception as e:
        print(f"Failed to create OpenTelemetry exporter: {e}")
        return None
