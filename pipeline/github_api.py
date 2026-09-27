"""GitHub request budget shared by every repository in one collection run."""

try:
    from .source_utils import call_json
except ImportError:
    from source_utils import call_json

MAX_CALLS = 800
RESERVE = 100


class BudgetExhausted(RuntimeError):
    """Raised when another GitHub request would consume the protected reserve."""


def _rate_limited(error):
    status = getattr(error, 'code', getattr(error, 'status', None))
    headers = getattr(error, 'headers', None)
    remaining = headers.get('X-RateLimit-Remaining') if headers else None
    if status == 429 or str(remaining) == '0':
        return True
    if status != 403:
        return False
    details = [str(error), str(getattr(error, 'reason', ''))]
    read = getattr(error, 'read', None)
    if callable(read):
        try:
            body = read()
            details.append(body.decode('utf-8', 'replace') if isinstance(body, bytes) else str(body))
        except Exception:
            pass
    return 'rate limit' in ' '.join(details).casefold()


class GitHubAPI:
    """Count attempted requests and stop before GitHub's protected API reserve."""

    def __init__(self, http_get, headers, max_calls=MAX_CALLS, reserve=RESERVE):
        self.http_get = http_get
        self.headers = headers
        self.max_calls = max_calls
        self.reserve = reserve
        self.calls = 0
        self.remaining = None
        self.stopped = False
        self.stop_reason = None
        self.started = False

    def start(self):
        if self.started:
            return
        self.started = True
        self.calls += 1
        try:
            response = call_json(self.http_get, 'https://api.github.com/rate_limit', self.headers)
            self.remaining = int(response['resources']['core']['remaining'])
        except Exception as error:
            self.stopped = True
            if _rate_limited(error):
                self.stop_reason = 'rate limit reached'
                raise BudgetExhausted('GitHub rate limit reached') from error
            self.stop_reason = 'quota unavailable'
            raise BudgetExhausted('Could not read GitHub request quota') from error
        if self.remaining < 0:
            self.stopped = True
            self.stop_reason = 'invalid quota response'
            raise BudgetExhausted('GitHub quota response was invalid')

    def get(self, url):
        if not self.started:
            self.start()
        if self.stopped:
            raise BudgetExhausted('GitHub request budget stopped')
        if self.calls >= self.max_calls:
            self.stopped = True
            self.stop_reason = 'request cap reached'
            raise BudgetExhausted('GitHub request cap reached')
        if self.remaining <= self.reserve:
            self.stopped = True
            self.stop_reason = 'reserve reached'
            raise BudgetExhausted('GitHub request reserve reached')
        self.calls += 1
        self.remaining -= 1
        try:
            return call_json(self.http_get, url, self.headers)
        except Exception as error:
            if _rate_limited(error):
                self.stopped = True
                self.stop_reason = 'rate limit reached'
                raise BudgetExhausted('GitHub rate limit reached') from error
            raise
