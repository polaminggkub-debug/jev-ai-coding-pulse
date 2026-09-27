"""Offline contracts for HN, Bluesky, Dev.to, Lobsters, and source isolation."""
import unittest
import tempfile
from urllib.parse import parse_qs, urlsplit

from fetch_bluesky import fetch_bluesky, _search
from fetch_devto import fetch_devto, _articles
from fetch_hn import fetch_hn
from fetch_lobsters import fetch_lobsters
from fetch_sources import run_sources
from registry import R
from source_utils import iso_utc

NOW = 1_800_000_000


class FreeSourceTests(unittest.TestCase):
    def test_hn_queries_story_and_comment_for_each_family_and_keeps_good_story(self):
        searched = []

        def fake(url):
            if '/search_by_date' in url:
                query = parse_qs(urlsplit(url).query)
                searched.append((query['query'][0], query['tags'][0]))
                return {'hits': [{'objectID': '7', 'story_id': '7', 'title': 'Opus coding',
                                  'created_at_i': NOW - 3600, 'points': 12,
                                  'num_comments': 1, 'url': 'https://news.ycombinator.com/item?id=7'}],
                        'nbPages': 1}
            return {'id': 7, 'title': 'Opus coding', 'created_at_i': NOW - 3600,
                    'points': 12, 'children': [{'id': 8, 'type': 'comment', 'text': 'I like Opus',
                    'created_at_i': NOW - 1800, 'author': 'person'}]}

        listings = fetch_hn(now=NOW, http_get=fake)
        self.assertEqual(len(searched), len(R) * 2)
        self.assertEqual({kind for _, kind in searched}, {'story', 'comment'})
        self.assertEqual(len(listings[0]['top']), 1)
        self.assertEqual(listings[0]['top'][0]['comments'][0]['source'], 'hn')

    def test_bluesky_searches_every_family_and_skips_auth_failure_cleanly(self):
        queries = []

        def fake(url):
            query = parse_qs(urlsplit(url).query)
            if 'searchPosts' in url:
                queries.append(query['q'][0])
                return {'posts': []}
            return {'thread': {'replies': []}}

        self.assertEqual(fetch_bluesky(now=NOW, http_get=fake)[0]['top'], [])
        self.assertEqual(set(queries), {name for name, _, _ in R})
        self.assertEqual(fetch_bluesky(now=NOW, http_get=lambda _: (_ for _ in ()).throw(PermissionError('auth required'))), [])

    def test_bluesky_direct_post_view_and_replies_are_retained(self):
        def fake(url):
            post = {'uri': 'at://person/app.bsky.feed.post/abc', 'likeCount': 5,
                    'replyCount': 1, 'author': {'handle': 'person.test'},
                    'record': {'text': 'Opus helps coding', 'createdAt': iso_utc(NOW - 100)}}
            if 'searchPosts' in url:
                return {'posts': [post]}
            reply = dict(post, uri='at://person/app.bsky.feed.post/reply', likeCount=1)
            return {'thread': {'replies': [{'post': reply}]}}

        posts = fetch_bluesky(now=NOW, http_get=fake)[0]['top']
        self.assertEqual(len(posts), 1)
        self.assertEqual(len(posts[0]['comments']), 1)
        self.assertEqual(posts[0]['score'], 5)
        self.assertTrue(posts[0]['comments'][0]['id'].endswith('/reply'))

    def test_devto_reaction_threshold_comments_and_tag_coverage(self):
        requests = []

        def fake(url):
            requests.append(url)
            if '/comments' in url:
                self.assertIn('/api/comments?a_id=1', url)
                return [{'id_code': 'nine', 'body_markdown': 'Good Opus detail', 'created_at': iso_utc(NOW - 60),
                         'user': {'username': 'dev'}}]
            return [{'id': 1, 'title': 'Claude coding', 'description': 'Opus experience',
                     'published_at': iso_utc(NOW - 3600), 'positive_reactions_count': 5,
                     'comments_count': 1, 'url': 'https://dev.to/a/one'}]

        posts = fetch_devto(now=NOW, http_get=fake)[0]['top']
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]['comments'][0]['source'], 'devto')
        tags = {parse_qs(urlsplit(url).query).get('tag', [''])[0] for url in requests if '/comments' not in url}
        self.assertIn('ai', tags)
        self.assertIn('qwen', tags)

    def test_bluesky_cursor_and_devto_pages_continue_without_repeats(self):
        cursors = []
        def bluesky(url):
            query = parse_qs(urlsplit(url).query)
            cursors.append(query.get('cursor', [''])[0])
            self.assertIn('since', query)
            return {'posts': [{'uri': cursors[-1] or 'first'}], 'cursor': 'next'}
        self.assertEqual(len(list(_search('Qwen', bluesky, NOW))), 2)
        self.assertEqual(cursors, ['', 'next'])
        pages = []
        def devto(url):
            page = int(parse_qs(urlsplit(url).query)['page'][0])
            pages.append(page)
            if page == 1:
                return [dict(id=i, published_at=iso_utc(NOW - 100)) for i in range(100)]
            return [dict(id=101, published_at=iso_utc(NOW - 200))]
        self.assertEqual(len(list(_articles('ai', devto, NOW))), 101)
        self.assertEqual(pages, [1, 2])

    def test_lobsters_threshold_and_source_error_isolation(self):
        def fake(url):
            if '/vibecoding.json' in url:
                raise OSError('tag unavailable')
            if '/s/' in url:
                return {'comments': [{'short_id': 'xy', 'comment': 'Opus works',
                    'created_at': iso_utc(NOW - 60), 'score': 1, 'url': 'https://lobste.rs/c/xy'}]}
            return [{'short_id': 'ab', 'title': 'AI coding', 'score': 5,
                     'created_at': iso_utc(NOW - 3600), 'url': 'https://lobste.rs/s/ab'}]

        posts = fetch_lobsters(now=NOW, http_get=fake)[0]['top']
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]['comments'][0]['source'], 'lobsters')
        with tempfile.TemporaryDirectory() as directory:
            result = run_sources(f'{directory}/incoming.json', fetchers=[
                lambda: (_ for _ in ()).throw(OSError('one bad source')),
                lambda: [{'source': 'hn', 'community': 'HN', 'top': []}]])
        self.assertEqual(result, [{'source': 'hn', 'community': 'HN', 'top': []}])


if __name__ == '__main__':
    unittest.main()
