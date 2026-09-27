"""A qualified high-vote comment stays on a read card without a Jev job."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import curator
import store
from classify import classify

NOW = 1_800_000_000
POST_DATE = NOW - 10 * 86400


def raw_thread():
    url = 'https://www.reddit.com/r/Example/comments/thread1/codex-experience/'
    comments = [{"id": "card-top", "body": "This workflow tip saved me hours.",
                 "score": 9, "author": "human", "created_utc": NOW - 3600,
                 "url": url + 'card-top/'}]
    comments.extend({"id": f"judged-{index}",
                     "body": f"Codex is excellent for coding, experience {index}.",
                     "score": index, "author": "human", "created_utc": NOW - 3600,
                     "url": url + f"judged-{index}/"} for index in range(1, 6))
    comments.extend([
        {"id": "removed-high", "body": "[removed]", "score": 100,
         "author": "human", "created_utc": NOW - 3600, "url": url + 'removed-high/'},
        {"id": "settled-low", "body": "An old comment", "score": 0,
         "author": "human", "created_utc": NOW - 5 * 86400, "url": url + 'settled-low/'},
    ])
    return {"Example": {"top": [{"id": "thread1", "title": "Codex experience",
            "selftext": "", "score": 20, "num_comments": len(comments),
            "created_utc": POST_DATE, "permalink": url, "comments": comments}]}}


class TopCommentTests(unittest.TestCase):
    def test_unmatched_top_comment_survives_classification_store_and_read_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / 'incoming.json'
            data = root / 'data'
            raw.write_text(json.dumps(raw_thread()), encoding='utf-8')
            sentiment_calls = []

            def sentiment(state, _questions):
                sentiment_calls.append(state['text'])
                return {"s": {"choice": "praise", "probabilities": {"praise": 0.9}}}

            with patch('classify.time.time', return_value=NOW):
                classified = classify(raw, data, sentiment)

            self.assertEqual(len(sentiment_calls), 6)
            self.assertFalse(any('workflow tip saved me hours' in text for text in sentiment_calls))
            item_rows = store.load_mentions(data)
            top = {"id": "reddit:card-top", "text": "This workflow tip saved me hours.",
                   "score": 9, "link": "https://www.reddit.com/r/Example/comments/thread1/codex-experience/card-top/"}
            self.assertEqual(len(classified), 6)
            self.assertTrue(all(row.get('thread_top_comment') == top for row in item_rows))

            reads_calls = []

            def reads_decision(_state, _questions):
                reads_calls.append(True)
                return {"s": {"choice": "yes", "probabilities": {"yes": 0.8}}}

            self.assertEqual(curator.curate(data, reads_decision, now=NOW)['calls'], 1)
            with patch('classify.time.time', return_value=NOW):
                classify(raw, data, sentiment)
            payload = curator.reads_payload(data, now=NOW)

            self.assertEqual(len(sentiment_calls), 6)
            self.assertEqual(len(reads_calls), 1)
            [card] = payload['daily'][payload['default_day']]
            self.assertEqual(card['popular_comment'], {"text": top['text'], "score": 9, "url": top['link']})

    def test_unknown_score_ranks_below_a_known_zero_score(self):
        rows = [
            {"id": "reddit:known-zero", "kind": "comment", "text": "Known zero",
             "score": 0, "link": "https://discussion.test/zero"},
            {"id": "reddit:other", "kind": "post", "text": "Other opinion",
             "score": 1, "link": "https://discussion.test/other",
             "thread_top_comment": {"id": "reddit:unknown", "text": "Unknown score",
                                    "score": None, "link": "https://discussion.test/unknown"}},
        ]

        self.assertEqual(curator._popular_comment(rows)['id'], 'reddit:known-zero')


if __name__ == '__main__':
    unittest.main()
