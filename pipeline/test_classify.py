"""Offline tests for durable, versioned classification."""

import contextlib
import datetime as dt
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import store
from classify import MAX_CALLS, QUESTION_VERSION, classify
from migrate import migrate


def stamp(value):
    return dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp()


def fixture(body="I like Opus 5.5", comment_score=4, thread_score=12,
            created_utc=None, comment_id="comment1"):
    post = {
        "id": "post1",
        "title": "A coding tools thread",
        "selftext": "",
        "score": thread_score,
        "num_comments": 5,
        "permalink": "/r/Example/comments/post1/thread/",
        "created_utc": created_utc,
        "comments": [{"id": comment_id, "body": body, "score": comment_score,
                      "created_utc": created_utc}],
    }
    return {"Example": {"top": [post]}}


class FakeDecide:
    def __init__(self, labels=("praise",)):
        self.calls = []
        self.labels = iter(labels)

    def __call__(self, state, _questions):
        self.calls.append(state)
        label = next(self.labels, "praise")
        return {"s": {"choice": label, "probabilities": {label: 0.9}}}


class DurableClassifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw_path = self.root / "incoming.json"
        self.decide = FakeDecide()

    def tearDown(self):
        self.temp.cleanup()

    def write_raw(self, raw):
        self.raw_path.write_text(json.dumps(raw), encoding="utf-8")

    def run_classify(self, q=QUESTION_VERSION):
        return classify(self.raw_path, self.root / "data", self.decide, q=q)

    def test_same_pair_is_not_judged_again_when_raw_date_moves_month(self):
        self.write_raw(fixture(created_utc=stamp("2026-01-31T23:30:00")))
        first = self.run_classify()
        self.assertEqual(len(self.decide.calls), 1)
        self.assertEqual(first[0]["label"], "praise")

        self.write_raw(fixture(comment_score=19, thread_score=45,
                               created_utc=stamp("2026-02-01T01:00:00")))
        second = self.run_classify()

        self.assertEqual(len(self.decide.calls), 1)
        self.assertEqual(second[0]["score"], 19)
        self.assertEqual(second[0]["thread_score"], 45)
        self.assertEqual(second[0]["label"], "praise")
        judgments = list(store.read_rows(self.root / "data" / "judgments"))
        self.assertEqual(len(judgments), 1)
        self.assertEqual(store.date(judgments[0]["created_utc"]), "2026-01-31")

    def test_question_version_bump_rejudges_the_same_pair(self):
        self.decide = FakeDecide(("praise", "complaint"))
        self.write_raw(fixture(created_utc=stamp("2026-01-10T12:00:00")))

        first = self.run_classify(q="sentiment-v1")
        second = self.run_classify(q="sentiment-v2")

        self.assertEqual([row["label"] for row in first], ["praise"])
        self.assertEqual([row["label"] for row in second], ["complaint"])
        self.assertEqual(len(self.decide.calls), 2)
        self.assertEqual({row["q"] for row in store.read_rows(self.root / "data" / "judgments")},
                         {"sentiment-v1", "sentiment-v2"})
        daily = json.loads(next((self.root / "data" / "daily").glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(daily["families"]["Claude Opus"]["praise"], 0)
        self.assertEqual(daily["families"]["Claude Opus"]["complaint"], 1)
        self.assertEqual(daily["families"]["Claude Opus"]["opinion"], 1)

    def test_returns_all_persisted_rows_when_incoming_feed_is_empty(self):
        self.write_raw(fixture())
        self.run_classify()

        self.write_raw({})
        rows = self.run_classify()

        self.assertEqual(len(self.decide.calls), 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "comment1")
        self.assertEqual(rows[0]["label"], "praise")

    def test_rerun_refreshes_scores_and_keeps_the_existing_answer(self):
        self.write_raw(fixture())
        self.run_classify()
        self.write_raw(fixture(comment_score=19, thread_score=45))

        rows = self.run_classify()

        self.assertEqual(len(self.decide.calls), 1)
        self.assertEqual(rows[0]["score"], 19)
        self.assertEqual(rows[0]["thread_score"], 45)
        self.assertEqual(rows[0]["label"], "praise")

    def test_failed_decision_is_retried_on_the_next_run(self):
        class FailsOnce:
            def __init__(self):
                self.calls = 0

            def __call__(self, _state, _questions):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("temporary provider failure")
                return {"s": {"choice": "praise", "probabilities": {"praise": 0.9}}}

        decide = FailsOnce()
        self.write_raw(fixture())

        with contextlib.redirect_stdout(io.StringIO()):
            first = classify(self.raw_path, self.root / "data", decide)
            second = classify(self.raw_path, self.root / "data", decide)

        self.assertEqual(first, [])
        self.assertEqual([row["label"] for row in second], ["praise"])
        self.assertEqual(decide.calls, 2)
        self.assertEqual(len(list(store.read_rows(self.root / "data" / "judgments"))), 1)

    def test_version_is_extracted_from_full_text_before_short_storage(self):
        body = "Opus " + ("x" * 1500) + " and later Opus 5.7"
        self.write_raw(fixture(body=body))

        rows = self.run_classify()

        self.assertEqual(rows[0]["version"], "Opus 5.7")
        self.assertLessEqual(len(rows[0]["text"]), 400)
        self.assertNotIn("5.7", rows[0]["text"])

    def prepare_legacy_migration(self):
        created = stamp("2026-01-12T12:00:00")
        judged = stamp("2026-01-13T12:00:00")
        fallback_date = stamp("2025-12-30T12:00:00")

        def legacy(item_id, subject, label, probability):
            return {
                "id": item_id, "kind": "comment", "subject": subject,
                "q": "sentiment-v1", "label": label,
                "probs": {label: probability}, "created_utc": created,
                "judged_at": judged,
            }

        shared = legacy("comment-a", "Claude Opus", "complaint", 0.8)
        cache_only = legacy("cache-only", "Qwen", "mixed", 0.7)
        conflicting_answer = legacy("comment-a", "Claude Opus", "praise", 0.6)
        label_only = legacy("comment-b", "Claude Opus", "no_opinion", 0.9)
        fallback_only = {"id": "fallback-only", "kind": "comment", "subject": "Codex",
                         "q": "sentiment-v1", "label": "praise", "probs": {"praise": 0.7}}
        (self.root / "classify_cache.json").write_text(
            json.dumps([shared, cache_only, fallback_only]), encoding="utf-8")
        (self.root / "labeled.json").write_text(
            json.dumps([shared, conflicting_answer, label_only]), encoding="utf-8")
        raw_post = fixture().get("Example", {}).get("top", [])[0]
        raw_post["comments"][0]["id"] = "comment-a"
        raw_post["comments"].append({
            "id": "comment-b", "body": "Claude Opus is a tool", "score": 3,
            "created_utc": created,
        })
        (self.root / "raw.json").write_text(
            json.dumps({"Example": {"top": [raw_post]}}), encoding="utf-8")
        for name, modified in (("classify_cache.json", fallback_date),
                               ("labeled.json", fallback_date + 10),
                               ("raw.json", fallback_date + 20)):
            path = self.root / name
            os.utime(path, (modified, modified))

    def test_migration_unions_cache_and_labels_including_cache_only_answers(self):
        self.prepare_legacy_migration()
        added = migrate(self.root)

        rows = list(store.read_rows(self.root / "judgments"))
        signatures = {(row["id"], row["subject"], row["q"], row["label"])
                      for row in rows}
        self.assertEqual(added, 5)
        self.assertEqual(len(rows), 5)
        self.assertEqual(signatures, {
            ("comment-a", "Claude Opus", "sentiment-v1", "complaint"),
            ("cache-only", "Qwen", "sentiment-v1", "mixed"),
            ("comment-a", "Claude Opus", "sentiment-v1", "praise"),
            ("comment-b", "Claude Opus", "sentiment-v1", "no_opinion"),
            ("fallback-only", "Codex", "sentiment-v1", "praise"),
        })
        imported_items = list(store.read_rows(self.root / "items"))
        cache_item = next(row for row in imported_items if row["id"] == "cache-only")
        self.assertEqual(cache_item["subject"], "Qwen")
        self.assertEqual(cache_item["text"], "")
        self.assertEqual(cache_item["zone"], "open")
        enriched = next(row for row in imported_items if row["id"] == "comment-a")
        self.assertIn("Opus 5.5", enriched["text"])
        self.assertEqual(enriched["score"], 4)
        fallback = next(row for row in rows if row["id"] == "fallback-only")
        self.assertEqual(store.date(fallback["created_utc"]), "2025-12-30")
        self.assertTrue(all(not (self.root / name).exists() for name in
                            ("classify_cache.json", "labeled.json", "raw.json")))
        self.assertEqual(migrate(self.root), 0)

    def test_hard_cap_makes_only_12000_fake_calls_and_defers_the_rest(self):
        count = MAX_CALLS + 2
        post = {
            "id": "post1", "title": "Coding tools", "selftext": "",
            "num_comments": count,
            "score": 10,
            "permalink": "/r/Example/comments/post1/thread/", "created_utc": stamp("2026-02-01T12:00:00"),
            "comments": [{"id": f"comment{i}", "body": "I like Opus 5.5", "score": i + 1,
                          "created_utc": stamp("2026-02-01T12:00:00")} for i in range(count)],
        }
        self.write_raw({"Example": {"top": [post]}})
        decide = FakeDecide()
        output = io.StringIO()

        # The behavior under test is the call cap; skip 16,000 real fsyncs.
        with patch("store.os.fsync"), contextlib.redirect_stdout(output):
            rows = classify(self.raw_path, self.root / "data", decide)

        self.assertEqual(len(decide.calls), MAX_CALLS)
        self.assertEqual(len(rows), MAX_CALLS)
        self.assertIn(f"Hard cap reached: {MAX_CALLS} new Jev calls", output.getvalue())
        self.assertEqual(len(list(store.read_rows(self.root / "data" / "judgments"))), MAX_CALLS)


if __name__ == "__main__":
    unittest.main()
