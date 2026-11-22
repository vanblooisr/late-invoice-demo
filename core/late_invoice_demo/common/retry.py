"""The one retry policy: three attempts with a growing wait, then cancel and report.

It lives here so every stage uses the same one.

This policy is for calls that are safe to repeat (a read, a create that carries an idempotency
key). A call that is not safe to repeat, such as a booking, must not be wrapped in it: a retry
after a lost reply would book twice.

Retried: connection, timeout and other transport errors from the HTTP client, and an HTTP 429
reply (rate limited). Never retried: any other HTTP status error, a malformed request or URL
(httpx.UnsupportedProtocol, httpx.LocalProtocolError), a response body that cannot be decoded
(httpx.DecodingError), StageNotBuilt, UnsupportedVerb, ValueError, MoneyError, PermissionError.
After the last failure the last exception is re-raised.

The wait between attempts grows: RETRY_FIRST_WAIT_SECONDS before the second attempt, multiplied by
RETRY_WAIT_FACTOR for each later gap (1 second, then 2 seconds, for three attempts). A 429 reply
that carries a Retry-After header holding a whole number of seconds, or an HTTP date, waits that
long instead of the growing wait (a date in the past counts as 0 seconds); a 429 without a
parseable Retry-After uses the growing wait. A 429
whose Retry-After is larger than RETRY_AFTER_CAP_SECONDS is neither waited nor retried: the HTTP
status error is re-raised at once, so the caller reports it (fail closed).
"""

import math
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TypeVar

import httpx

__all__ = [
    "RETRY_ATTEMPTS",
    "RETRY_FIRST_WAIT_SECONDS",
    "RETRY_WAIT_FACTOR",
    "RETRY_AFTER_CAP_SECONDS",
    "retry",
]

T = TypeVar("T")

RETRY_ATTEMPTS = 3
# The growing wait: the first gap, and the factor each later gap is multiplied by.
RETRY_FIRST_WAIT_SECONDS = 1.0
RETRY_WAIT_FACTOR = 2
# The longest Retry-After, in seconds, that is waited out; a longer ask is not waited and not retried.
RETRY_AFTER_CAP_SECONDS = 60.0
# A digit run with more significant digits than this is read as infinity, so it always exceeds the cap.
_MAX_SANE_DIGITS = 18


def _utc_now() -> datetime:
    """The real clock: the current moment, timezone-aware, in UTC."""
    return datetime.now(UTC)


def retry(
    fn: Callable[[], T],
    *,
    attempts: int = RETRY_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
    retry_after_cap_seconds: float = RETRY_AFTER_CAP_SECONDS,
    now: Callable[[], datetime] = _utc_now,
) -> T:
    """Call `fn` up to `attempts` times; after the last failure re-raise, so the caller cancels and reports.

    Only for a call that is safe to repeat. A call that is not (a booking) must not be wrapped in
    this policy.

    `sleep(seconds)` is called between attempts, never after the last one; the default is the real
    sleep, and tests inject their own. The wait before attempt n + 1 is
    RETRY_FIRST_WAIT_SECONDS * RETRY_WAIT_FACTOR ** (n - 1), except after a 429 whose Retry-After
    header is a whole number of seconds (ASCII digits, so "7" and "0" but not "-1", "1.5" or "soon";
    a zero-padded run is compared by value) or an HTTP date (the seconds from `now()` until then,
    0 for a date in the past; a date without a zone is read as UTC): then the wait is that number,
    provided it is at most `retry_after_cap_seconds` (default RETRY_AFTER_CAP_SECONDS): a larger
    Retry-After is neither waited nor retried, and that HTTP status error is re-raised at once, on
    any attempt. A cap that is not a finite number of at least 0 (infinity, NaN, a negative) raises
    ValueError before the first call. A Retry-After that cannot be read at all (an HTTP date with an
    absurd field included) counts as no Retry-After: the growing wait. `now` is a function returning a timezone-aware datetime; the default is the real
    UTC clock, and tests inject a fixed one. Retried: httpx connection, timeout and other transport
    errors, and httpx.HTTPStatusError with status 429. Never retried: any other HTTP status error,
    httpx.UnsupportedProtocol, httpx.LocalProtocolError, httpx.DecodingError, StageNotBuilt,
    UnsupportedVerb, ValueError, MoneyError, PermissionError.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if not _is_finite_non_negative(retry_after_cap_seconds):
        raise ValueError("retry_after_cap_seconds must be a finite number of at least 0")
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise
            asked = _retry_after_seconds(exc.response, now)
            if asked is not None and asked > retry_after_cap_seconds:
                raise
            wait = asked if asked is not None else _growing_wait(attempt)
            if attempt == attempts:
                raise
        except (httpx.UnsupportedProtocol, httpx.LocalProtocolError):
            # A bad URL or a malformed request: repeating it cannot help.
            raise
        except httpx.TransportError:
            wait = _growing_wait(attempt)
            if attempt == attempts:
                raise
        sleep(wait)
    raise AssertionError("unreachable: the last attempt returns or raises")  # pragma: no cover


def _is_finite_non_negative(value: object) -> bool:
    """True for an int or float that is finite and at least 0 (not NaN, not infinity, not negative)."""
    return isinstance(value, (int, float)) and math.isfinite(value) and value >= 0


def _growing_wait(attempt: int) -> float:
    """The wait after the failed attempt number `attempt` (1-based)."""
    return RETRY_FIRST_WAIT_SECONDS * RETRY_WAIT_FACTOR ** (attempt - 1)


def _retry_after_seconds(response: httpx.Response, now: Callable[[], datetime]) -> float | None:
    """The Retry-After header as seconds to wait, or None when absent or not understood.

    Digits only: the value, however it is padded; a run too long to be a sane wait is read as
    infinity, so it always exceeds the cap. Otherwise an HTTP date: the seconds from `now()`,
    0 when the date has passed.
    """
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    if re.fullmatch(r"[0-9]+", value) is not None:
        significant = value.lstrip("0")
        return int(significant or "0") if len(significant) <= _MAX_SANE_DIGITS else float("inf")
    try:
        moment = parsedate_to_datetime(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return max(0.0, (moment - now()).total_seconds())
    except (TypeError, ValueError, IndexError, OverflowError):
        # Any failure to read the date, an absurd field included, means no usable Retry-After.
        return None
