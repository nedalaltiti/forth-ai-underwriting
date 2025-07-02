"""
Comprehensive error handling with specific exception catching and observability.
"""

import json
import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any

import httpx
from botocore.exceptions import BotoCoreError
from botocore.exceptions import ClientError as AWSClientError
from forth_ai_underwriting.core.exceptions import (
    AIParsingError,
    BaseUnderwritingException,
    ConfigurationError,
    DatabaseError,
    DocumentProcessingError,
    ExternalAPIError,
    ValidationError,
)
from forth_ai_underwriting.core.observability import increment_counter, trace_span
from loguru import logger
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError


class ErrorClassifier:
    """Classifies errors into categories for proper handling."""

    # Expected AWS exceptions
    AWS_EXCEPTIONS = (
        AWSClientError,
        BotoCoreError,
        ConnectionError,
    )

    # Expected HTTP/API exceptions
    HTTP_EXCEPTIONS = (
        httpx.HTTPError,
        httpx.RequestError,
        httpx.HTTPStatusError,
        httpx.TimeoutException,
        httpx.ConnectError,
    )

    # Expected JSON/Data exceptions
    JSON_EXCEPTIONS = (
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
    )

    # Expected validation exceptions
    VALIDATION_EXCEPTIONS = (
        PydanticValidationError,
        ValidationError,
        TypeError,
    )

    # Expected database exceptions
    DATABASE_EXCEPTIONS = (
        SQLAlchemyError,
        DatabaseError,
    )

    # Expected business logic exceptions
    BUSINESS_EXCEPTIONS = (
        BaseUnderwritingException,
        ValidationError,
        AIParsingError,
        DocumentProcessingError,
        ExternalAPIError,
        ConfigurationError,
    )

    @classmethod
    def classify_error(cls, error: Exception) -> str:
        """Classify an error into a category."""
        if isinstance(error, cls.AWS_EXCEPTIONS):
            return "aws"
        elif isinstance(error, cls.HTTP_EXCEPTIONS):
            return "http"
        elif isinstance(error, cls.JSON_EXCEPTIONS):
            return "json"
        elif isinstance(error, cls.VALIDATION_EXCEPTIONS):
            return "validation"
        elif isinstance(error, cls.DATABASE_EXCEPTIONS):
            return "database"
        elif isinstance(error, cls.BUSINESS_EXCEPTIONS):
            return "business"
        else:
            return "unexpected"


class ErrorContext:
    """Context for error handling with metadata."""

    def __init__(
        self, operation: str, component: str, metadata: dict[str, Any] | None = None
    ):
        self.operation = operation
        self.component = component
        self.metadata = metadata or {}
        self.start_time = time.time()

    def get_context(self) -> dict[str, Any]:
        """Get error context as dictionary."""
        return {
            "operation": self.operation,
            "component": self.component,
            "duration_ms": int((time.time() - self.start_time) * 1000),
            "metadata": self.metadata,
        }


def handle_expected_errors(
    operation: str,
    component: str = "unknown",
    re_raise: bool = True,
    fallback_value: Any = None,
):
    """
    Decorator to handle expected exceptions with proper classification and observability.

    Args:
        operation: Name of the operation being performed
        component: Component/service name
        re_raise: Whether to re-raise exceptions after handling
        fallback_value: Value to return if exception is caught and not re-raised
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            context = ErrorContext(operation, component)

            with trace_span(f"{component}.{operation}", context.get_context()) as span:
                try:
                    result = await func(*args, **kwargs)

                    # Record success metric
                    increment_counter(
                        "operation_success_total",
                        {"operation": operation, "component": component},
                    )

                    return result

                except json.JSONDecodeError as e:
                    _handle_json_error(e, context, span)
                    if re_raise:
                        raise ExternalAPIError(
                            message=f"Invalid JSON response in {operation}",
                            error_code="JSON_DECODE_ERROR",
                            details={"operation": operation, "error": str(e)},
                        )
                    return fallback_value

                except httpx.HTTPStatusError as e:
                    _handle_http_status_error(e, context, span)
                    if re_raise:
                        raise ExternalAPIError(
                            message=f"HTTP {e.response.status_code} error in {operation}",
                            error_code="HTTP_STATUS_ERROR",
                            details={
                                "operation": operation,
                                "status_code": e.response.status_code,
                                "url": str(e.request.url),
                                "response": e.response.text[:1000]
                                if hasattr(e.response, "text")
                                else None,
                            },
                        )
                    return fallback_value

                except httpx.RequestError as e:
                    _handle_http_request_error(e, context, span)
                    if re_raise:
                        raise ExternalAPIError(
                            message=f"HTTP request error in {operation}",
                            error_code="HTTP_REQUEST_ERROR",
                            details={"operation": operation, "error": str(e)},
                        )
                    return fallback_value

                except AWSClientError as e:
                    _handle_aws_client_error(e, context, span)
                    if re_raise:
                        raise ExternalAPIError(
                            message=f"AWS error in {operation}",
                            error_code="AWS_CLIENT_ERROR",
                            details={
                                "operation": operation,
                                "service": e.response.get("Error", {}).get(
                                    "Code", "Unknown"
                                ),
                                "error": str(e),
                            },
                        )
                    return fallback_value

                except BotoCoreError as e:
                    _handle_aws_core_error(e, context, span)
                    if re_raise:
                        raise ExternalAPIError(
                            message=f"AWS core error in {operation}",
                            error_code="AWS_CORE_ERROR",
                            details={"operation": operation, "error": str(e)},
                        )
                    return fallback_value

                except PydanticValidationError as e:
                    _handle_validation_error(e, context, span)
                    if re_raise:
                        raise ValidationError(
                            message=f"Validation error in {operation}",
                            error_code="VALIDATION_ERROR",
                            details={"operation": operation, "errors": e.errors()},
                        )
                    return fallback_value

                except SQLAlchemyError as e:
                    _handle_database_error(e, context, span)
                    if re_raise:
                        raise DatabaseError(
                            message=f"Database error in {operation}",
                            error_code="DATABASE_ERROR",
                            details={"operation": operation, "error": str(e)},
                        )
                    return fallback_value

                except BaseUnderwritingException:
                    # Business exceptions are already properly structured
                    increment_counter(
                        "operation_error_total",
                        {
                            "operation": operation,
                            "component": component,
                            "error_type": "business",
                        },
                    )
                    raise

                except Exception as e:
                    # Unexpected exceptions - let them crash with proper observability
                    _handle_unexpected_error(e, context, span)
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            context = ErrorContext(operation, component)

            with trace_span(f"{component}.{operation}", context.get_context()) as span:
                try:
                    result = func(*args, **kwargs)

                    # Record success metric
                    increment_counter(
                        "operation_success_total",
                        {"operation": operation, "component": component},
                    )

                    return result

                except json.JSONDecodeError as e:
                    _handle_json_error(e, context, span)
                    if re_raise:
                        raise ExternalAPIError(
                            message=f"Invalid JSON response in {operation}",
                            error_code="JSON_DECODE_ERROR",
                            details={"operation": operation, "error": str(e)},
                        )
                    return fallback_value

                except httpx.HTTPStatusError as e:
                    _handle_http_status_error(e, context, span)
                    if re_raise:
                        raise ExternalAPIError(
                            message=f"HTTP {e.response.status_code} error in {operation}",
                            error_code="HTTP_STATUS_ERROR",
                            details={
                                "operation": operation,
                                "status_code": e.response.status_code,
                                "url": str(e.request.url),
                            },
                        )
                    return fallback_value

                except httpx.RequestError as e:
                    _handle_http_request_error(e, context, span)
                    if re_raise:
                        raise ExternalAPIError(
                            message=f"HTTP request error in {operation}",
                            error_code="HTTP_REQUEST_ERROR",
                            details={"operation": operation, "error": str(e)},
                        )
                    return fallback_value

                except AWSClientError as e:
                    _handle_aws_client_error(e, context, span)
                    if re_raise:
                        raise ExternalAPIError(
                            message=f"AWS error in {operation}",
                            error_code="AWS_CLIENT_ERROR",
                            details={
                                "operation": operation,
                                "service": e.response.get("Error", {}).get(
                                    "Code", "Unknown"
                                ),
                                "error": str(e),
                            },
                        )
                    return fallback_value

                except BotoCoreError as e:
                    _handle_aws_core_error(e, context, span)
                    if re_raise:
                        raise ExternalAPIError(
                            message=f"AWS core error in {operation}",
                            error_code="AWS_CORE_ERROR",
                            details={"operation": operation, "error": str(e)},
                        )
                    return fallback_value

                except PydanticValidationError as e:
                    _handle_validation_error(e, context, span)
                    if re_raise:
                        raise ValidationError(
                            message=f"Validation error in {operation}",
                            error_code="VALIDATION_ERROR",
                            details={"operation": operation, "errors": e.errors()},
                        )
                    return fallback_value

                except SQLAlchemyError as e:
                    _handle_database_error(e, context, span)
                    if re_raise:
                        raise DatabaseError(
                            message=f"Database error in {operation}",
                            error_code="DATABASE_ERROR",
                            details={"operation": operation, "error": str(e)},
                        )
                    return fallback_value

                except BaseUnderwritingException:
                    # Business exceptions are already properly structured
                    increment_counter(
                        "operation_error_total",
                        {
                            "operation": operation,
                            "component": component,
                            "error_type": "business",
                        },
                    )
                    raise

                except Exception as e:
                    # Unexpected exceptions - let them crash with proper observability
                    _handle_unexpected_error(e, context, span)
                    raise

        # Return appropriate wrapper based on function type
        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _handle_json_error(
    error: json.JSONDecodeError, context: ErrorContext, span
) -> None:
    """Handle JSON decode errors."""
    logger.warning(
        "JSON decode error",
        extra={
            **context.get_context(),
            "error": str(error),
            "error_type": "json_decode",
            "line": error.lineno,
            "column": error.colno,
        },
    )

    increment_counter(
        "operation_error_total",
        {
            "operation": context.operation,
            "component": context.component,
            "error_type": "json",
        },
    )

    if span:
        span.set_attribute("error.type", "json_decode")
        span.set_attribute("error.line", error.lineno)
        span.set_attribute("error.column", error.colno)


def _handle_http_status_error(
    error: httpx.HTTPStatusError, context: ErrorContext, span
) -> None:
    """Handle HTTP status errors."""
    logger.warning(
        "HTTP status error",
        extra={
            **context.get_context(),
            "error": str(error),
            "error_type": "http_status",
            "status_code": error.response.status_code,
            "url": str(error.request.url),
            "method": error.request.method,
        },
    )

    increment_counter(
        "operation_error_total",
        {
            "operation": context.operation,
            "component": context.component,
            "error_type": "http_status",
            "status_code": str(error.response.status_code),
        },
    )

    if span:
        span.set_attribute("error.type", "http_status")
        span.set_attribute("http.status_code", error.response.status_code)
        span.set_attribute("http.url", str(error.request.url))
        span.set_attribute("http.method", error.request.method)


def _handle_http_request_error(
    error: httpx.RequestError, context: ErrorContext, span
) -> None:
    """Handle HTTP request errors."""
    logger.warning(
        "HTTP request error",
        extra={
            **context.get_context(),
            "error": str(error),
            "error_type": "http_request",
        },
    )

    increment_counter(
        "operation_error_total",
        {
            "operation": context.operation,
            "component": context.component,
            "error_type": "http_request",
        },
    )

    if span:
        span.set_attribute("error.type", "http_request")


def _handle_aws_client_error(
    error: AWSClientError, context: ErrorContext, span
) -> None:
    """Handle AWS client errors."""
    error_code = error.response.get("Error", {}).get("Code", "Unknown")

    logger.warning(
        "AWS client error",
        extra={
            **context.get_context(),
            "error": str(error),
            "error_type": "aws_client",
            "aws_error_code": error_code,
            "service": error.response.get("Error", {}).get("Service", "Unknown"),
        },
    )

    increment_counter(
        "operation_error_total",
        {
            "operation": context.operation,
            "component": context.component,
            "error_type": "aws_client",
            "aws_error_code": error_code,
        },
    )

    if span:
        span.set_attribute("error.type", "aws_client")
        span.set_attribute("aws.error_code", error_code)


def _handle_aws_core_error(error: BotoCoreError, context: ErrorContext, span) -> None:
    """Handle AWS core errors."""
    logger.warning(
        "AWS core error",
        extra={**context.get_context(), "error": str(error), "error_type": "aws_core"},
    )

    increment_counter(
        "operation_error_total",
        {
            "operation": context.operation,
            "component": context.component,
            "error_type": "aws_core",
        },
    )

    if span:
        span.set_attribute("error.type", "aws_core")


def _handle_validation_error(
    error: PydanticValidationError, context: ErrorContext, span
) -> None:
    """Handle validation errors."""
    logger.warning(
        "Validation error",
        extra={
            **context.get_context(),
            "error": str(error),
            "error_type": "validation",
            "validation_errors": error.errors(),
        },
    )

    increment_counter(
        "operation_error_total",
        {
            "operation": context.operation,
            "component": context.component,
            "error_type": "validation",
        },
    )

    if span:
        span.set_attribute("error.type", "validation")
        span.set_attribute("validation.error_count", len(error.errors()))


def _handle_database_error(error: SQLAlchemyError, context: ErrorContext, span) -> None:
    """Handle database errors."""
    logger.error(
        "Database error",
        extra={**context.get_context(), "error": str(error), "error_type": "database"},
    )

    increment_counter(
        "operation_error_total",
        {
            "operation": context.operation,
            "component": context.component,
            "error_type": "database",
        },
    )

    if span:
        span.set_attribute("error.type", "database")


def _handle_unexpected_error(error: Exception, context: ErrorContext, span) -> None:
    """Handle unexpected errors with detailed logging."""
    logger.error(
        "Unexpected error - this should be investigated",
        extra={
            **context.get_context(),
            "error": str(error),
            "error_type": "unexpected",
            "exception_class": error.__class__.__name__,
            "exception_module": error.__class__.__module__,
        },
        exc_info=True,
    )

    increment_counter(
        "operation_error_total",
        {
            "operation": context.operation,
            "component": context.component,
            "error_type": "unexpected",
            "exception_class": error.__class__.__name__,
        },
    )

    if span:
        span.set_attribute("error.type", "unexpected")
        span.set_attribute("error.unexpected", True)
        span.set_attribute("exception.class", error.__class__.__name__)


@contextmanager
def error_boundary(
    operation: str,
    component: str = "unknown",
    fallback_value: Any = None,
    suppress_errors: bool = False,
):
    """
    Context manager for creating error boundaries around code blocks.

    Args:
        operation: Name of the operation being performed
        component: Component/service name
        fallback_value: Value to return if exception is caught and suppressed
        suppress_errors: Whether to suppress exceptions and return fallback_value
    """
    context = ErrorContext(operation, component)

    try:
        with trace_span(f"{component}.{operation}", context.get_context()):
            yield

            # Record success metric
            increment_counter(
                "operation_success_total",
                {"operation": operation, "component": component},
            )

    except Exception as e:
        error_category = ErrorClassifier.classify_error(e)

        logger.error(
            f"Error in {operation}",
            extra={
                **context.get_context(),
                "error": str(e),
                "error_category": error_category,
                "exception_class": e.__class__.__name__,
            },
            exc_info=not suppress_errors,
        )

        increment_counter(
            "operation_error_total",
            {
                "operation": operation,
                "component": component,
                "error_type": error_category,
            },
        )

        if suppress_errors:
            return fallback_value
        else:
            raise


# Convenience decorators for common patterns
def handle_json_errors(operation: str, component: str = "json_parser"):
    """Decorator specifically for JSON parsing operations."""
    return handle_expected_errors(operation, component, re_raise=True)


def handle_http_errors(operation: str, component: str = "http_client"):
    """Decorator specifically for HTTP operations."""
    return handle_expected_errors(operation, component, re_raise=True)


def handle_aws_errors(operation: str, component: str = "aws_client"):
    """Decorator specifically for AWS operations."""
    return handle_expected_errors(operation, component, re_raise=True)


def handle_database_errors(operation: str, component: str = "database"):
    """Decorator specifically for database operations."""
    return handle_expected_errors(operation, component, re_raise=True)
