"""Named data-quality thresholds shared by collection and classification."""

import datetime as dt
import time

SETTLED_THREAD_AGE_DAYS = 3
MIN_SETTLED_THREAD_SCORE = 10
MIN_RECENT_THREAD_COMMENTS = 5
MIN_SETTLED_COMMENT_SCORE = 0
BOT_COMMENT_AUTHORS = frozenset({"automoderator"})
REMOVED_COMMENT_BODIES = frozenset({"[deleted]", "[removed]"})
SECONDS_PER_DAY = 86400


def _timestamp(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        if isinstance(value, str) and value.strip():
            try:
                parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt.timezone.utc)
                return parsed.timestamp()
            except ValueError:
                pass
        return None


def _comment_count(post):
    value = post.get("num_comments")
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return len(post.get("comments") or [])


def thread_qualifies(post, *, now=None):
    """Apply the settled-vote or recent-comment-count gate to a thread."""
    now = time.time() if now is None else float(now)
    created = _timestamp(post.get("created_utc"))
    score = _timestamp(post.get("score")) or 0
    comments = _comment_count(post)
    if created is None:
        # Unknown-age legacy rows can pass either conservative signal.
        return score >= MIN_SETTLED_THREAD_SCORE or comments >= MIN_RECENT_THREAD_COMMENTS
    age = now - created
    if age > SETTLED_THREAD_AGE_DAYS * SECONDS_PER_DAY:
        return score >= MIN_SETTLED_THREAD_SCORE
    return comments >= MIN_RECENT_THREAD_COMMENTS


def comment_qualifies(comment, *, now=None, parent_created_utc=None):
    """Keep readable human comments and apply score only after votes settle."""
    body = str(comment.get("body") or "").strip()
    if not body or body.casefold() in REMOVED_COMMENT_BODIES:
        return False
    author = str(comment.get("author") or "").strip().casefold()
    if author in BOT_COMMENT_AUTHORS:
        return False
    now = time.time() if now is None else float(now)
    created = _timestamp(comment.get("created_utc"))
    if created is None:
        created = _timestamp(parent_created_utc)
    if created is not None and now - created > SETTLED_THREAD_AGE_DAYS * SECONDS_PER_DAY:
        score = _timestamp(comment.get("score")) or 0
        if score <= MIN_SETTLED_COMMENT_SCORE:
            return False
    return True
