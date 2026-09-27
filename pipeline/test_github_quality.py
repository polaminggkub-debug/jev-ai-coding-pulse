"""GitHub comments pass the shared classifier quality gate."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classify import classify

NOW = 1_800_000_000


class GitHubQualityTests(unittest.TestCase):
    def test_deleted_and_settled_zero_score_comments_are_not_judged(self):
        calls = []

        def decide(state, _questions):
            calls.append(state)
            return {"s": {"choice": "praise", "probabilities": {"praise": 0.9}}}

        post = {
            "id": "issue:4",
            "title": "Codex issue",
            "selftext": "",
            "score": 3,
            "num_comments": 3,
            "created_utc": NOW - 30 * 86400,
            "url": "https://github.com/openai/codex/issues/4",
            "context_only": True,
            "source": "github",
            "community": "openai/codex",
            "implicit_subjects": [{"name": "Codex", "zone": "tool"}],
            "comments": [
                {"id": "comment:deleted", "body": "[deleted]", "score": 20,
                 "created_utc": NOW - 4 * 86400, "author": "human"},
                {"id": "comment:old-zero", "body": "Codex failed here", "score": 0,
                 "created_utc": NOW - 4 * 86400, "author": "human"},
                {"id": "comment:recent", "body": "Useful detail", "score": 0,
                 "created_utc": NOW - 86400, "author": "human"},
            ],
        }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incoming = root / "incoming.json"
            incoming.write_text(json.dumps([{
                "source": "github", "community": "openai/codex", "top": [post]
            }]), encoding="utf-8")
            with patch("classify.time.time", return_value=NOW):
                rows = classify(incoming, root / "data", decide)

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "github:comment:recent")
        self.assertEqual(rows[0]["source"], "github")
        self.assertEqual(rows[0]["community"], "openai/codex")


if __name__ == "__main__":
    unittest.main()
