"""Durable, versioned Jev decisions for the reads curator."""
import json
import os
import time
from pathlib import Path

try:
    from . import curator, store
except ImportError:
    import curator
    import store


def read_answer_index(root):
    answers = {}
    for row in store.read_rows(Path(root) / "curation"):
        if row.get("q") == curator.QUESTION_VERSION and row.get("answer") in {"yes", "no"}:
            answers[(row.get("id"), row.get("q"))] = row
    return answers


def _read_attempts(root):
    attempted, calls_by_day = set(), {}
    for row in store.read_rows(Path(root) / "curation-attempts"):
        key = (row.get("id"), row.get("q"))
        if row.get("q") == curator.QUESTION_VERSION:
            attempted.add(key)
        if row.get("attempted_at") is not None:
            day = store.date(row["attempted_at"])
            calls_by_day[day] = calls_by_day.get(day, 0) + 1
    return attempted, calls_by_day


def _append_jsonl(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _append_attempt(root, candidate, attempted_at):
    month = store.date(attempted_at)[:7]
    path = Path(root) / "curation-attempts" / f"{month}.jsonl"
    _append_jsonl(path, {"id": candidate["id"], "q": curator.QUESTION_VERSION,
                        "attempted_at": attempted_at})


def _append_answer(root, candidate, answer, probability, judged_at):
    month = store.date(candidate["date"])[:7]
    record = {"id": candidate["id"], "kind": "thread", "subject": "worth_reading",
              "q": curator.QUESTION_VERSION, "answer": answer,
              "probabilities": {"yes": probability}, "source": candidate["source"],
              "community": candidate["community"], "thread_url": candidate["url"],
              "created_utc": store.timestamp(candidate["date"]), "judged_at": judged_at}
    _append_jsonl(Path(root) / "curation" / f"{month}.jsonl", record)


def _yes_probability(answer):
    probabilities = answer.get("probabilities") or answer.get("probs") or {}
    if not isinstance(probabilities, dict):
        return None
    if "yes" in probabilities:
        value = probabilities["yes"]
        complement = False
    elif "no" in probabilities:
        value = probabilities["no"]
        complement = True
    else:
        return None
    try:
        probability = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if complement:
        probability = 1 - probability
    return probability if 0 <= probability <= 1 else None


def _decide_function(decide_fn):
    if decide_fn is not None:
        return decide_fn
    try:
        from .jev import decide
    except ImportError:
        from jev import decide
    return decide


def _decision_state(candidate):
    rows = candidate["rows"]
    post = next((row for row in rows if row.get("kind") == "post" and row.get("text")), None)
    comments_by_id = {row.get("id"): row for row in rows
                      if row.get("kind") == "comment" and row.get("text")}
    comments = sorted(comments_by_id.values(),
                      key=lambda row: (-_number(row.get("score"), 0), str(row.get("id"))))
    pieces = [f"Title: {candidate['title']}", f"Community: {candidate['community']}",
              f"Models/tools: {', '.join(candidate['models'])}"]
    if post:
        pieces.append(f"Post: {post['text'][:900]}")
    if comments:
        pieces.append("Top comments:\n" + "\n".join(
            f"- {row['text'][:350]}" for row in comments[:4]))
    return {"subject": "AI coding model or tool discussion", "text": "\n".join(pieces)}


def _answer_call(decide, candidate):
    result = decide(_decision_state(candidate), {"s": curator.QUESTION})
    answer = result.get("s", {}) if isinstance(result, dict) else {}
    choice = str(answer.get("choice") or "").casefold()
    probability = _yes_probability(answer)
    return (choice, probability) if choice in {"yes", "no"} else ("", probability)


def _curate_locked(root, candidates, decide_fn, now, cap):
    answers = read_answer_index(root)
    attempted, calls_by_day = _read_attempts(root)
    pending = [item for item in candidates if (item["id"], curator.QUESTION_VERSION) not in attempted
               and (item["id"], curator.QUESTION_VERSION) not in answers]
    called = failed = saved = 0
    decide = None
    for candidate in pending:
        attempted_at = time.time() if now is None else now
        day = store.date(attempted_at)
        daily_calls = calls_by_day.get(day, 0)
        if daily_calls >= min(curator.MAX_DAILY_CALLS, cap):
            break
        _append_attempt(root, candidate, attempted_at)
        calls_by_day[day] = daily_calls + 1
        attempted.add((candidate["id"], curator.QUESTION_VERSION))
        called += 1
        try:
            if decide is None:
                decide = _decide_function(decide_fn)
            choice, probability = _answer_call(decide, candidate)
        except Exception as error:
            print(f"Reads decision failed for {candidate['id']}: {type(error).__name__}")
            failed += 1
            continue
        if not choice or probability is None:
            failed += 1
            continue
        judged_at = time.time() if now is None else now
        _append_answer(root, candidate, choice, probability, judged_at)
        answers[(candidate["id"], curator.QUESTION_VERSION)] = {
            "answer": choice, "probabilities": {"yes": probability}}
        saved += 1
    return _stats(candidates, pending, called, failed, saved, calls_by_day, now, cap)


def _number(value, default=0):
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError, OverflowError):
        return default


def _stats(candidates, pending, called, failed, saved, calls_by_day, now, cap):
    current_time = time.time() if now is None else now
    current_calls = calls_by_day.get(store.date(current_time), 0)
    return {"eligible": len(candidates), "pending": len(pending), "calls": called,
            "failed": failed, "saved": saved,
            "remaining_today": max(0, min(curator.MAX_DAILY_CALLS, cap) - current_calls)}


def curate(data_dir=curator.DATA, decide_fn=None, *, now=None, max_calls=curator.MAX_DAILY_CALLS):
    """Ask once per candidate; count every attempt against the UTC daily cap."""
    root = Path(data_dir)
    fixed_time = None if now is None else store.timestamp(now)
    cap = max(0, int(max_calls))
    with store.run_lock(root, "curation"):
        as_of = time.time() if fixed_time is None else fixed_time
        candidates = curator.ranked_candidates(store.load_mentions(root), now=as_of)
        return _curate_locked(root, candidates, decide_fn, fixed_time, cap)


if __name__ == "__main__":
    result = curate()
    print("Reads curator: " + json.dumps(result, sort_keys=True))
