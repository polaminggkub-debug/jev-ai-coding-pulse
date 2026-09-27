"""Deterministic request pacing and 429 recovery tests for the Dev.to client."""
from email.utils import formatdate
from urllib.error import HTTPError
import unittest
from unittest.mock import patch

import devto_api
import fetch_devto as devto
from devto_api import DevToAPI
from source_utils import iso_utc

NOW = 1_800_000_000


def response_article():
    return {'id': 77, 'title': 'Codex coding experience',
            'published_at': iso_utc(NOW - 60), 'positive_reactions_count': 7,
            'comments_count': 1, 'url': 'https://dev.to/codex/experience'}


def too_many_requests(url, retry_after=None):
    headers = {'Retry-After': str(retry_after)} if retry_after is not None else {}
    return HTTPError(url, 429, 'Too Many Requests', headers, None)


class Clock:
    def __init__(self, now=NOW):
        self.now = float(now)
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class DevToAPITests(unittest.TestCase):
    def test_default_fetcher_retries_comment_429_and_keeps_article_comment(self):
        comment_calls = []

        def fake(url):
            if '/comments' not in url:
                return [response_article()]
            comment_calls.append(url)
            if len(comment_calls) == 1:
                raise too_many_requests(url, 0)
            return [{'id_code': 'reply-1', 'body_markdown': 'Useful experience',
                     'created_at': iso_utc(NOW - 30), 'positive_reactions_count': 2,
                     'url': 'https://dev.to/codex/experience/reply-1'}]

        clock = Clock()
        with patch.object(devto, '_tags', return_value=['ai']), \
                patch.object(devto, 'get_json', side_effect=fake), \
                patch.object(devto_api.time, 'time', clock), \
                patch.object(devto_api.time, 'sleep', clock.sleep):
            posts = devto.fetch_devto(now=NOW)[0]['top']

        self.assertEqual(len(posts), 1)
        self.assertEqual(len(comment_calls), 2)
        self.assertEqual(posts[0]['comments'][0]['id'], 'devto:reply-1')

    def test_numeric_and_http_date_retry_after_are_honored(self):
        for header, expected in ((3, 3), (formatdate(NOW + 5, usegmt=True), 5)):
            clock = Clock()
            attempts = []

            def fake(url):
                attempts.append(url)
                if len(attempts) == 1:
                    raise too_many_requests(url, header)
                return {'ok': True}

            self.assertEqual(DevToAPI(fake, clock=clock, sleep=clock.sleep)('/test'), {'ok': True})
            self.assertEqual(len(attempts), 2)
            self.assertEqual(clock.sleeps, [expected])

    def test_normal_calls_are_spaced_and_missing_header_uses_thirty_seconds(self):
        clock = Clock()
        times = []
        client = DevToAPI(lambda url: times.append(clock()) or [], clock=clock, sleep=clock.sleep)

        client('/one')
        client('/two')

        self.assertAlmostEqual(times[1] - times[0], 1.1, places=3)
        self.assertEqual(clock.sleeps, [1.1])

        clock = Clock()
        attempts = []

        def no_retry_header(url):
            attempts.append(url)
            if len(attempts) == 1:
                raise too_many_requests(url)
            return []

        self.assertEqual(DevToAPI(no_retry_header, clock=clock, sleep=clock.sleep)('/test'), [])
        self.assertEqual(clock.sleeps, [30])

    def test_long_retry_after_stops_without_retry_and_other_errors_are_not_retried(self):
        for error in (too_many_requests('/test', 61), HTTPError('/test', 403, 'Forbidden', {}, None)):
            attempts = []
            clock = Clock()

            def fail(url):
                attempts.append(url)
                raise error

            with self.assertRaises(HTTPError):
                DevToAPI(fail, clock=clock, sleep=clock.sleep)('/test')
            self.assertEqual(len(attempts), 1)
            self.assertEqual(clock.sleeps, [])

    def test_repeated_429_stops_after_two_retries_and_article_is_retained(self):
        clock = Clock()
        calls = []

        def fake(url):
            calls.append(url)
            if '/comments' in url:
                raise too_many_requests(url, 0)
            return [response_article()]

        client = DevToAPI(fake, clock=clock, sleep=clock.sleep)
        with patch.object(devto, '_tags', return_value=['ai']):
            posts = devto.fetch_devto(now=NOW, http_get=client)[0]['top']

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]['comments'], [])
        self.assertEqual(len([url for url in calls if '/comments' in url]), 3)
        self.assertEqual(clock.sleeps, [1.1, 1.1, 1.1])


if __name__ == '__main__':
    unittest.main()
