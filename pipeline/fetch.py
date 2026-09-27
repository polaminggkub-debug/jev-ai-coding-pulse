"""Fetch recent Reddit threads into a deterministic, offline-readable snapshot."""

import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SUBREDDITS_PATH = ROOT / "config" / "subreddits.txt"
INCOMING_PATH = DATA / "incoming.json"
BASE = "https://arctic-shift.photon-reddit.com/api"
DAYS = 5
SECONDS_PER_DAY = 86400
POST_PAGE_SIZE = 100
COMMENT_PAGE_SIZE = 100
TOP_POSTS = 8
MAX_CONCURRENT_REQUESTS = 4
RETRIES = 4
BACKOFF_SECONDS = 3


def load_subreddits(path=SUBREDDITS_PATH):
    """Read subreddit names, ignoring blank lines, comments, and duplicates."""
    names = []
    seen = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        name = line.split("#", 1)[0].strip()
        if name and name not in seen:
            names.append(name)
            seen.add(name)
    return names


def _open_json(request, timeout):
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def get(path, *, opener=None, sleep_fn=time.sleep, attempts=RETRIES, **query):
    """Call Arctic Shift with bounded exponential retries; raise after exhaustion."""
    opener = opener or _open_json
    url = f"{BASE}/{path}?{urllib.parse.urlencode(query)}"
    last_error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "jev-reddit-pulse/1.0 (scheduled public-data fetch)"},
            )
            payload = opener(request, timeout=60)
            data = payload.get("data", []) if isinstance(payload, dict) else []
            return data if isinstance(data, list) else []
        except Exception as error:  # Network and response errors share the retry policy.
            last_error = error
            print(f"retry {path} ({attempt + 1}/{attempts}): {error}", file=sys.stderr)
            if attempt + 1 < attempts:
                sleep_fn(BACKOFF_SECONDS * (2**attempt))
    raise RuntimeError(f"{path} failed after {attempts} attempts") from last_error


def _timestamp(row):
    try:
        return float(row["created_utc"])
    except (KeyError, TypeError, ValueError):
        return None


def _page_items(fetch_json, endpoint, params, lower_bound, upper_bound, page_size):
    """Walk a descending Arctic Shift listing without repeating a cursor."""
    collected = {}
    before = int(upper_bound) + 1
    while True:
        page = fetch_json(endpoint, **params, after=int(lower_bound), before=before, limit=page_size)
        if not page:
            break
        page_times = []
        for item in page:
            created = _timestamp(item)
            if created is None:
                continue
            page_times.append(created)
            if lower_bound <= created <= upper_bound:
                item_id = str(item.get("id") or item.get("permalink") or "")
                if item_id:
                    collected[item_id] = item
        if len(page) < page_size or not page_times:
            break
        cursor = int(min(page_times))
        if cursor >= before or cursor < lower_bound:
            break
        before = cursor
    return list(collected.values())


def fetch_subreddit(subreddit, *, now=None, fetch_json=get):
    """Fetch one subreddit; callers isolate errors so another subreddit can finish."""
    now = time.time() if now is None else float(now)
    after = now - DAYS * SECONDS_PER_DAY
    posts = _page_items(
        fetch_json,
        "posts/search",
        {"subreddit": subreddit, "sort": "desc"},
        after,
        now,
        POST_PAGE_SIZE,
    )
    top = sorted(posts, key=lambda post: post.get("score") or 0, reverse=True)[:TOP_POSTS]
    output = []
    for post in top:
        post_id = str(post.get("id") or "")
        comments = _page_items(
            fetch_json,
            "comments/search",
            {"link_id": post_id, "sort": "desc"},
            after,
            now,
            COMMENT_PAGE_SIZE,
        )
        output.append(
            {
                key: post.get(key)
                for key in (
                    "id", "title", "selftext", "score", "num_comments", "permalink", "created_utc"
                )
            }
            | {
                "comments": [
                    {key: comment.get(key) for key in ("id", "body", "score", "created_utc")}
                    for comment in comments
                ]
            }
        )
    return subreddit, {"scanned": len(posts), "top": output}


def _safe_fetch(subreddit, *, now, fetch_json):
    try:
        return fetch_subreddit(subreddit, now=now, fetch_json=fetch_json)
    except Exception as error:
        print(f"failed r/{subreddit}: {error}", file=sys.stderr)
        return subreddit, {"scanned": 0, "top": [], "error": str(error)}


def run_fetch(
    subreddits=None,
    *,
    subreddits_path=SUBREDDITS_PATH,
    output_path=INCOMING_PATH,
    now=None,
    fetch_json=None,
):
    """Fetch configured subreddits with at most four workers and save the snapshot."""
    names = load_subreddits(subreddits_path) if subreddits is None else list(subreddits)
    now = time.time() if now is None else float(now)
    fetch_json = get if fetch_json is None else fetch_json
    if not names:
        results = {}
    else:
        worker_count = min(MAX_CONCURRENT_REQUESTS, len(names))
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            pairs = pool.map(
                lambda name: _safe_fetch(name, now=now, fetch_json=fetch_json), names
            )
            results = dict(pairs)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(
        json.dumps(results, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    for subreddit, value in results.items():
        scores = [post.get("score") or 0 for post in value["top"]]
        comments = sum(len(post["comments"]) for post in value["top"])
        print(f"{subreddit:20} scanned={value['scanned']:4} top_scores={scores} comments={comments}")
    return results


def main():
    run_fetch()


if __name__ == "__main__":
    main()
