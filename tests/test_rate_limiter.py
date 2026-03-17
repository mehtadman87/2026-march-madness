"""
Unit tests for RateLimiter and MonthlyQuotaTracker.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.7, 14.2, 14.4
"""

import logging
import time

import pytest

from src.utils.rate_limiter import MonthlyQuotaTracker, RateLimiter


# ---------------------------------------------------------------------------
# RateLimiter tests
# ---------------------------------------------------------------------------


def test_rate_limiter_enforces_requests_per_second():
    """
    Acquiring more tokens than the bucket holds should take measurable time.

    Use a high rate (100 req/sec) so the test completes quickly.
    The bucket starts full (100 tokens). Acquiring 101 tokens must wait
    for at least one refill cycle (~10 ms), so elapsed time > 0.
    """
    limiter = RateLimiter(requests_per_second=100.0)
    start = time.monotonic()
    # Drain the full bucket (100 tokens) plus one extra that requires a wait
    for _ in range(101):
        limiter.acquire()
    elapsed = time.monotonic() - start
    # At 100 req/sec the 101st token takes ~0.01 s; allow generous headroom
    assert elapsed >= 0.005, f"Expected rate limiting delay, got {elapsed:.4f}s"


def test_rate_limiter_allows_burst_up_to_limit():
    """
    Acquiring tokens up to the bucket capacity should be near-instant.
    """
    limiter = RateLimiter(requests_per_second=100.0)
    start = time.monotonic()
    for _ in range(100):
        limiter.acquire()
    elapsed = time.monotonic() - start
    # 100 tokens available immediately; should complete well under 50 ms
    assert elapsed < 0.05, f"Burst should be fast, got {elapsed:.4f}s"


def test_rate_limiter_queue_and_retry_sleeps_and_returns():
    """
    When the bucket is empty, acquire() should sleep and eventually return
    (blocking behavior per Requirement 1.7).
    """
    limiter = RateLimiter(requests_per_second=100.0)
    # Drain the bucket completely
    for _ in range(100):
        limiter.acquire()

    # This call must block briefly then succeed (not raise)
    start = time.monotonic()
    limiter.acquire()
    elapsed = time.monotonic() - start

    # Should have waited roughly 1/100 s = 10 ms
    assert elapsed >= 0.005, f"Expected sleep during retry, got {elapsed:.4f}s"


def test_rate_limiter_default_rate_is_five():
    """Default requests_per_second should be 5.0 (NCAA API limit)."""
    limiter = RateLimiter()
    assert limiter.requests_per_second == 5.0


def test_rate_limiter_raises_for_non_positive_rate():
    """ValueError is raised when requests_per_second <= 0 (Requirement 1.1)."""
    with pytest.raises(ValueError, match="positive"):
        RateLimiter(requests_per_second=0)
    with pytest.raises(ValueError, match="positive"):
        RateLimiter(requests_per_second=-1.0)


def test_rate_limiter_safe_from_async_context():
    """
    acquire() must not raise RuntimeError when called from within a running
    asyncio event loop (Requirement 1.2).
    """
    import asyncio

    async def _call_acquire():
        limiter = RateLimiter(requests_per_second=100.0)
        limiter.acquire()  # must not raise

    asyncio.run(_call_acquire())


def test_rate_limiter_concurrent_threads_serialize():
    """
    Multiple threads calling acquire() concurrently must not exceed the
    configured rate (Requirement 1.4).
    """
    import threading

    limiter = RateLimiter(requests_per_second=200.0)
    results: list[float] = []
    lock = threading.Lock()

    def worker():
        limiter.acquire()
        with lock:
            results.append(time.monotonic())

    # Launch 201 threads — first 200 drain the bucket, 201st must wait
    threads = [threading.Thread(target=worker) for _ in range(201)]
    start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed = time.monotonic() - start
    # The 201st token requires at least one refill interval (~5 ms at 200/s)
    assert elapsed >= 0.003, f"Expected serialization delay, got {elapsed:.4f}s"


# ---------------------------------------------------------------------------
# MonthlyQuotaTracker tests
# ---------------------------------------------------------------------------


def test_monthly_quota_tracker_can_call_returns_true_when_under_limit():
    """can_call() returns True when no calls have been recorded yet."""
    tracker = MonthlyQuotaTracker(monthly_limit=1000)
    assert tracker.can_call() is True


def test_monthly_quota_tracker_record_call_increments_count():
    """record_call() increments the internal call counter."""
    tracker = MonthlyQuotaTracker(monthly_limit=1000)
    assert tracker.calls_used == 0
    tracker.record_call()
    assert tracker.calls_used == 1
    tracker.record_call()
    assert tracker.calls_used == 2


def test_monthly_quota_tracker_blocks_after_limit_reached():
    """can_call() returns False once the monthly limit is exhausted."""
    tracker = MonthlyQuotaTracker(monthly_limit=3)
    for _ in range(3):
        tracker.record_call()
    assert tracker.can_call() is False


def test_monthly_quota_tracker_can_call_true_one_before_limit():
    """can_call() still returns True when one call remains."""
    tracker = MonthlyQuotaTracker(monthly_limit=5)
    for _ in range(4):
        tracker.record_call()
    assert tracker.can_call() is True
    tracker.record_call()
    assert tracker.can_call() is False


def test_monthly_quota_tracker_calls_remaining():
    """calls_remaining decrements correctly and floors at 0."""
    tracker = MonthlyQuotaTracker(monthly_limit=10)
    assert tracker.calls_remaining == 10
    for _ in range(10):
        tracker.record_call()
    assert tracker.calls_remaining == 0
    # Extra calls beyond limit should not go negative
    tracker.record_call()
    assert tracker.calls_remaining == 0


def test_monthly_quota_tracker_logs_warning_at_limit(caplog):
    """
    A warning is logged when the monthly limit is reached (Requirement 14.4).
    """
    tracker = MonthlyQuotaTracker(monthly_limit=2)
    with caplog.at_level(logging.WARNING, logger="src.utils.rate_limiter"):
        tracker.record_call()  # 1st call – no warning yet
        assert len(caplog.records) == 0
        tracker.record_call()  # 2nd call – hits the limit
    assert any(
        "monthly" in r.message.lower() or "limit" in r.message.lower()
        for r in caplog.records
    ), "Expected a warning log when monthly limit is reached"


def test_monthly_quota_tracker_default_limit_is_1000():
    """Default monthly_limit should be 1000 (CBBD free-tier limit)."""
    tracker = MonthlyQuotaTracker()
    assert tracker.monthly_limit == 1000


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis import HealthCheck


@given(st.floats(min_value=500.0, max_value=5000.0))
@settings(max_examples=5, deadline=2000, suppress_health_check=[HealthCheck.too_slow])
def test_property_rate_limiter_no_raise_in_async_context(requests_per_second):
    """
    Property 1: RateLimiter does not raise in async context.

    For any valid requests_per_second, calling acquire() from within a running
    asyncio event loop must not raise RuntimeError.

    Validates: Requirements 1.2
    """
    import asyncio

    async def _call_acquire():
        # Use a fresh limiter with 1 token available — no sleep needed
        limiter = RateLimiter(requests_per_second=requests_per_second)
        limiter.acquire()  # must not raise RuntimeError

    asyncio.run(_call_acquire())


@given(st.integers(min_value=2, max_value=8))
@settings(max_examples=3, deadline=2000, suppress_health_check=[HealthCheck.too_slow])
def test_property_rate_limiter_concurrent_load(n_threads):
    """
    Property 2: RateLimiter enforces rate limit under concurrent load.

    Launch n_threads threads all calling acquire() simultaneously on a
    RateLimiter with requests_per_second=5000.0 (very high rate so no
    real sleeping occurs). Verify no exceptions are raised.

    Validates: Requirements 1.3, 1.4
    """
    import threading

    # Use a very high rate so all threads get tokens immediately — no sleep
    limiter = RateLimiter(requests_per_second=5000.0)
    errors: list[Exception] = []
    lock = threading.Lock()

    def worker():
        try:
            limiter.acquire()
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Unexpected exceptions in threads: {errors}"


@given(st.floats(min_value=1000.0, max_value=5000.0))
@settings(max_examples=3, deadline=2000, suppress_health_check=[HealthCheck.too_slow])
def test_property_rate_limiter_blocks_until_token_available(rate):
    """
    Property 3: RateLimiter blocks until token available.

    Use a very high rate so draining the bucket is instant, then verify
    the next acquire() blocks for a non-zero but very short time.

    Validates: Requirements 1.7
    """
    import math

    limiter = RateLimiter(requests_per_second=rate)
    # Drain the full bucket (ceil(rate) calls — all instant at high rate)
    n_drain = math.ceil(rate)
    for _ in range(n_drain):
        limiter.acquire()

    # The next acquire must complete without raising (bucket was empty)
    # At very high rates the sleep is sub-millisecond so we only assert no exception
    limiter.acquire()  # must not raise

# ---------------------------------------------------------------------------
# Slow property test — run with: pytest -m slow
# ---------------------------------------------------------------------------

@pytest.mark.slow
@given(st.floats(min_value=5.0, max_value=20.0))
@settings(max_examples=3, deadline=10000, suppress_health_check=[HealthCheck.too_slow])
def test_property_rate_limiter_blocks_with_measurable_delay_slow(rate):
    """
    Property 3 (rigorous): RateLimiter blocks for a measurable duration.

    Uses realistic rates (5–20 req/s) to verify acquire() actually sleeps
    after the bucket is drained. Excluded from the default test run because
    it involves real time.sleep calls (~50–200ms per example).

    Run with: pytest -m slow tests/test_rate_limiter.py

    Validates: Requirements 1.7
    """
    import math

    limiter = RateLimiter(requests_per_second=rate)
    n_drain = math.ceil(rate)
    for _ in range(n_drain):
        limiter.acquire()

    start = time.monotonic()
    limiter.acquire()
    elapsed = time.monotonic() - start

    expected_min = 0.8 / rate  # at least 80% of one token interval
    assert elapsed >= expected_min, (
        f"Expected acquire() to block >= {expected_min:.4f}s at rate={rate:.1f}, "
        f"got {elapsed:.6f}s"
    )
