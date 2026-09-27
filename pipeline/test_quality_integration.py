"""Exercise quality gates at the fetch and pre-Jev classification boundaries."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from classify import classify
from fetch import fetch_subreddit
import store

NOW = 1_800_000_000
DAY = 86400


class FakeDecide:
    def __init__(self):
        self.texts = []

    def __call__(self, state, _questions):
        self.texts.append(state["text"])
        return {"s": {"choice": "praise", "probabilities": {"praise": 0.9}}}


def comment(item_id, *, body="I like Opus 5.5", score=1, age_days=1, author="human"):
    return {
        "id": item_id,
        "body": body,
        "score": score,
        "author": author,
        "created_utc": NOW - age_days * DAY,
    }


def post(post_id, *, age_days, score, num_comments, comments):
    return {
        "id": post_id,
        "title": "A coding discussion",
        "selftext": "",
        "score": score,
        "num_comments": num_comments,
        "permalink": f"/r/Example/comments/{post_id}/thread/",
        "created_utc": NOW - age_days * DAY,
        "comments": comments,
    }


class QualityIntegrationTests(unittest.TestCase):
    def test_fetch_caps_at_twenty_five_eligible_threads(self):
        posts = [
            {"id": f"p{score}", "title": f"Thread {score}", "selftext": "",
             "score": score, "num_comments": 5,
             "permalink": f"/r/Example/comments/p{score}/thread/",
             "created_utc": NOW - DAY}
            for score in range(30)
        ]

        def fake_fetch(endpoint, **_params):
            return posts if endpoint == "posts/search" else []

        _name, result = fetch_subreddit("Example", now=NOW, fetch_json=fake_fetch)

        self.assertEqual(len(result["top"]), 25)
        self.assertEqual([row["score"] for row in result["top"]], list(range(29, 4, -1)))

    def test_only_quality_eligible_comments_reach_jev(self):
        eligible_recent = post(
            "recent-ok", age_days=1, score=0, num_comments=5,
            comments=[
                comment("recent-zero", age_days=1, score=0),
                comment("deleted", age_days=1, score=10, body="[deleted]"),
                comment("removed", age_days=1, score=10, body="[removed]"),
                comment("bot", age_days=1, score=10, author="AutoModerator"),
            ],
        )
        eligible_settled = post(
            "settled-ok", age_days=4, score=10, num_comments=0,
            comments=[
                comment("settled-positive", age_days=4, score=1),
                comment("settled-thread-comment", age_days=4, score=1),
                comment("settled-zero", age_days=4, score=0),
            ],
        )
        rejected_recent_thread = post(
            "recent-four-comments", age_days=1, score=999, num_comments=4,
            comments=[comment("recent-thread-leak", age_days=1, score=5)],
        )
        rejected_settled_thread = post(
            "settled-score-nine", age_days=4, score=9, num_comments=100,
            comments=[comment("settled-thread-leak", age_days=4, score=5)],
        )
        raw = {"Example": {"top": [
            eligible_recent, eligible_settled,
            rejected_recent_thread, rejected_settled_thread,
        ]}}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "incoming.json"
            data_dir = root / "data"
            raw_path.write_text(json.dumps(raw), encoding="utf-8")
            decide = FakeDecide()
            with patch("classify.time.time", return_value=NOW):
                rows = classify(raw_path, data_dir, decide)

            self.assertEqual(len(decide.texts), 3)
            self.assertEqual({row["id"] for row in rows}, {
                "recent-zero", "settled-positive", "settled-thread-comment",
            })
            self.assertEqual(len(list(store.read_rows(data_dir / "judgments"))), 3)


if __name__ == "__main__":
    unittest.main()
