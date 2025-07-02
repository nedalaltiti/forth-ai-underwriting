"""
Comprehensive observability setup with OpenTelemetry tracing and Prometheus metrics.
"""

import os
import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any

try:
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.boto3sqs import Boto3SQSInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.trace import Resource, TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.trace import Status, StatusCode

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
    from prometheus_fastapi_instrumentator import (
        Instrumentator,
    )
    from prometheus_fastapi_instrumentator import (
        metrics as prom_metrics,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # Create fallback for when Prometheus is not available
    class CollectorRegistry:
        pass


from loguru import logger

try:
    from forth_ai_underwriting.config.settings import settings
except ImportError:
    # Fallback configuration
    class MockSettings:
        app_name = "forth-ai-underwriting"
        app_version = "1.0.0"
        environment = "development"

    settings = MockSettings()


class ObservabilityConfig:
    """Configuration for observability features."""

    def __init__(self):
        self.service_name = settings.app_name.replace(" ", "-").lower()
        self.service_version = settings.app_version
        self.environment = settings.environment

        # Tracing configuration
        self.enable_tracing = (
            os.getenv("ENABLE_TRACING", "true").lower() == "true"
            and OPENTELEMETRY_AVAILABLE
        )
        self.jaeger_endpoint = os.getenv(
            "JAEGER_ENDPOINT", "http://localhost:14268/api/traces"
        )
        self.otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
        self.trace_console_export = (
            os.getenv("TRACE_CONSOLE_EXPORT", "false").lower() == "true"
        )

        # Metrics configuration
        self.enable_metrics = (
            os.getenv("ENABLE_METRICS", "true").lower() == "true"
            and PROMETHEUS_AVAILABLE
        )
        self.metrics_port = int(os.getenv("METRICS_PORT", "9090"))
        self.prometheus_endpoint = os.getenv("PROMETHEUS_ENDPOINT", "/metrics")


class CustomMetrics:
    """Custom business metrics using Prometheus."""

    def __init__(self, registry: CollectorRegistry | None = None):
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus not available, metrics disabled")
            return

        self.registry = registry or CollectorRegistry()

        # Webhook metrics
        self.webhook_requests_total = Counter(
            "webhook_requests_total",
            "Total number of webhook requests",
            ["method", "endpoint", "status"],
            registry=self.registry,
        )

        self.webhook_processing_duration = Histogram(
            "webhook_processing_duration_seconds",
            "Time spent processing webhook requests",
            ["endpoint", "status"],
            registry=self.registry,
        )

        self.webhook_payload_size = Histogram(
            "webhook_payload_size_bytes",
            "Size of webhook payloads",
            ["endpoint"],
            registry=self.registry,
        )

        # Queue metrics
        self.queue_messages_sent = Counter(
            "queue_messages_sent_total",
            "Total number of messages sent to queue",
            ["queue_name", "status"],
            registry=self.registry,
        )

        self.queue_processing_duration = Histogram(
            "queue_processing_duration_seconds",
            "Time spent processing queue messages",
            ["queue_name", "operation"],
            registry=self.registry,
        )

        self.queue_size = Gauge(
            "queue_size",
            "Current number of messages in queue",
            ["queue_name"],
            registry=self.registry,
        )

        # Validation metrics
        self.validation_checks_total = Counter(
            "validation_checks_total",
            "Total number of validation checks performed",
            ["check_type", "result"],
            registry=self.registry,
        )

        self.validation_duration = Histogram(
            "validation_duration_seconds",
            "Time spent on validation checks",
            ["check_type"],
            registry=self.registry,
        )

        # Document processing metrics
        self.document_processing_total = Counter(
            "document_processing_total",
            "Total number of documents processed",
            ["document_type", "status"],
            registry=self.registry,
        )

        self.document_processing_duration = Histogram(
            "document_processing_duration_seconds",
            "Time spent processing documents",
            ["document_type"],
            registry=self.registry,
        )

        # AI/LLM metrics
        self.llm_requests_total = Counter(
            "llm_requests_total",
            "Total number of LLM requests",
            ["provider", "model", "status"],
            registry=self.registry,
        )

        self.llm_request_duration = Histogram(
            "llm_request_duration_seconds",
            "Time spent on LLM requests",
            ["provider", "model"],
            registry=self.registry,
        )

        self.llm_tokens_used = Counter(
            "llm_tokens_used_total",
            "Total number of tokens used",
            ["provider", "model", "type"],  # type: prompt, completion
            registry=self.registry,
        )

        # Error metrics
        self.error_count = Counter(
            "errors_total",
            "Total number of errors",
            ["service", "error_type", "severity"],
            registry=self.registry,
        )


class ObservabilityManager:
    """Central manager for all observability features."""

    def __init__(self):
        self.config = ObservabilityConfig()
        self.tracer = None
        self.meter = None
        self.custom_metrics = None
        self.instrumentator = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all observability components."""
        if self._initialized:
            return

        try:
            if self.config.enable_tracing:
                self._setup_tracing()

            if self.config.enable_metrics:
                self._setup_metrics()

            self._initialized = True
            logger.info("✅ Observability initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize observability: {e}")
            # Don't raise - allow application to continue without observability

    def _setup_tracing(self) -> None:
        """Setup OpenTelemetry tracing."""
        if not OPENTELEMETRY_AVAILABLE:
            logger.warning("OpenTelemetry not available, tracing disabled")
            return

        try:
            # Create resource
            resource = Resource.create(
                {
                    "service.name": self.config.service_name,
                    "service.version": self.config.service_version,
                    "service.environment": self.config.environment,
                }
            )

            # Setup tracer provider
            trace.set_tracer_provider(TracerProvider(resource=resource))
            tracer_provider = trace.get_tracer_provider()

            # Setup exporters
            exporters = []

            # Console exporter for development
            if self.config.trace_console_export:
                exporters.append(ConsoleSpanExporter())

            # Jaeger exporter
            try:
                jaeger_exporter = JaegerExporter(
                    endpoint=self.config.jaeger_endpoint,
                    collector_endpoint=self.config.jaeger_endpoint,
                )
                exporters.append(jaeger_exporter)
                logger.info(
                    f"✅ Jaeger tracing configured: {self.config.jaeger_endpoint}"
                )
            except Exception as e:
                logger.warning(f"Failed to setup Jaeger exporter: {e}")

            # OTLP exporter
            try:
                otlp_exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint)
                exporters.append(otlp_exporter)
                logger.info(f"✅ OTLP tracing configured: {self.config.otlp_endpoint}")
            except Exception as e:
                logger.warning(f"Failed to setup OTLP exporter: {e}")

            # Add span processors
            for exporter in exporters:
                span_processor = BatchSpanProcessor(exporter)
                tracer_provider.add_span_processor(span_processor)

            # Get tracer
            self.tracer = trace.get_tracer(__name__)

            # Auto-instrument libraries
            FastAPIInstrumentor.instrument()
            HTTPXClientInstrumentor.instrument()
            Boto3SQSInstrumentor.instrument()
            SQLAlchemyInstrumentor.instrument()

            logger.info("✅ OpenTelemetry tracing setup complete")
        except Exception as e:
            logger.warning(f"Failed to setup tracing: {e}")

    def _setup_metrics(self) -> None:
        """Setup Prometheus metrics."""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus not available, metrics disabled")
            return

        try:
            # Setup custom metrics
            self.custom_metrics = CustomMetrics()

            # Setup FastAPI instrumentator
            self.instrumentator = Instrumentator(
                should_group_status_codes=True,
                should_ignore_untemplated=True,
                should_respect_env_var=True,
                should_instrument_requests_inprogress=True,
                excluded_handlers=["/metrics", "/health"],
                env_var_name="ENABLE_METRICS",
                inprogress_name="http_requests_inprogress",
                inprogress_labels=True,
            )

            # Add custom metrics
            self.instrumentator.add(
                prom_metrics.requests(
                    should_include_handler=True,
                    should_include_method=True,
                    should_include_status=True,
                )
            )

            self.instrumentator.add(
                prom_metrics.latency(
                    should_include_handler=True,
                    should_include_method=True,
                    should_include_status=True,
                )
            )

            self.instrumentator.add(
                prom_metrics.response_size(
                    should_include_handler=True,
                    should_include_method=True,
                    should_include_status=True,
                )
            )

            self.instrumentator.add(
                prom_metrics.request_size(
                    should_include_handler=True,
                    should_include_method=True,
                )
            )

            logger.info("✅ Prometheus metrics setup complete")
        except Exception as e:
            logger.warning(f"Failed to setup metrics: {e}")

    def instrument_app(self, app) -> None:
        """Instrument a FastAPI application."""
        if not self._initialized:
            self.initialize()

        if self.instrumentator:
            try:
                self.instrumentator.instrument(app)
                self.instrumentator.expose(
                    app, endpoint=self.config.prometheus_endpoint
                )
                logger.info(
                    f"✅ FastAPI instrumented with metrics endpoint: {self.config.prometheus_endpoint}"
                )
            except Exception as e:
                logger.warning(f"Failed to instrument app: {e}")

    def get_tracer(self, name: str = None):
        """Get OpenTelemetry tracer."""
        if not self._initialized:
            self.initialize()
        if OPENTELEMETRY_AVAILABLE and self.tracer:
            return trace.get_tracer(name or __name__)
        return None

    def get_custom_metrics(self) -> CustomMetrics | None:
        """Get custom metrics instance."""
        if not self._initialized:
            self.initialize()
        return self.custom_metrics


# Global observability manager instance
observability = ObservabilityManager()


def trace_function(operation_name: str = None):
    """Decorator to trace function calls."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = observability.get_tracer()
            if not tracer:
                return await func(*args, **kwargs)

            span_name = operation_name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(span_name) as span:
                try:
                    # Add function metadata
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)

                    # Execute function
                    result = await func(*args, **kwargs)

                    # Mark as successful
                    span.set_status(Status(StatusCode.OK))
                    return result

                except Exception as e:
                    # Record error
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = observability.get_tracer()
            if not tracer:
                return func(*args, **kwargs)

            span_name = operation_name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(span_name) as span:
                try:
                    # Add function metadata
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)

                    # Execute function
                    result = func(*args, **kwargs)

                    # Mark as successful
                    span.set_status(Status(StatusCode.OK))
                    return result

                except Exception as e:
                    # Record error
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        # Return appropriate wrapper based on function type
        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] = None):
    """Context manager for creating traced spans."""
    tracer = observability.get_tracer()
    if not tracer:
        yield None
        return

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise


def record_metric(
    metric_name: str,
    value: float,
    labels: dict[str, str] = None,
    metric_type: str = "counter",
) -> None:
    """Record a custom metric value."""
    try:
        metrics_obj = observability.get_custom_metrics()
        if not metrics_obj:
            return

        # Get the appropriate metric
        metric = getattr(metrics_obj, metric_name, None)
        if not metric:
            logger.warning(f"Metric not found: {metric_name}")
            return

        # Record value based on metric type
        if metric_type == "counter":
            if labels:
                metric.labels(**labels).inc(value)
            else:
                metric.inc(value)
        elif metric_type == "gauge":
            if labels:
                metric.labels(**labels).set(value)
            else:
                metric.set(value)
        elif metric_type == "histogram":
            if labels:
                metric.labels(**labels).observe(value)
            else:
                metric.observe(value)

    except Exception as e:
        logger.warning(f"Failed to record metric {metric_name}: {e}")


def time_operation(metric_name: str, labels: dict[str, str] = None):
    """Decorator to time operations and record metrics."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                record_metric(metric_name, duration, labels, "histogram")
                return result
            except Exception:
                duration = time.time() - start_time
                error_labels = {**(labels or {}), "status": "error"}
                record_metric(metric_name, duration, error_labels, "histogram")
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                record_metric(metric_name, duration, labels, "histogram")
                return result
            except Exception:
                duration = time.time() - start_time
                error_labels = {**(labels or {}), "status": "error"}
                record_metric(metric_name, duration, error_labels, "histogram")
                raise

        # Return appropriate wrapper
        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Utility functions for common patterns
def increment_counter(name: str, labels: dict[str, str] = None) -> None:
    """Increment a counter metric."""
    record_metric(name, 1.0, labels, "counter")


def set_gauge(name: str, value: float, labels: dict[str, str] = None) -> None:
    """Set a gauge metric value."""
    record_metric(name, value, labels, "gauge")


def observe_histogram(name: str, value: float, labels: dict[str, str] = None) -> None:
    """Observe a value in a histogram metric."""
    record_metric(name, value, labels, "histogram")


# Initialize observability on module import if enabled
if os.getenv("AUTO_INIT_OBSERVABILITY", "true").lower() == "true":
    try:
        observability.initialize()
    except Exception as e:
        logger.warning(f"Failed to auto-initialize observability: {e}")
