"""GitHub comments pass the shared classifier quality gate."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classify import classify
import store

NOW = 1_800_000_000


def github_cap_raw():
    comments = [{'id': f'comment:{index}', 'body': 'Useful detail', 'score': 1,
                 'created_utc': NOW - 3600} for index in range(301)]
    comments.append({'id': 'comment:cached', 'body': 'Updated detail', 'score': 99,
                     'created_utc': NOW - 3600})
    post = {'id': 'issue:1', 'title': 'Coding issue', 'selftext': '', 'context_only': True,
            'created_utc': NOW - 86400, 'url': 'https://github.com/openai/codex/issues/1',
            'source': 'github', 'community': 'openai/codex',
            'implicit_subjects': [{'name': 'Codex', 'zone': 'tool'}], 'comments': comments}
    other = {'id': 'hn-post', 'title': 'Coding question', 'selftext': '',
             'created_utc': NOW - 3600, 'url': 'https://news.ycombinator.com/item?id=9',
             'comments': [{'id': 'hn-comment', 'body': 'Opus works nicely', 'score': 4,
                           'created_utc': NOW - 1800}]}
    return [{'source': 'github', 'community': 'openai/codex', 'top': [post]},
            {'source': 'hn', 'community': 'HN', 'top': [other]}]


def seed_github_judgments(data):
    for item_id, subject, created, label, text in (
            ('github:comment:cached', 'Codex', NOW - 3600, 'praise', 'Old detail'),
            ('github:comment:absent', 'Qwen', NOW - 7200, 'complaint', 'Older stored issue')):
        store.append_item(data, {'id': item_id, 'kind': 'comment', 'subject': subject,
            'source': 'github', 'community': 'openai/codex', 'created_utc': created, 'text': text})
        store.append_judgment(data, {'id': item_id, 'kind': 'comment', 'subject': subject,
            'q': 'sentiment-source-v1', 'label': label, 'created_utc': created, 'judged_at': NOW - 60})


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

    def test_github_attempt_cap_counts_failures_and_refreshes_cached_rows(self):
        calls = []
        def decide(state, _questions):
            calls.append(state)
            if len(calls) == 1:
                raise RuntimeError('temporary provider error')
            if len(calls) == 2:
                return {'s': {'choice': 'not-a-label'}}
            return {'s': {'choice': 'praise', 'probabilities': {'praise': 0.9}}}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / 'data'
            seed_github_judgments(data)
            incoming = root / 'incoming.json'
            incoming.write_text(json.dumps(github_cap_raw()), encoding='utf-8')
            output = io.StringIO()
            with patch('classify.time.time', return_value=NOW), patch('store.os.fsync'), \
                    contextlib.redirect_stdout(output):
                rows = classify(incoming, data, decide)
            cached = next(row for row in rows if row['id'] == 'github:comment:cached')
            judgments = list(store.read_rows(data / 'judgments'))
            stats = json.loads((data / 'run-stats.json').read_text(encoding='utf-8'))
            self.assertEqual(len(calls), 301)
            self.assertEqual(len(judgments), 301)
            self.assertEqual(cached['score'], 99)
            self.assertIn('github:comment:absent', {row['id'] for row in rows})
            self.assertIn('hn:hn-comment', {row['id'] for row in rows})
            self.assertEqual(stats['calls'], 301)
            self.assertEqual(stats['githubCalls'], 300)
            self.assertEqual(stats['githubDeferred'], 1)
            self.assertIn('GitHub Jev: attempts=300/300 deferred=1', output.getvalue())


if __name__ == "__main__":
    unittest.main()
