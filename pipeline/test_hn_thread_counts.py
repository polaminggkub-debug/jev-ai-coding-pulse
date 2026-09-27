"""HN item responses supply nested children rather than num_comments."""
import unittest
from urllib.parse import parse_qs, urlsplit

from fetch_hn import fetch_hn

NOW = 1_800_000_000


class HnThreadCountTests(unittest.TestCase):
    def test_comment_search_parent_counts_all_nested_comments(self):
        def fake(url):
            if '/search_by_date' in url:
                kind = parse_qs(urlsplit(url).query)['tags'][0]
                hit = {'objectID': '8', 'story_id': '7', 'created_at_i': NOW - 100,
                       'comment_text': 'Opus works well for coding'}
                return {'hits': [hit] if kind == 'comment' else [], 'nbPages': 1}
            return {'id': 7, 'title': 'A coding workflow', 'created_at_i': NOW - 3600,
                    'points': 20, 'children': [
                        {'id': 8, 'type': 'comment', 'text': 'Opus works well for coding',
                         'created_at_i': NOW - 100, 'children': [
                             {'id': 9, 'type': 'comment', 'text': 'A nested reply',
                              'created_at_i': NOW - 50}]},
                        {'id': 10, 'type': 'comment', 'text': None,
                         'created_at_i': NOW - 25}]}

        post = fetch_hn(now=NOW, http_get=fake)[0]['top'][0]

        self.assertEqual(post['num_comments'], 3)
        self.assertEqual(len(post['comments']), 2)
        self.assertEqual(post['score'], 20)


if __name__ == '__main__':
    unittest.main()
