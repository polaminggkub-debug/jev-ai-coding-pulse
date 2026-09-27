"""Backfill history one day at a time: top threads posted that day, plus comments from their first 3 days.

Usage: OPENROUTER_API_KEY=... python3 scripts/backfill.py --from-days 30 --to-days 5 [--top 5]
Judged pairs are never re-sent to Jev, so rerunning is safe and cheap.
"""
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import classify  # noqa: E402
import fetch  # noqa: E402

DAY = 86400
COMMENT_DAYS = 3


def day_snapshot(subreddit, start, top_n):
    posts = fetch._page_items(fetch.get, "posts/search", {"subreddit": subreddit, "sort": "desc"},
                              start, start + DAY, fetch.POST_PAGE_SIZE)
    top = sorted(posts, key=lambda p: p.get("score") or 0, reverse=True)[:top_n]
    out = []
    for post in top:
        comments = fetch._page_items(fetch.get, "comments/search", {"link_id": str(post.get("id")), "sort": "desc"},
                                     start, start + COMMENT_DAYS * DAY, fetch.COMMENT_PAGE_SIZE)
        row = {k: post.get(k) for k in ("id", "title", "selftext", "score", "num_comments", "permalink", "created_utc")}
        row["comments"] = [{k: c.get(k) for k in ("id", "body", "score", "created_utc")} for c in comments]
        out.append(row)
    return subreddit, {"scanned": len(posts), "top": out}


def safe(subreddit, start, top_n):
    try:
        return day_snapshot(subreddit, start, top_n)
    except Exception as error:  # one broken subreddit must not stop the backfill
        print(f"failed r/{subreddit}: {error}", file=sys.stderr)
        return subreddit, {"scanned": 0, "top": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-days", type=int, default=30)
    ap.add_argument("--to-days", type=int, default=5)
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()
    subs = fetch.load_subreddits()
    today = int(time.time()) // DAY * DAY
    for back in range(args.from_days, args.to_days, -1):
        start = today - back * DAY
        with ThreadPoolExecutor(fetch.MAX_CONCURRENT_REQUESTS) as pool:
            snapshot = dict(pool.map(lambda s: safe(s, start, args.top), subs))
        path = fetch.DATA / "backfill.json"
        path.write_text(__import__("json").dumps(snapshot))
        print(f"== {time.strftime('%Y-%m-%d', time.gmtime(start))}: "
              f"{sum(len(v['top']) for v in snapshot.values())} threads", flush=True)
        classify.classify(raw_path=path)
        path.unlink()


if __name__ == "__main__":
    main()
