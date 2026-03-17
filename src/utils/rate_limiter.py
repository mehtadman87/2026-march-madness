"""
Rate limiting utilities for external API calls.

- RateLimiter: Token-bucket implementation for NCAA API (5 req/sec)
- MonthlyQuotaTracker: Call counter for CBBD API (1000 calls/month)

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token-bucket rate limiter for enforcing requests-per-second limits.

    Uses threading.Lock and time.sleep so it is safe to call from within
    a running asyncio event loop (no RuntimeError).

    Requirements: 1.1, 1.3, 1.4, 1.7
    """

    def __init__(self, requests_per_second: float = 5.0) -> None:
        """
        Initialize the rate limiter.

        Args:
            requests_per_second: Maximum number of requests allowed per second.
                                 Defaults to 5.0 (NCAA API limit).

        Raises:
            ValueError: If requests_per_second is not positive.
        """
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self.requests_per_second = requests_per_second
        self._tokens: float = requests_per_second
        self._last_refill: float = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self.requests_per_second,
            self._tokens + elapsed * self.requests_per_second,
        )
        self._last_refill = now

    def acquire(self) -> None:
        """
        Acquire a token, blocking until one is available.

        Thread-safe: serializes token consumption across concurrent callers.
        Safe to call from within a running asyncio event loop.

        Requirements: 1.1, 1.2, 1.3, 1.4, 1.7
        """
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait_time = (1.0 - self._tokens) / self.requests_per_second
            time.sleep(wait_time)


class MonthlyQuotaTracker:
    """
    Tracks cumulative API calls against a monthly limit.

    Used to enforce the CBBD API 1000 calls/month free-tier limit.

    Requirements: 14.2, 14.4
    """

    def __init__(self, monthly_limit: int = 1000) -> None:
        """
        Initialize the monthly quota tracker.

        Args:
            monthly_limit: Maximum number of API calls allowed per month.
                           Defaults to 1000 (CBBD free-tier limit).
        """
        self.monthly_limit = monthly_limit
        self._call_count: int = 0

    def can_call(self) -> bool:
        """
        Check whether another API call is allowed within the monthly quota.

        Returns:
            True if the call count is below the monthly limit, False otherwise.

        Requirements: 14.2
        """
        return self._call_count < self.monthly_limit

    def record_call(self) -> None:
        """
        Record that an API call was made.

        Increments the call counter. Logs a warning when the monthly limit
        is reached so the Structured_Data_Agent can fall back to other sources.

        Requirements: 14.2, 14.4
        """
        self._call_count += 1
        if self._call_count >= self.monthly_limit:
            logger.warning(
                "CBBD monthly API limit reached (%d/%d calls used). "
                "Structured_Data_Agent will continue with remaining data sources.",
                self._call_count,
                self.monthly_limit,
            )

    @property
    def calls_used(self) -> int:
        """Return the number of API calls recorded so far."""
        return self._call_count

    @property
    def calls_remaining(self) -> int:
        """Return the number of API calls remaining in the monthly quota."""
        return max(0, self.monthly_limit - self._call_count)
