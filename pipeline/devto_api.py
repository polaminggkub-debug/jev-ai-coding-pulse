"""Polite Dev.to request pacing with narrow, bounded 429 recovery."""
from datetime import timezone
from email.utils import parsedate_to_datetime
import math
import time
from urllib.error import HTTPError

SPACING_SECONDS = 1.1
MAX_RETRIES = 2
MAX_RETRY_AFTER = 60
FALLBACK_RETRY_AFTER = 30


def _retry_delay(error, now):
    headers = getattr(error, 'headers', None)
    value = (headers.get('Retry-After') or headers.get('retry-after')) if headers else None
    if value is None:
        return FALLBACK_RETRY_AFTER
    try:
        seconds = float(value)
        return max(0, seconds) if math.isfinite(seconds) else FALLBACK_RETRY_AFTER
    except (TypeError, ValueError, OverflowError):
        try:
            when = parsedate_to_datetime(str(value))
        except (TypeError, ValueError, OverflowError):
            return FALLBACK_RETRY_AFTER
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0, when.timestamp() - now)


class DevToAPI:
    """Callable HTTP adapter; inject clock and sleep to test timing without waiting."""

    def __init__(self, http_get, *, clock=None, sleep=None, spacing=SPACING_SECONDS):
        self.http_get = http_get
        self.clock = time.time if clock is None else clock
        self.sleep = time.sleep if sleep is None else sleep
        self.spacing = spacing
        self.last_request = None
        self.stopped_error = None

    def _space(self):
        now = self.clock()
        if self.last_request is not None:
            wait = self.spacing - (now - self.last_request)
            if wait > 0:
                self.sleep(wait)
        self.last_request = self.clock()

    def __call__(self, url):
        if self.stopped_error is not None:
            raise self.stopped_error
        retries = 0
        while True:
            self._space()
            try:
                return self.http_get(url)
            except HTTPError as error:
                if error.code != 429:
                    raise
                if retries >= MAX_RETRIES:
                    self.stopped_error = error
                    raise
                delay = _retry_delay(error, self.clock())
                if delay > MAX_RETRY_AFTER:
                    self.stopped_error = error
                    raise
                retries += 1
                if delay:
                    self.sleep(delay)
