"""Choose and cache Jev's versioned ``worth reading`` decisions."""
import datetime as dt
import hashlib
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

try:
    from . import store
    from .source_identity import normalize_item, source_name
except ImportError:
    import store
    from source_identity import normalize_item, source_name

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MAX_DAILY_CALLS = 60
QUESTION_VERSION = "reads-v1"
QUESTION = {
    "type": "choice",
    "instructions": "Answer yes or no: Is this thread worth reading for a developer deciding which AI coding model or tool to use (real experience, comparisons, regressions, tips — not memes or news reposts)?",
    "criteria": {
        "yes": "Worth reading: it offers useful developer experience, comparison, regression, or practical advice about an AI coding model or tool.",
        "no": "Not worth reading: it is mostly a meme, news repost, or lacks useful developer experience about an AI coding model or tool.",
    },
}
SOURCE_ICONS = {"reddit": "🔴", "hn": "🟧", "github": "🐙",
                "bluesky": "🦋", "devto": "✍️", "lobsters": "🦞"}


def _number(value, default=None):
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError, OverflowError):
        return default


def _timestamp(value):
    if value in (None, ""):
        return None
    try:
        return store.timestamp(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _thread_url(row, source):
    value = row.get("thread_url") or row.get("link") or ""
    if not value:
        return ""
    parts = urlsplit(str(value))
    path = parts.path.rstrip("/")
    if source == "reddit" and not row.get("thread_url"):
        segments = [part for part in path.split("/") if part]
        if "comments" in segments:
            index = segments.index("comments")
            segments = segments[:index + (3 if len(segments) > index + 2 else 2)]
            path = "/" + "/".join(segments)
    query = parts.query if source == "hn" else ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def _thread_key(row, source, community, url, day):
    if url:
        identity = url
    else:
        identity = "|".join((community.casefold(), str(row.get("thread") or "").casefold(), day))
    return f"{source}|{identity}"


def _thread_time(row):
    return _timestamp(row.get("thread_created_utc") or row.get("parent_created_utc")
                      or row.get("post_created_utc") or row.get("created_utc"))


def _group_rows(rows):
    groups = {}
    for original in rows:
        row = normalize_item(original)
        source = source_name(row.get("source"))
        community = str(row.get("community") or row.get("sub") or source)
        created = _thread_time(row)
        if created is None:
            continue
        day = store.date(row.get("thread_created_utc") or row.get("parent_created_utc")
                         or row.get("post_created_utc") or row.get("created_utc"))
        url = _thread_url(row, source)
        key = _thread_key(row, source, community, url, day)
        group = groups.setdefault(key, {"key": key, "source": source, "community": community,
                                        "url": url, "rows": [], "pairs": set(),
                                        "times": [], "days": []})
        pair = (row.get("id"), row.get("subject"))
        if pair in group["pairs"]:
            continue
        group["pairs"].add(pair)
        group["rows"].append(row)
        group["times"].append(created)
        group["days"].append(day)
    return list(groups.values())


def _engagement(group):
    rows = group["rows"]
    score = next((_number(row.get("thread_score")) for row in rows
                  if _number(row.get("thread_score")) is not None), None)
    if score is None:
        score = next((_number(row.get("score")) for row in rows if row.get("kind") == "post"
                      and _number(row.get("score")) is not None), 0)
    comments = next((_number(row.get("thread_comments")) for row in rows
                     if _number(row.get("thread_comments")) is not None), None)
    if comments is None:
        comments = len({row.get("id") for row in rows if row.get("kind") == "comment"})
    return max(0, score) + max(0, comments)


def _percentile(values, value):
    lower = sum(candidate < value for candidate in values)
    equal = sum(candidate == value for candidate in values)
    return (lower + equal / 2) / len(values) if values else 0.5


def _counts(rows):
    counts = {label: 0 for label in (*store.LABELS, "opinions")}
    for row in rows:
        label = row.get("label")
        if label in store.LABELS:
            counts[label] += 1
            counts["opinions"] += label != "no_opinion"
    return counts


def _popular_comment(rows):
    comments = {}
    for row in rows:
        if row.get("kind") != "comment" or not row.get("text"):
            continue
        comment = dict(row)
        key = str(row.get("id") or row.get("link") or "")
        if key not in comments or _comment_score(comment) > _comment_score(comments[key]):
            comments[key] = comment
    return max(comments.values(), key=lambda row: (_comment_score(row),
               str(row.get("id") or "")), default=None)


def _comment_score(row):
    score = _number(row.get("score"), -1)
    return -1 if score is None else score


def _candidate(group, as_of):
    rows = group["rows"]
    counts = _counts(rows)
    title = next((str(row.get("thread") or "").strip() for row in rows if row.get("thread")), "")
    if not title or not group["url"]:
        return None
    times = group["times"]
    thread_time = min(times)
    if not as_of - 30 * 86400 <= thread_time <= as_of:
        return None
    day = min(group["days"])
    subjects = {}
    for row in rows:
        name = str(row.get("subject") or "").strip()
        if name:
            subjects[name] = subjects.get(name, 0) + (row.get("label") != "no_opinion")
    models = sorted(subjects, key=lambda name: (-subjects[name], name.casefold()))
    comment = _popular_comment(rows)
    score = _number(next((row.get("thread_score") for row in rows
                          if row.get("thread_score") is not None), None))
    if score is None:
        score = _number(next((row.get("score") for row in rows if row.get("kind") == "post"), None))
    comments = _number(next((row.get("thread_comments") for row in rows
                             if row.get("thread_comments") is not None), None))
    if comments is None:
        comments = len({row.get("id") for row in rows if row.get("kind") == "comment"})
    judged = sum(counts[label] for label in store.LABELS)
    heated = (judged > 0 and counts["praise"] / judged >= 0.3 and
              counts["complaint"] / judged >= 0.3)
    if heated:
        label = "🔥 Heated debate"
    elif counts["praise"] > counts["complaint"]:
        label = "👍 People love it"
    elif counts["complaint"] > counts["praise"]:
        label = "👎 People are angry"
    else:
        label = "💬 Mixed reactions"
    digest = hashlib.sha256(group["key"].encode("utf-8")).hexdigest()[:24]
    return {"id": f"{group['source']}:reads:{digest}", "source": group["source"],
            "source_icon": SOURCE_ICONS.get(group["source"], "💬"),
            "community": group["community"], "url": group["url"], "title": title,
            "date": day, "score": score, "comments": comments, "models": models,
            "counts": counts, "heat": ((counts["praise"] + counts["complaint"]) / judged
                                         if judged else 0.0),
            "label": label, "popular_comment": comment, "engagement": _engagement(group),
            "rank_score": 0.0, "eligible": counts["opinions"] >= 5,
            "opinions": counts["opinions"], "rows": rows}


def ranked_candidates(rows, now=None):
    as_of = time.time() if now is None else store.timestamp(now)
    groups = _group_rows(rows)
    threads = [candidate for group in groups if (candidate := _candidate(group, as_of))]
    communities = {}
    for candidate in threads:
        key = (candidate["source"], candidate["community"])
        communities.setdefault(key, []).append(candidate["engagement"])
    for candidate in threads:
        key = (candidate["source"], candidate["community"])
        percentile = _percentile(communities[key], candidate["engagement"])
        candidate["engagement_percentile"] = percentile
        candidate["rank_score"] = percentile * candidate["heat"]
    candidates = [candidate for candidate in threads if candidate["eligible"]]
    return sorted(candidates, key=lambda item: (-item["rank_score"], item["date"], item["id"]))


def curate(data_dir=DATA, decide_fn=None, *, now=None, max_calls=MAX_DAILY_CALLS):
    """Ask once per candidate and persist a 60-call-per-UTC-day attempt cap."""
    try:
        from .curator_decisions import curate as curate_decisions
    except ImportError:
        from curator_decisions import curate as curate_decisions
    return curate_decisions(data_dir, decide_fn, now=now, max_calls=max_calls)


def _story_card(candidate):
    comment = candidate["popular_comment"]
    popular = None
    if comment:
        text = " ".join(str(comment.get("text") or "").split())
        popular = {"text": text[:180], "score": _number(comment.get("score")),
                   "url": comment.get("link") or ""}
    public = {key: candidate[key] for key in ("id", "source", "source_icon", "community", "url",
              "title", "date", "score", "comments", "models", "counts", "heat", "label", "rank_score")}
    public["popular_comment"] = popular
    return public


def reads_payload(data_dir=DATA, *, now=None):
    """Return the offline page payload: up to ten accepted threads for each day."""
    as_of = time.time() if now is None else store.timestamp(now)
    candidates = ranked_candidates(store.load_mentions(data_dir), as_of)
    try:
        from .curator_decisions import read_answer_index
    except ImportError:
        from curator_decisions import read_answer_index
    answers = read_answer_index(data_dir)
    accepted = [candidate for candidate in candidates
                if (record := answers.get((candidate["id"], QUESTION_VERSION)))
                and record.get("answer") == "yes"
                and _accepted_probability(record) >= 0.6]
    by_day = {}
    for candidate in accepted:
        by_day.setdefault(candidate["date"], []).append(_story_card(candidate))
    for day in by_day:
        by_day[day] = sorted(by_day[day], key=lambda row: (-row["rank_score"], row["title"].casefold()))[:10]
    days = sorted(by_day)
    today = dt.datetime.fromtimestamp(as_of, dt.timezone.utc).date().isoformat()
    default_day = today if today in by_day else (days[-1] if days else today)
    return {"days": days, "daily": by_day, "today": today, "default_day": default_day}


def _accepted_probability(record):
    try:
        return float((record.get("probabilities") or {}).get("yes", 0))
    except (TypeError, ValueError, OverflowError):
        return 0.0


if __name__ == "__main__":
    result = curate()
    import json
    print("Reads curator: " + json.dumps(result, sort_keys=True))
