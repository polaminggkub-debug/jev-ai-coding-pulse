"""Small stdlib helpers shared by the free-source fetchers."""

import datetime as dt
import html
from html.parser import HTMLParser
import json
import time
import urllib.parse
import urllib.request

UA = "jev-reddit-pulse/1.0 (scheduled public-data fetch)"
DAY = 86400


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value):
    parser = _Text()
    parser.feed(str(value or ""))
    return html.unescape(" ".join(" ".join(parser.parts).split()))


def epoch(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.timestamp()
        except ValueError:
            return None


def in_window(value, now, days=5):
    created = epoch(value)
    return created is not None and now - days * DAY <= created <= now


def iso_utc(value):
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat().replace("+00:00", "Z")


def api_url(base, **params):
    return base + "?" + urllib.parse.urlencode(params, doseq=True)


def get_json(url, headers=None):
    request = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def safe_int(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def maybe_int(value):
    """Parse a score without turning an absent score into zero."""
    return None if value is None or value == "" else safe_int(value, None)


def call_json(http_get, url, headers=None):
    """Call injected clients that may or may not accept a headers keyword."""
    if headers is None:
        return http_get(url)
    try:
        return http_get(url, headers=headers)
    except TypeError as error:
        if "headers" not in str(error):
            raise
        return http_get(url)


def source_id(source, value):
    """Prefix IDs consistently while accepting already-normalized IDs."""
    raw = str(value or "").strip()
    prefix = source + ":"
    return raw if raw.startswith(prefix) else prefix + raw if raw else ""


def attach_context(item, source, community):
    item["source"] = source
    item["community"] = community
    return item


def source_listing(source, community, posts):
    return {"source": source, "community": community, "top": posts}


def now_epoch(value=None):
    return time.time() if value is None else float(value)
