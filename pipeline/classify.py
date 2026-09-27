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
    from .source_identity import normalize_item, prefixed_id, source_name
    from .versions import extract_version
except ImportError:
    import store
    from quality import comment_qualifies, thread_qualifies
    from registry import mentions
    from source_identity import normalize_item, prefixed_id, source_name
    from versions import extract_version

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_PATH = DATA / "incoming.json"
MAX_CALLS = 12000
VALID_LABELS = set(store.LABELS)
# Bump this whenever Q changes: judgments are keyed by this question version.
QUESTION_VERSION = "sentiment-v1"
SOURCE_QUESTION_VERSION = "sentiment-source-v1"

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
SOURCE_Q = {
    **Q,
    "instructions": "`text` is a post or comment from a developer discussion. How does it judge `subject` as a tool for writing code or doing agentic coding work? Use the thread title as context when present.",
}


def _path_id(link, kind):
    """Recover a stable ID from a source URL when an adapter omits it."""
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


def _pair_id(kind, raw_id, link, source="reddit"):
    item_id = str(raw_id or _path_id(link, kind) or "")
    if not item_id:
        return ""
    # Reddit post IDs and comment IDs are distinct in practice; prefix posts
    # anyway so the cache key stays unambiguous if a fixture reuses an ID.
    if kind == "post" and not item_id.startswith("post:"):
        item_id = f"post:{item_id}"
    return prefixed_id(source, item_id)


def _source_listings(raw):
    """Accept the legacy subreddit mapping and source listing collections."""
    if isinstance(raw, list):
        return [("", listing) for listing in raw if isinstance(listing, dict)]
    if not isinstance(raw, dict):
        return []
    if "top" in raw:
        return [("", raw)]
    return [(str(name), listing) for name, listing in raw.items()
            if isinstance(listing, dict)]


def _subject_zones(text, *implicit_lists):
    found = list(mentions(text))
    seen = set(found)
    for subjects in implicit_lists:
        for entry in subjects or []:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            pair = (str(entry["name"]), str(entry.get("zone") or "tool"))
            if pair not in seen:
                found.append(pair)
                seen.add(pair)
    return found


def _thread_link(source, post):
    link = post.get("permalink") or post.get("url") or ""
    if not link:
        return ""
    if str(link).startswith(("http://", "https://")):
        return str(link)
    return ("https://www.reddit.com" if source == "reddit" else "") + str(link)


def jobs_from_raw(raw, *, now=None, apply_quality=True):
    """Build one current metadata row for each unique item/subject pair."""
    now = time.time() if now is None else float(now)
    jobs = {}
    for legacy_name, listing in _source_listings(raw):
        source = source_name(listing.get("source"))
        community = listing.get("community") or legacy_name
        if source == "reddit" and community.startswith("r/"):
            community = community[2:]
        community = community or ("Reddit" if source == "reddit" else "")
        for post in listing.get("top", []):
            item_source = source_name(post.get("source") or source)
            item_community = post.get("community") or community
            entries, metadata = _post_entries(post, item_source, item_community, now, apply_quality)
            _add_entry_jobs(jobs, entries, metadata)
    return jobs


def _post_entries(post, source, community, now, apply_quality):
    if apply_quality and source == "reddit" and not thread_qualifies(post, now=now):
        return [], {}
    thread_url = _thread_link(source, post)
    created = post.get("created_utc")
    title = post.get("title") or ""
    entries = [] if post.get("context_only") else [
        ("post", post.get("id"), title + "\n" + (post.get("selftext") or ""),
         post.get("score"), thread_url, created, None, post.get("implicit_subjects"), None)]
    for comment in post.get("comments", []):
        if apply_quality and not comment_qualifies(
                comment, now=now, parent_created_utc=created):
            continue
        link = comment.get("url") or (thread_url + str(comment.get("id") or "") + "/")
        entries.append(("comment", comment.get("id"), comment.get("body") or "",
                        comment.get("score"), link, comment.get("created_utc"), created,
                        post.get("implicit_subjects"), comment.get("implicit_subjects")))
    metadata = {"source": source, "community": community, "title": title,
                "thread_url": thread_url, "thread_score": post.get("score"),
                "thread_comments": post.get("num_comments", len(post.get("comments", []))),
                "thread_created_utc": created, "zone": "tool",
                "thread_top_comment": _thread_top_comment(entries, source)}
    return entries, metadata


def _thread_top_comment(entries, source):
    comments = [entry for entry in entries if entry[0] == "comment" and
                _pair_id("comment", entry[1], entry[4], source)]
    if not comments: return None
    def score(entry):
        try: return float(entry[3])
        except (TypeError, ValueError, OverflowError): return float("-inf")
    top = max(comments, key=lambda entry: (score(entry), str(entry[1] or "")))
    return {"id": _pair_id("comment", top[1], top[4], source), "text": str(top[2] or "")[:400],
            "score": top[3], "link": top[4]}


def _add_entry_jobs(jobs, entries, metadata):
    for entry in entries:
        kind, raw_id, text, score, link, created, parent, inherited, own = entry
        for subject, zone in _subject_zones(text, inherited, own):
            item_id = _pair_id(kind, raw_id, link, metadata["source"])
            if item_id:
                row = _job_row(item_id, subject, zone, text, score, link,
                               created, parent, entry, metadata)
                jobs[(item_id, subject)] = row


def _job_row(item_id, subject, zone, text, score, link, created, parent, entry, metadata):
    source, community = metadata["source"], metadata["community"]
    title = metadata["title"]
    row = {"id": item_id, "comment_id": item_id, "created_utc": created,
           "parent_created_utc": parent, "sub": community if source == "reddit" else "",
           "source": source, "community": community, "kind": entry[0], "text": text[:1500],
           "score": score, "link": link, "thread": title, "thread_score": metadata["thread_score"],
           "thread_comments": metadata["thread_comments"],
           "thread_created_utc": metadata["thread_created_utc"],
           "thread_url": metadata["thread_url"], "subject": subject, "zone": zone,
           "thread_top_comment": metadata.get("thread_top_comment"),
           "version": extract_version(subject, text, thread_title=title)}
    return normalize_item(row, source, community)


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


def classify(raw_path=RAW_PATH, data_dir=DATA, decide_fn=None, q=None):
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
        active_q = q or (QUESTION_VERSION if row["source"] == "reddit"
                         else SOURCE_QUESTION_VERSION)
        judgment = index.get((*key, active_q))
        if judgment is None:
            if called >= MAX_CALLS:
                continue
            if decide is None:
                decide = _decide_function(decide_fn)
            called += 1
            try:
                question = Q if active_q == QUESTION_VERSION else SOURCE_Q
                text = row["text"]
                if row["source"] != "reddit":
                    text = f"Thread: {row.get('thread', '')}\n{text}"
                state = {"subject": row["subject"], "text": text}
                answer = decide(state, {"s": question}).get("s", {})
            except Exception as error:
                print(f"Decision failed for {key}: {type(error).__name__}")
                continue
            if answer.get("choice") not in VALID_LABELS:
                continue
            now = time.time()
            prior = created_dates.get(key, {})
            created = _created_for_new_decision(row, prior, now)
            judgment = {"id": key[0], "kind": row['kind'], "subject": key[1], "q": active_q,
                        "label": answer['choice'], "probs": answer.get('probabilities'),
                        "created_utc": created, "judged_at": now}
            # Save metadata before the irreversible append; a restart can recover it.
            store.append_item(data_dir, row, fallback=now)
            store.append_judgment(data_dir, judgment)
            index[(*key, active_q)] = judgment
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
    sources = Path(data_dir) / 'incoming-sources.json'
    if Path(raw_path).resolve() == RAW_PATH.resolve() and sources.exists():
        jobs.update(jobs_from_raw(json.loads(sources.read_text(encoding='utf-8'))))
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
