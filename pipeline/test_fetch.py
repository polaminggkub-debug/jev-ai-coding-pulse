"""Offline tests for the bounded, configurable Reddit fetcher."""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fetch import get, load_subreddits, run_fetch

NOW = 1_800_000_000
DAY = 86400


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_subreddit_config_skips_comments_blanks_and_duplicates(self):
        config = self.root / "subreddits.txt"
        config.write_text("# heading\n Alpha  \n\nBeta # note\nAlpha\n", encoding="utf-8")
        self.assertEqual(load_subreddits(config), ["Alpha", "Beta"])

    def test_get_retries_with_exponential_backoff(self):
        calls = []
        delays = []

        def opener(request, timeout):
            calls.append((request, timeout))
            if len(calls) < 3:
                raise OSError("temporary")
            return {"data": [{"id": "post1"}]}

        rows = get(
            "posts/search",
            subreddit="Example Sub",
            after=10,
            opener=opener,
            sleep_fn=delays.append,
            attempts=3,
        )

        self.assertEqual(rows, [{"id": "post1"}])
        self.assertEqual([timeout for _, timeout in calls], [60, 60, 60])
        self.assertEqual(delays, [3, 6])
        self.assertEqual(parse_qs(urlsplit(calls[-1][0].full_url).query), {"subreddit": ["Example Sub"], "after": ["10"]})

    def test_fetch_keeps_top_eight_recent_posts_and_created_timestamps(self):
        recent = [
            {"id": f"p{score}", "title": f"Thread {score}", "selftext": "", "score": score,
             "num_comments": 1, "permalink": f"/r/Example/comments/p{score}/thread/",
             "created_utc": NOW - score * 10}
            for score in range(10)
        ]
        rows = recent + [
            {**recent[0], "id": "old", "score": 999, "created_utc": NOW - 6 * DAY},
            {**recent[0], "id": "future", "score": 1000, "created_utc": NOW + 100},
        ]
        calls = []

        def fake_get(endpoint, **params):
            calls.append((endpoint, params))
            if endpoint == "posts/search":
                return rows
            return [{"id": "c1", "body": "Great", "score": 5, "created_utc": NOW - 20}]

        destination = self.root / "data" / "incoming.json"
        result = run_fetch(["Example"], output_path=destination, now=NOW, fetch_json=fake_get)
        item = result["Example"]

        self.assertEqual(item["scanned"], 10)
        self.assertEqual([post["score"] for post in item["top"]], list(range(9, 1, -1)))
        self.assertTrue(all(post["created_utc"] is not None for post in item["top"]))
        self.assertTrue(all(comment["created_utc"] == NOW - 20 for post in item["top"] for comment in post["comments"]))
        self.assertTrue(all(post["id"] not in {"old", "future"} for post in item["top"]))
        query = next(params for endpoint, params in calls if endpoint == "posts/search")
        self.assertEqual(query["after"], NOW - 5 * DAY)
        self.assertEqual(query["before"], NOW + 1)
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), result)

    def test_a_failed_subreddit_is_recorded_without_failing_other_results(self):
        def fake_get(endpoint, **params):
            if params.get("subreddit") == "Broken":
                raise OSError("upstream unavailable")
            return []

        result = run_fetch(
            ["Healthy", "Broken"],
            output_path=self.root / "incoming.json",
            now=NOW,
            fetch_json=fake_get,
        )

        self.assertEqual(result["Healthy"], {"scanned": 0, "top": []})
        self.assertEqual(result["Broken"]["top"], [])
        self.assertIn("upstream unavailable", result["Broken"]["error"])

    def test_requests_never_exceed_four_concurrent_workers(self):
        lock = threading.Lock()
        first_wave = threading.Barrier(4)
        active = 0
        maximum = 0
        calls = 0

        def fake_get(_endpoint, **_params):
            nonlocal active, maximum, calls
            with lock:
                active += 1
                calls += 1
                current_call = calls
                maximum = max(maximum, active)
            try:
                if current_call <= 4:
                    first_wave.wait(timeout=5)
                return []
            finally:
                with lock:
                    active -= 1

        run_fetch(
            [f"Sub{i}" for i in range(6)],
            output_path=self.root / "incoming.json",
            now=NOW,
            fetch_json=fake_get,
        )

        self.assertEqual(maximum, 4)


if __name__ == "__main__":
    unittest.main()
