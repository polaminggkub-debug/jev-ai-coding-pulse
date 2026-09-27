"""Normalize source labels, community names, and source-prefixed identities."""

from urllib.parse import urlsplit

SOURCES = frozenset({"reddit", "hn", "github", "bluesky", "devto", "lobsters"})
SOURCE_ALIASES = {"hacker news": "hn", "dev.to": "devto"}


def source_name(value=None):
    """Return a supported lowercase source name, defaulting legacy rows to Reddit."""
    source = str(value or "reddit").strip().casefold()
    source = SOURCE_ALIASES.get(source, source)
    return source if source in SOURCES else "reddit"


def prefixed_id(source, value):
    """Prefix an identity exactly once while preserving its native suffix."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    prefix = source_name(source) + ":"
    return raw if raw.startswith(prefix) else prefix + raw


def source_from_id(value):
    """Recognize a source prefix on a previously normalized identity."""
    prefix, separator, _ = str(value or "").partition(":")
    return source_name(prefix) if separator and prefix in SOURCES else None


def community_from_url(url):
    """Recover a Reddit community from a legacy permalink when possible."""
    parts = [part for part in urlsplit(str(url or "")).path.split("/") if part]
    if len(parts) > 1 and parts[0].casefold() == "r":
        return parts[1]
    return ""


def normalize_item(row, fallback_source="reddit", fallback_community=""):
    """Add stable source/community metadata and normalize an item's identity."""
    result = dict(row)
    source = source_name(result.get("source") or source_from_id(result.get("id")) or fallback_source)
    community = (result.get("community") or result.get("sub") or fallback_community
                 or community_from_url(result.get("thread_url") or result.get("link")))
    if not community:
        community = {"reddit": "Reddit", "hn": "HN", "github": "GitHub",
                     "bluesky": "Bluesky", "devto": "Dev.to", "lobsters": "Lobsters"}[source]
    result["source"] = source
    result["community"] = str(community)
    result["id"] = prefixed_id(source, result.get("id") or result.get("comment_id"))
    if source == "reddit":
        result.setdefault("sub", str(community).removeprefix("r/"))
    return result


def normalize_judgment(row, item=None, fallback_source=None):
    """Normalize a decision key using its item, while leaving stored rows untouched."""
    result = dict(row)
    source = ((item or {}).get("source") or source_from_id(result.get("id"))
              or fallback_source or "reddit")
    result["id"] = prefixed_id(source, result.get("id"))
    result["source"] = source_name(source)
    if item:
        result["community"] = normalize_item(item, source).get("community", "")
    else:
        result["community"] = normalize_item(result, source).get("community", "")
    return result
