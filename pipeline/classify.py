"""Classify model mentions, reusing judgments saved in ``data/``."""

import json
import time
import datetime as dt
from pathlib import Path
from urllib.parse import urlsplit

try:
    from . import store
    from .quality import comment_qualifies, thread_qualifies
    from .registry import mentions
    from .versions import extract_version
except ImportError:
    import store
    from quality import comment_qualifies, thread_qualifies
    from registry import mentions
    from versions import extract_version

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_PATH = DATA / "incoming.json"
MAX_CALLS = 12000
VALID_LABELS = set(store.LABELS)
# Bump this whenever Q changes: judgments are keyed by this question version.
QUESTION_VERSION = "sentiment-v1"

Q = {
    "type": "choice",
    "instructions": "`text` is a Reddit post or comment. How does it talk about `subject` as a tool for writing code or doing agentic coding work?",
    "criteria": {
        "praise": "Positive about `subject`: works well, impressed, recommends it, prefers it",
        "complaint": "Negative about `subject`: broken, worse, nerfed, limits, too expensive, disappointed, prefers something else",
        "mixed": "Both clear positives and clear negatives about `subject`",
        "no_opinion": "Mentions `subject` without judging it, asks a question, or is not about `subject` at all",
    },
}


def _path_id(link, kind):
    """Recover the stable Reddit ID from legacy labeled rows."""
    parts = [part for part in urlsplit(link or "").path.split("/") if part]
    try:
        index = parts.index("comments")
        if kind == "comment" and len(parts) > index + 3:
            return parts[-1]
        if len(parts) > index + 1:
            return parts[index + 1]
    except ValueError:
        pass
    return ""


def _pair_id(kind, raw_id, link):
    item_id = str(raw_id or _path_id(link, kind) or "")
    if not item_id:
        return ""
    # Reddit post IDs and comment IDs are distinct in practice; prefix posts
    # anyway so the cache key stays unambiguous if a fixture reuses an ID.
    return f"post:{item_id}" if kind == "post" else item_id


def jobs_from_raw(raw, *, now=None, apply_quality=True):
    """Build one current metadata row for each unique item/subject pair."""
    now = time.time() if now is None else float(now)
    jobs = {}
    for subreddit, listing in raw.items():
        for post in listing.get("top", []):
            if apply_quality and not thread_qualifies(post, now=now):
                continue
            thread_url = "https://www.reddit.com" + (post.get("permalink") or "")
            post_id = post.get("id")
            parent_created = post.get("created_utc")
            entries = [
                ("post", post_id, (post.get("title") or "") + "\n" + (post.get("selftext") or ""), post.get("score"), thread_url, parent_created, None)
            ]
            entries.extend(
                ("comment", comment.get("id"), comment.get("body") or "", comment.get("score"), thread_url + str(comment.get("id") or "") + "/", comment.get("created_utc"), parent_created)
                for comment in post.get("comments", [])
                if not apply_quality or comment_qualifies(
                    comment, now=now, parent_created_utc=parent_created)
            )
            for kind, raw_id, text, score, link, created, parent in entries:
                for subject, zone in mentions(text):
                    comment_id = _pair_id(kind, raw_id, link)
                    if not comment_id:
                        continue
                    row = {
                        "id": comment_id,
                        "comment_id": comment_id,
                        "created_utc": created,
                        "parent_created_utc": parent,
                        "sub": subreddit,
                        "kind": kind,
                        "text": text[:1500],
                        "score": score or 0,
                        "link": link,
                        "thread": post.get("title") or "",
                        "thread_score": post.get("score") or 0,
                        "thread_url": thread_url,
                        "subject": subject,
                        "zone": zone,
                        "version": extract_version(subject, text, thread_title=post.get("title") or ""),
                    }
                    jobs[(comment_id, subject)] = row
    return jobs


def _decide_function(decide_fn):
    if decide_fn is not None:
        return decide_fn
    # jev reads the API key when imported, so import it only if there is work.
    try:
        from .jev import decide
    except ImportError:
        from jev import decide
    return decide


def _created_for_new_decision(row, prior, judged_at):
    created = store.resolved_created_utc(row, prior)
    if created is None:
        row['judged_at'] = judged_at
        row['created_utc_source'] = 'judged'
        return judged_at
    if row.get('created_utc') is not None:
        row['created_utc_source'] = 'item'
    elif row.get('parent_created_utc') is not None:
        row['created_utc_source'] = 'parent'
    else:
        row['created_utc_source'] = 'judged'
    return created


def classify(raw_path=RAW_PATH, data_dir=DATA, decide_fn=None, q=QUESTION_VERSION):
    with store.run_lock(data_dir, 'classify'):
        return _classify(raw_path, data_dir, decide_fn, q)


def _process_jobs(jobs, data_dir, decide_fn, q):
    """Judge unseen jobs and refresh metadata for already judged jobs."""
    index = store.judgment_index(data_dir)
    created_dates = {(r['id'], r['subject']): r for r in index.values()}
    called = 0
    new_mentions = 0
    new_opinions = 0
    decide = None
    refreshed = []
    for key, row in jobs.items():
        judgment = index.get((*key, q))
        if judgment is None:
            if called >= MAX_CALLS:
                continue
            if decide is None:
                decide = _decide_function(decide_fn)
            called += 1
            try:
                answer = decide({"subject": row["subject"], "text": row["text"]}, {"s": Q}).get("s", {})
            except Exception as error:
                print(f"Decision failed for {key}: {type(error).__name__}")
                continue
            if answer.get("choice") not in VALID_LABELS:
                continue
            now = time.time()
            prior = created_dates.get(key, {})
            created = _created_for_new_decision(row, prior, now)
            judgment = {"id": key[0], "kind": row['kind'], "subject": key[1], "q": q,
                        "label": answer['choice'], "probs": answer.get('probabilities'),
                        "created_utc": created, "judged_at": now}
            # Save metadata before the irreversible append; a restart can recover it.
            store.append_item(data_dir, row, fallback=now)
            store.append_judgment(data_dir, judgment)
            index[(*key, q)] = judgment
            new_mentions += 1
            new_opinions += answer['choice'] != 'no_opinion'
        if row.get('created_utc') is None and row.get('parent_created_utc') is None:
            row.setdefault('judged_at', judgment.get('judged_at'))
            row.setdefault('created_utc_source', 'judged')
        refreshed.append(row)
    return refreshed, called, new_mentions, new_opinions


def _classify(raw_path, data_dir, decide_fn, q):
    """Persist each successful answer immediately; retry only absent answers."""
    try:
        from .migrate import migrate
    except ImportError:
        from migrate import migrate
    migrate(data_dir)
    raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    jobs = jobs_from_raw(raw)
    refreshed, called, new_mentions, new_opinions = _process_jobs(
        jobs, data_dir, decide_fn, q)
    store.update_items(data_dir, refreshed)
    store.rebuild_daily(data_dir)
    completed_at = dt.datetime.fromtimestamp(time.time(), dt.timezone.utc).isoformat().replace('+00:00', 'Z')
    store.write_json(Path(data_dir) / 'run-stats.json', {
        'newOpinions': new_opinions,
        'newMentions': new_mentions,
        'calls': called,
        'completedAt': completed_at,
    })
    if called >= MAX_CALLS:
        print(f"Hard cap reached: {MAX_CALLS} new Jev calls; remaining work deferred.")
    print(f"{len(jobs)} mentions; {called} new Jev calls")
    return store.load_mentions(data_dir)


if __name__ == "__main__":
    classify()
