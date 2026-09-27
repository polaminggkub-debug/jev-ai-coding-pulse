"""Keep recent Dev.to articles when their optional comments are unavailable."""
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from fetch_devto import _articles, fetch_devto
from source_utils import iso_utc

NOW = 1_800_000_000


class DevtoRecoveryTests(unittest.TestCase):
    def test_popularity_search_is_limited_to_the_last_five_days(self):
        def fake(url):
            self.assertEqual(parse_qs(urlsplit(url).query)['top'], ['5'])
            return []

        self.assertEqual(list(_articles('ai', fake, NOW)), [])

    def test_comment_failure_keeps_article_and_does_not_repeat_across_tags(self):
        calls = []

        def fake(url):
            if '/comments' in url:
                calls.append(url)
                raise HTTPError(url, 403, 'Forbidden', {}, None)
            return [{'id': 1, 'title': 'Opus coding experience',
                     'published_at': iso_utc(NOW - 60), 'positive_reactions_count': 7,
                     'comments_count': 2, 'url': 'https://dev.to/a/opus'}]

        posts = fetch_devto(now=NOW, http_get=fake)[0]['top']

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]['num_comments'], 2)
        self.assertEqual(posts[0]['comments'], [])
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
