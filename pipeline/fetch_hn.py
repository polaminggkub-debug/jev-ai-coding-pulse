"""Hacker News Algolia adapter, including family-matched stories and comments."""

import sys
from collections import defaultdict

try:
    from .quality import comment_qualifies
    from .registry import R
    from .source_utils import api_url, attach_context, epoch, in_window, maybe_int
    from .source_utils import now_epoch, safe_int, source_id, source_listing, get_json, plain_text
except ImportError:
    from quality import comment_qualifies
    from registry import R
    from source_utils import api_url, attach_context, epoch, in_window, maybe_int
    from source_utils import now_epoch, safe_int, source_id, source_listing, get_json, plain_text

BASE = "https://hn.algolia.com/api/v1"
SEARCH = BASE + "/search_by_date"
ITEM = BASE + "/items/{}"
PAGE_SIZE = 100


def _search_family(family, kind, now, http_get):
    page, hits = 0, []
    while page < 10:
        url = api_url(SEARCH, query=family, tags=kind,
                      numericFilters=f"created_at_i>{int(now - 5 * 86400)}",
                      hitsPerPage=PAGE_SIZE, page=page)
        payload = http_get(url)
        rows = payload.get("hits", []) if isinstance(payload, dict) else []
        hits.extend(rows)
        if not rows or page + 1 >= safe_int(payload.get("nbPages"), 1):
            break
        page += 1
    return hits


def _as_comment(raw, parent_created, now):
    created = raw.get("created_at_i") or raw.get("created_at")
    body = plain_text(raw.get("comment_text") or raw.get("text") or "")
    score = maybe_int(raw.get("points"))
    comment = {"id": source_id("hn", raw.get("id") or raw.get("objectID")),
               "body": body, "score": score, "created_utc": epoch(created),
               "author": raw.get("author"),
               "url": f"https://news.ycombinator.com/item?id={raw.get('id') or raw.get('objectID')}"}
    if (in_window(created, now) and comment_qualifies(
            comment, now=now, parent_created_utc=parent_created)):
        return attach_context(comment, "hn", "HN")
    return None


def _comment_rows(item, now, parent_created, output):
    for child in item.get("children", []) or []:
        if child.get("type") == "comment":
            comment = _as_comment(child, parent_created, now)
            if comment:
                output[comment["id"]] = comment
        _comment_rows(child, now, parent_created, output)


def _comment_count(item):
    return sum((child.get("type") == "comment") + _comment_count(child)
               for child in item.get("children", []) or [])


def _story(hit, detail, now, matched_comments):
    detail = detail or {}
    story_id = str(detail.get("id") or hit.get("objectID") or hit.get("id") or "")
    created = detail.get("created_at_i") or detail.get("created_at") or hit.get("created_at_i")
    discussion = f"https://news.ycombinator.com/item?id={story_id}"
    comment_rows = {}
    _comment_rows(detail, now, created, comment_rows)
    for raw in matched_comments:
        comment = _as_comment(raw, created, now)
        if comment:
            comment_rows[comment["id"]] = comment
    post = {"id": source_id("hn", story_id), "title": detail.get("title") or hit.get("title") or "",
            "selftext": detail.get("text") or hit.get("story_text") or "",
            "score": maybe_int(detail.get("points", hit.get("points"))),
            "num_comments": safe_int(detail.get("num_comments", hit.get(
                "num_comments", _comment_count(detail)))),
            "created_utc": epoch(created), "url": discussion, "comments": list(comment_rows.values())}
    external = detail.get("url") or hit.get("url")
    if external:
        post["external_url"] = external
    return attach_context(post, "hn", "HN")


def _collect_candidates(now, http_get):
    stories, comments = {}, defaultdict(dict)
    for family, _, _ in R:
        try:
            for hit in _search_family(family, "story", now, http_get):
                sid = str(hit.get("story_id") or hit.get("objectID") or hit.get("id") or "")
                if sid and in_window(hit.get("created_at_i"), now) and maybe_int(hit.get("points")) is not None:
                    stories[sid] = hit
        except Exception as error:
            print(f"failed HN story search {family}: {error}", file=sys.stderr)
        try:
            for hit in _search_family(family, "comment", now, http_get):
                sid = str(hit.get("story_id") or "")
                cid = str(hit.get("objectID") or hit.get("id") or "")
                if sid and cid and in_window(hit.get("created_at_i"), now):
                    comments[sid][cid] = hit
                    stories.setdefault(sid, {"id": sid, "objectID": sid})
        except Exception as error:
            print(f"failed HN comment search {family}: {error}", file=sys.stderr)
    return stories, comments


def fetch_hn(*, now=None, http_get=None):
    """Return recent HN stories with at least ten points and recent comments."""
    now, http_get = now_epoch(now), get_json if http_get is None else http_get
    stories, comments = _collect_candidates(now, http_get)
    posts = []
    for story_id, hit in stories.items():
        try:
            detail = http_get(ITEM.format(story_id))
        except Exception as error:
            print(f"failed HN item {story_id}: {error}", file=sys.stderr)
            detail = hit
        created = detail.get("created_at_i", hit.get("created_at_i"))
        score = maybe_int(detail.get("points", hit.get("points")))
        if in_window(created, now) and score is not None and score >= 10:
            posts.append(_story(hit, detail, now, comments.get(story_id, {}).values()))
    return [source_listing("hn", "HN", posts)]


if __name__ == "__main__":
    import json
    print(json.dumps(fetch_hn(), ensure_ascii=False))
