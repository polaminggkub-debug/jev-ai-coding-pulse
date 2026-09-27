"""Offline tests for the append-only judgment and derived item store."""

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import store


def stamp(value):
    return dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp()


def item(item_id, subject, version, created, score=1, text="example"):
    return {
        "id": item_id,
        "kind": "comment",
        "sub": "Example",
        "score": score,
        "link": f"https://reddit.test/comments/{item_id}/",
        "thread": "A coding thread",
        "thread_score": 10,
        "thread_url": "https://reddit.test/comments/post1/",
        "subject": subject,
        "zone": "model",
        "version": version,
        "text": text,
        "created_utc": created,
    }


def judgment(row, label, judged_at=None, q="sentiment-v1"):
    return {
        "id": row["id"], "kind": row["kind"], "subject": row["subject"], "q": q,
        "label": label, "probs": {label: 0.9}, "created_utc": row["created_utc"],
        "judged_at": judged_at if judged_at is not None else row["created_utc"] + 60,
    }


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_judgments_are_append_only_and_indexed_across_month_files(self):
        jan = item("c1", "Claude Opus", "Opus 5.5", stamp("2026-01-31T23:30:00"))
        feb = item("c2", "Qwen", "Qwen 3.8", stamp("2026-02-01T00:30:00"))

        store.append_judgment(self.root, judgment(jan, "praise"))
        store.append_judgment(self.root, judgment(feb, "complaint"))

        paths = sorted((self.root / "judgments").glob("*.jsonl"))
        self.assertEqual([path.name for path in paths], ["2026-01.jsonl", "2026-02.jsonl"])
        index = store.judgment_index(self.root)
        self.assertEqual(index[("c1", "Claude Opus", "sentiment-v1")]["label"], "praise")
        self.assertEqual(index[("c2", "Qwen", "sentiment-v1")]["label"], "complaint")

    def test_items_keep_required_metadata_short_text_and_refresh_scores(self):
        created = stamp("2026-03-04T05:06:00")
        long_text = "x" * 600
        original = item("c1", "Claude Opus", "Opus 5.5", created, score=2, text=long_text)
        store.append_item(self.root, original)
        store.update_items(self.root, [dict(original, score=18, thread_score=44, text="updated")])

        [saved] = list(store.read_rows(self.root / "items"))
        self.assertEqual(saved["score"], 18)
        self.assertEqual(saved["thread_score"], 44)
        self.assertEqual(saved["created_utc"], created)
        self.assertEqual(saved["text"], "updated")
        self.assertLessEqual(len(saved["text"]), 400)
        self.assertEqual(saved["subject"], "Claude Opus")
        self.assertEqual(saved["version"], "Opus 5.5")
        self.assertEqual(saved["kind"], "comment")
        self.assertEqual(saved["link"], original["link"])
        self.assertEqual(saved["thread_url"], original["thread_url"])

    def test_daily_aggregates_count_labels_and_opinions_by_family_and_version(self):
        created = stamp("2026-03-04T05:06:00")
        cases = [
            (item("c1", "Claude Opus", "Opus 5.5", created), "praise"),
            (item("c2", "Claude Opus", "Opus 5.5", created), "complaint"),
            (item("c3", "Claude Opus", "Opus 5.7", created), "no_opinion"),
            (item("c4", "Qwen", "Qwen 3.8", created), "mixed"),
        ]
        with patch("store.os.fsync"):
            for row, label in cases:
                store.append_item(self.root, row)
                store.append_judgment(self.root, judgment(row, label))

        days = store.rebuild_daily(self.root)

        self.assertEqual(set(days), {"2026-03-04"})
        saved = json.loads((self.root / "daily" / "2026-03-04.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["families"]["Claude Opus"], {
            "praise": 1, "complaint": 1, "mixed": 0, "no_opinion": 1, "opinion": 2,
        })
        self.assertEqual(saved["versions"]["Claude Opus"]["Opus 5.5"], {
            "praise": 1, "complaint": 1, "mixed": 0, "no_opinion": 0, "opinion": 2,
        })
        self.assertEqual(saved["opinions"], [
            {"id": "c1", "subject": "Claude Opus", "version": "Opus 5.5", "label": "praise",
             "q": "sentiment-v1", "probs": {"praise": 0.9}, "created_utc": created},
            {"id": "c2", "subject": "Claude Opus", "version": "Opus 5.5", "label": "complaint",
             "q": "sentiment-v1", "probs": {"complaint": 0.9}, "created_utc": created},
            {"id": "c3", "subject": "Claude Opus", "version": "Opus 5.7", "label": "no_opinion",
             "q": "sentiment-v1", "probs": {"no_opinion": 0.9}, "created_utc": created},
            {"id": "c4", "subject": "Qwen", "version": "Qwen 3.8", "label": "mixed",
             "q": "sentiment-v1", "probs": {"mixed": 0.9}, "created_utc": created},
        ])
        self.assertEqual(saved["versions"]["Claude Opus"]["Opus 5.7"]["opinion"], 0)
        self.assertEqual(saved["families"]["Qwen"]["mixed"], 1)
        self.assertEqual(saved["families"]["Qwen"]["opinion"], 1)

    def test_rebuilding_daily_removes_stale_days(self):
        (self.root / "daily").mkdir(parents=True)
        (self.root / "daily" / "1999-01-01.json").write_text("{}", encoding="utf-8")

        self.assertEqual(store.rebuild_daily(self.root), {})
        self.assertEqual(list((self.root / "daily").glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
