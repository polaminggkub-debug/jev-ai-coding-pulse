"""Date fallback, migration, and per-run statistics checks."""

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import store
from classify import classify, jobs_from_raw
from migrate import migrate


def stamp(value):
    return dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp()


def raw_with_dates(post_created, comment_created=None):
    post = {
        "id": "post1", "title": "A coding tools thread", "selftext": "", "score": 12,
        "num_comments": 5, "permalink": "/r/Example/comments/post1/thread/",
        "created_utc": post_created,
        "comments": [{"id": "comment1", "body": "I like Opus 5.5", "score": 4,
                      "created_utc": comment_created}],
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


class DateAndRunStatsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw_path = self.root / "incoming.json"

    def tearDown(self):
        self.temp.cleanup()

    def write_raw(self, raw):
        self.raw_path.write_text(json.dumps(raw), encoding="utf-8")

    def test_comment_uses_parent_date_when_its_own_date_is_missing(self):
        parent = stamp("2026-09-08T12:00:00")
        raw = raw_with_dates(parent)
        comment_job = next(row for row in jobs_from_raw(raw).values()
                           if row["kind"] == "comment")
        self.assertIsNone(comment_job["created_utc"])
        self.assertEqual(comment_job["parent_created_utc"], parent)

        self.write_raw(raw)
        rows = classify(self.raw_path, self.root / "data", FakeDecide())
        [comment] = [row for row in rows if row["kind"] == "comment"]
        [item] = [row for row in store.read_rows(self.root / "data" / "items")
                  if row["kind"] == "comment"]
        self.assertEqual(store.date(comment["created_utc"]), "2026-09-08")
        self.assertIsNone(item["created_utc"])
        self.assertEqual(item["parent_created_utc"], parent)
        self.assertEqual(item["created_utc_source"], "parent")

    def test_judged_at_is_used_only_when_item_and_parent_dates_are_missing(self):
        judged = stamp("2026-09-28T07:00:00")
        self.write_raw(raw_with_dates(None))
        with patch("classify.time.time", return_value=judged):
            rows = classify(self.raw_path, self.root / "data", FakeDecide())
        [comment] = [row for row in rows if row["kind"] == "comment"]
        self.assertEqual(comment["created_utc"], judged)
        [item] = [row for row in store.read_rows(self.root / "data" / "items")
                  if row["kind"] == "comment"]
        self.assertIsNone(item["created_utc"])
        self.assertIsNone(item["parent_created_utc"])
        self.assertEqual(item["created_utc_source"], "judged")
        self.assertEqual(item["judged_at"], judged)

    def test_migration_prefers_raw_parent_date_to_legacy_fallback_date(self):
        parent = stamp("2026-08-05T12:00:00")
        legacy_fallback = stamp("2026-09-28T07:00:00")
        self.write_raw(raw_with_dates(parent))
        legacy = [{
            "id": "comment1", "kind": "comment", "subject": "Claude Opus",
            "q": "sentiment-v1", "label": "praise", "probs": {"praise": 0.9},
            "created_utc": legacy_fallback, "judged_at": legacy_fallback,
        }]
        (self.root / "raw.json").write_text(json.dumps(raw_with_dates(parent)), encoding="utf-8")
        (self.root / "labeled.json").write_text(json.dumps(legacy), encoding="utf-8")

        migrate(self.root)

        [saved] = store.load_mentions(self.root)
        [item] = [row for row in store.read_rows(self.root / "items")
                  if row["kind"] == "comment"]
        self.assertEqual(store.date(saved["created_utc"]), "2026-08-05")
        self.assertEqual(item["parent_created_utc"], parent)
        self.assertIsNone(item["created_utc"])
        daily = store.rebuild_daily(self.root)
        self.assertEqual(set(daily), {"2026-08-05"})

    def test_run_stats_count_only_successful_new_non_no_opinion_decisions(self):
        self.write_raw({"Example": {"top": [
            {"id": "p1", "title": "Opus 5.5 tool", "selftext": "", "score": 12,
             "num_comments": 5, "created_utc": stamp("2026-09-08T12:00:00"),
             "permalink": "/r/Example/comments/p1/thread/", "comments": []},
            {"id": "p2", "title": "Opus 5.5 tool", "selftext": "", "score": 12,
             "num_comments": 5, "created_utc": stamp("2026-09-08T12:00:00"),
             "permalink": "/r/Example/comments/p2/thread/", "comments": []},
        ]}})
        decide = FakeDecide(("praise", "no_opinion"))

        classify(self.raw_path, self.root / "data", decide)

        stats_path = self.root / "data" / "run-stats.json"
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        self.assertEqual((stats["newMentions"], stats["newOpinions"], stats["calls"]), (2, 1, 2))
        self.assertTrue(stats["completedAt"].endswith("Z"))

        self.write_raw({})
        with patch("classify.time.time", return_value=stamp("2026-09-28T07:00:00")):
            classify(self.raw_path, self.root / "data", decide)
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        self.assertEqual((stats["newMentions"], stats["newOpinions"], stats["calls"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
