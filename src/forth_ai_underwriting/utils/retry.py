"""
Retry utilities for resilient API calls and operations.
"""

import asyncio
import functools
import logging
from collections.abc import Callable

from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from forth_ai_underwriting.core.exceptions import ExternalAPIError, RateLimitError

logger = logging.getLogger(__name__)


def retry_api_call(
    max_attempts: int = 3,
    wait_min: float = 1.0,
    wait_max: float = 60.0,
    wait_multiplier: float = 2.0,
    retry_on_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        ExternalAPIError,
    ),
    stop_on_exceptions: tuple[type[Exception], ...] = (
        RateLimitError,
        ValueError,
        TypeError,
    ),
):
    """
    Decorator for retrying API calls with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        wait_min: Minimum wait time between retries (seconds)
        wait_max: Maximum wait time between retries (seconds)
        wait_multiplier: Multiplier for exponential backoff
        retry_on_exceptions: Exceptions that should trigger a retry
        stop_on_exceptions: Exceptions that should stop retries immediately
    """

    def should_retry(exception):
        """Determine if we should retry based on the exception type."""
        if isinstance(exception, stop_on_exceptions):
            return False
        return isinstance(exception, retry_on_exceptions)

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=wait_multiplier, min=wait_min, max=wait_max),
        retry=retry_if_exception_type(retry_on_exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO),
    )


def retry_async_operation(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
):
    """
    Simple async retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier
        max_delay: Maximum delay between retries
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        # Last attempt failed
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"Attempt {attempt + 1} of {func.__name__} failed: {e}. "
                        f"Retrying in {current_delay} seconds..."
                    )

                    await asyncio.sleep(current_delay)
                    current_delay = min(current_delay * backoff, max_delay)

            # This should never be reached, but just in case
            raise last_exception

        return wrapper

    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern for protecting against cascading failures.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if self._should_attempt_reset():
                    self.state = "HALF_OPEN"
                else:
                    raise ExternalAPIError(
                        message="Circuit breaker is OPEN",
                        error_code="CIRCUIT_BREAKER_OPEN",
                        details={
                            "failure_count": self.failure_count,
                            "last_failure_time": self.last_failure_time,
                        },
                    )

            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception:
                self._on_failure()
                raise

        return wrapper

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt a reset."""
        if self.last_failure_time is None:
            return True

        import time

        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _on_success(self):
        """Reset the circuit breaker on successful operation."""
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self):
        """Handle failure and potentially open the circuit."""
        import time

        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )


# Pre-configured retry decorators for common scenarios
retry_forth_api = retry_api_call(
    max_attempts=3,
    wait_min=1.0,
    wait_max=30.0,
    retry_on_exceptions=(ConnectionError, TimeoutError, ExternalAPIError),
)

retry_ai_api = retry_api_call(
    max_attempts=2,
    wait_min=2.0,
    wait_max=60.0,
    retry_on_exceptions=(ConnectionError, TimeoutError, ExternalAPIError),
)

retry_database = retry_api_call(
    max_attempts=3, wait_min=0.5, wait_max=10.0, retry_on_exceptions=(ConnectionError,)
)
