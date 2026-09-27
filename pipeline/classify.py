"""Classify model mentions, reusing judgments saved in ``data/``."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

try:
    from .registry import mentions
    from .versions import extract_version
except ImportError:
    from registry import mentions
    from versions import extract_version

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_PATH = DATA / "raw.json"
LABELED_PATH = DATA / "labeled.json"
CACHE_PATH = DATA / "classify_cache.json"
WORKERS = 12
VALID_LABELS = {"praise", "complaint", "mixed", "no_opinion"}

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


def jobs_from_raw(raw):
    """Build one current metadata row for each unique item/subject pair."""
    jobs = {}
    for subreddit, listing in raw.items():
        for post in listing.get("top", []):
            thread_url = "https://www.reddit.com" + (post.get("permalink") or "")
            post_id = post.get("id")
            entries = [
                ("post", post_id, (post.get("title") or "") + "\n" + (post.get("selftext") or ""), post.get("score"), thread_url)
            ]
            entries.extend(
                ("comment", comment.get("id"), comment.get("body") or "", comment.get("score"), thread_url + str(comment.get("id") or "") + "/")
                for comment in post.get("comments", [])
            )
            for kind, raw_id, text, score, link in entries:
                for subject, zone in mentions(text):
                    comment_id = _pair_id(kind, raw_id, link)
                    if not comment_id:
                        continue
                    row = {
                        "comment_id": comment_id,
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


def _key(comment_id, subject):
    return f"{comment_id}\t{subject}"


def _load_cache(cache_path, labeled_path):
    """Load the durable cache and seed it from the original labeled file."""
    cache = {}
    if cache_path.exists():
        try:
            for row in json.loads(cache_path.read_text(encoding="utf-8")):
                if not isinstance(row, dict):
                    continue
                key = _key(str(row.get("comment_id") or ""), row.get("subject") or "")
                if key != "\t" and row.get("label") in VALID_LABELS:
                    cache[key] = {"comment_id": row["comment_id"], "subject": row["subject"], "label": row.get("label"), "probs": row.get("probs")}
        except (OSError, ValueError, TypeError):
            cache = {}
    if labeled_path.exists():
        try:
            labeled = json.loads(labeled_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            labeled = []
        for row in labeled if isinstance(labeled, list) else []:
            if not isinstance(row, dict):
                continue
            comment_id = str(row.get("comment_id") or _pair_id(row.get("kind", ""), "", row.get("link", "")))
            subject = row.get("subject") or ""
            key = _key(comment_id, subject)
            if comment_id and subject and row.get("label") in VALID_LABELS and key not in cache:
                cache[key] = {"comment_id": comment_id, "subject": subject, "label": row.get("label"), "probs": row.get("probs")}
    return cache


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def _decide_function(decide_fn):
    if decide_fn is not None:
        return decide_fn
    # jev reads the API key when imported, so import it only if there is work.
    try:
        from .jev import decide
    except ImportError:
        from jev import decide
    return decide


def classify(raw_path=RAW_PATH, labeled_path=LABELED_PATH, cache_path=CACHE_PATH, decide_fn=None):
    """Refresh labeled metadata and judge only pairs missing from the cache."""
    started = time.time()
    raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    jobs = jobs_from_raw(raw)
    cache = _load_cache(Path(cache_path), Path(labeled_path))
    pending = [(key, row) for key, row in jobs.items() if _key(*key) not in cache]

    if pending:
        decide = _decide_function(decide_fn)

        def run(item):
            key, row = item
            answer = decide({"subject": row["subject"], "text": row["text"]}, {"s": Q}).get("s", {})
            label = answer.get("choice")
            judgment = {"comment_id": key[0], "subject": key[1], "label": label, "probs": answer.get("probabilities")}
            return key, judgment if label in VALID_LABELS else None

        with ThreadPoolExecutor(WORKERS) as pool:
            for key, judgment in pool.map(run, pending):
                if judgment is not None:
                    cache[_key(*key)] = judgment

    output = []
    for key, row in jobs.items():
        judgment = cache.get(_key(*key), {})
        labeled = dict(row)
        labeled["label"] = judgment.get("label")
        labeled["probs"] = judgment.get("probs")
        labeled["version"] = row["version"]
        output.append(labeled)

    _write_json(Path(cache_path), sorted(cache.values(), key=lambda row: (row["comment_id"], row["subject"])))
    _write_json(Path(labeled_path), output)
    failed = sum(1 for row in output if not row.get("label"))
    print(f"{len(output)} mentions; {len(pending)} new judgments in {round(time.time() - started)}s; failed: {failed}")
    return output


def main():
    classify()


if __name__ == "__main__":
    main()
