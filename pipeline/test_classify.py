"""Offline checks for the durable incremental classifier cache."""

import json
import tempfile
import unittest
from pathlib import Path

from classify import classify


def fixture(body="I like Opus 5.5", comment_score=4, thread_score=12):
    return {
        "Example": {
            "top": [
                {
                    "id": "post1",
                    "title": "A coding tools thread",
                    "selftext": "",
                    "score": thread_score,
                    "permalink": "/r/Example/comments/post1/thread/",
                    "comments": [{"id": "comment1", "body": body, "score": comment_score}],
                }
            ]
        }
    }


class FakeDecide:
    def __init__(self):
        self.calls = []

    def __call__(self, state, _questions):
        self.calls.append(state)
        return {"s": {"choice": "praise", "probabilities": {"praise": 0.9}}}


class IncrementalClassifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw_path = self.root / "raw.json"
        self.labeled_path = self.root / "labeled.json"
        self.cache_path = self.root / "classify_cache.json"
        self.decide = FakeDecide()

    def tearDown(self):
        self.temp.cleanup()

    def write_raw(self, raw):
        self.raw_path.write_text(json.dumps(raw), encoding="utf-8")

    def run_classify(self):
        return classify(self.raw_path, self.labeled_path, self.cache_path, self.decide)

    def test_rerun_skips_decision_and_refreshes_scores(self):
        self.write_raw(fixture())
        first = self.run_classify()
        self.assertEqual(len(self.decide.calls), 1)
        self.assertEqual(first[0]["version"], "Opus 5.5")

        self.write_raw(fixture(comment_score=19, thread_score=45))
        second = self.run_classify()

        self.assertEqual(len(self.decide.calls), 1)
        self.assertEqual(second[0]["score"], 19)
        self.assertEqual(second[0]["thread_score"], 45)
        self.assertEqual(second[0]["label"], "praise")

    def test_new_subject_on_existing_comment_is_a_new_pair(self):
        self.write_raw(fixture())
        self.run_classify()
        self.write_raw(fixture("I like Opus 5.5 and Qwen3.8", comment_score=7))

        rows = self.run_classify()

        self.assertEqual(len(self.decide.calls), 2)
        self.assertEqual({row["subject"] for row in rows}, {"Claude Opus", "Qwen"})
        self.assertTrue(all(row["comment_id"] == "comment1" for row in rows))
        cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self.assertEqual(len(cache), 2)

    def test_legacy_labeled_file_seeds_cache_without_a_decision(self):
        self.write_raw(fixture())
        legacy = {
            "kind": "comment",
            "link": "https://www.reddit.com/r/Example/comments/post1/thread/comment1/",
            "subject": "Claude Opus",
            "label": "complaint",
            "probs": {"complaint": 0.8},
        }
        self.labeled_path.write_text(json.dumps([legacy]), encoding="utf-8")

        rows = self.run_classify()

        self.assertEqual(self.decide.calls, [])
        self.assertEqual(rows[0]["label"], "complaint")
        self.assertEqual(json.loads(self.cache_path.read_text(encoding="utf-8"))[0]["comment_id"], "comment1")

    def test_duplicate_raw_pairs_are_judged_once(self):
        raw = fixture()
        duplicate = dict(raw["Example"]["top"][0]["comments"][0], score=9)
        raw["Example"]["top"][0]["comments"].append(duplicate)
        self.write_raw(raw)

        rows = self.run_classify()

        self.assertEqual(len(self.decide.calls), 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["score"], 9)

    def test_failed_judgment_is_retried(self):
        class FailsOnce:
            calls = 0

            def __call__(self, _state, _questions):
                self.calls += 1
                if self.calls == 1:
                    return {"error": "temporary failure"}
                return {"s": {"choice": "praise", "probabilities": {"praise": 0.9}}}

        decide = FailsOnce()
        self.write_raw(fixture())
        first = classify(self.raw_path, self.labeled_path, self.cache_path, decide)
        second = classify(self.raw_path, self.labeled_path, self.cache_path, decide)

        self.assertEqual(first[0]["label"], None)
        self.assertEqual(second[0]["label"], "praise")
        self.assertEqual(decide.calls, 2)

    def test_version_uses_full_comment_before_classifier_truncation(self):
        body = "Opus " + ("x" * 1500) + " and later Opus 5.7"
        self.write_raw(fixture(body))

        rows = self.run_classify()

        self.assertEqual(rows[0]["version"], "Opus 5.7")
        self.assertNotIn("5.7", rows[0]["text"])


if __name__ == "__main__":
    unittest.main()
