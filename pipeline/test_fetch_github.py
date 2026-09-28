"""GitHub adapter tests use fake HTTP exclusively."""
import tempfile
from contextlib import redirect_stderr
from io import BytesIO, StringIO
from pathlib import Path
from urllib.error import HTTPError
import unittest
from urllib.parse import parse_qs, urlsplit

from fetch_github import fetch_github, REPO_TOOLS
from github_api import BudgetExhausted, GitHubAPI
from source_utils import iso_utc

NOW = 1_800_000_000


def issue(number, *, age=1, user=None):
    return dict(id=number, number=number, title='An actual coding issue', body='Opus broke',
                user=user or {'login': 'developer', 'type': 'User'}, comments=8,
                created_at=iso_utc(NOW - age * 86400),
                html_url=f'https://github.com/openai/codex/issues/{number}',
                reactions={'total_count': 4})


def rate_limit(remaining):
    return {'resources': {'core': {'remaining': remaining}}}


def comment(comment_id, issue_number):
    return dict(id=comment_id, issue_url=f'https://api.github.com/repos/openai/codex/issues/{issue_number}',
                body=f'Comment {comment_id}', user={'login': 'developer', 'type': 'User'},
                created_at=iso_utc(NOW - 3600), html_url=f'https://github.com/openai/codex/issues/comments/{comment_id}')


class GitHubTests(unittest.TestCase):
    def test_token_absence_skips_without_http(self):
        def forbidden(*args, **kwargs):
            self.fail('Missing credentials must not issue HTTP requests')
        self.assertEqual(fetch_github(token='', http_get=forbidden), [])

    def test_recent_human_issues_and_comments_keep_native_metadata(self):
        calls = []

        def http(url, headers=None):
            calls.append((url, headers))
            if url.endswith('/rate_limit'):
                return rate_limit(5000)
            if urlsplit(url).path.endswith('/issues/1/comments'):
                rows = [comment(22, 1), comment(23, 1), comment(24, 1)]
                rows[1]['user'] = {'login': 'ci[bot]'}
                rows[2]['created_at'] = iso_utc(NOW - 7 * 86400)
                rows[0]['body'] = 'Useful detail'
                return rows
            return [issue(1), issue(2, user={'login': 'robot', 'type': 'Bot'}),
                    dict(issue(3), pull_request={})]

        result = fetch_github(repos=['openai/codex'], token='fake', now=NOW, http_get=http)
        self.assertEqual(len(result), 1)
        post = result[0]['top'][0]
        self.assertEqual(result[0]['community'], 'openai/codex')
        self.assertEqual(len(result[0]['top']), 1)
        self.assertEqual(post['implicit_subjects'], [{'name': 'Codex', 'zone': 'tool'}])
        self.assertEqual(post['num_comments'], 8)
        self.assertEqual([c['id'] for c in post['comments']], ['comment:22'])
        self.assertIsNone(post['comments'][0]['score'])
        self.assertTrue(all(h['Authorization'] == 'Bearer fake' for _, h in calls))

    def test_issue_comments_use_bounded_per_issue_endpoints(self):
        calls = []

        def http(url, headers=None):
            calls.append(url)
            if url.endswith('/rate_limit'):
                return rate_limit(5000)
            path = urlsplit(url).path
            if path.endswith('/issues/1/comments'):
                return [comment(22, 1)]
            if path.endswith('/issues/2/comments'):
                return [comment(23, 2)]
            return [issue(1), issue(2)]

        result = fetch_github(repos=['openai/codex'], token='fake', now=NOW, http_get=http)
        per_issue_calls = [url for url in calls if urlsplit(url).path.endswith('/comments')]

        self.assertEqual(len(per_issue_calls), 2)
        self.assertTrue(all(parse_qs(urlsplit(url).query)['per_page'] == ['10']
                            for url in per_issue_calls))
        self.assertEqual([len(post['comments']) for post in result[0]['top']], [1, 1])

    def test_remaining_quota_reserve_stops_later_repositories_and_keeps_prior_data(self):
        calls = []

        def http(url, headers=None):
            calls.append(url)
            if url.endswith('/rate_limit'):
                return rate_limit(102)
            if '/repos/openai/codex/issues?' in url:
                return [issue(1)]
            if urlsplit(url).path.endswith('/issues/1/comments'):
                return [comment(22 + offset, 1) for offset in range(100)]
            return [issue(2)]

        log = StringIO()
        with redirect_stderr(log):
            result = fetch_github(repos=['openai/codex', 'anthropics/claude-code'],
                                  token='fake', now=NOW, http_get=http)

        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0], 'https://api.github.com/rate_limit')
        self.assertIn('repositories=1/2', log.getvalue())
        self.assertIn('api_calls=3', log.getvalue())
        self.assertIn('partial: reserve reached; omitted_repositories=1', log.getvalue())
        self.assertEqual(len(result[0]['top']), 1)
        self.assertEqual(len(result[0]['top'][0]['comments']), 10)
        self.assertEqual(result[0]['top'][0]['comments'][0]['id'], 'comment:22')
        comment_query = next(parse_qs(urlsplit(url).query) for url in calls
                             if urlsplit(url).path.endswith('/issues/1/comments'))
        self.assertEqual(comment_query['per_page'], ['10'])
        self.assertNotIn('/repos/anthropics/claude-code/issues?', '\n'.join(calls))

    def test_fetch_uses_five_issue_request_and_does_not_paginate(self):
        pages = []
        issue_rows = [issue(n, age=7) for n in range(1, 7)]
        issue_rows[4] = issue(5, age=1)

        def http(url, headers=None):
            if url.endswith('/rate_limit'):
                return rate_limit(5000)
            query = parse_qs(urlsplit(url).query)
            if urlsplit(url).path.endswith('/issues'):
                pages.append((query['page'][0], query['per_page'][0]))
                return issue_rows
            number = int(urlsplit(url).path.split('/')[-2])
            return [comment(1000 + number, number)]

        result = fetch_github(repos=['openai/codex'], token='fake', now=NOW, http_get=http)
        self.assertEqual(pages, [('1', '5')])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['top']), 5)
        self.assertTrue(result[0]['top'][0]['context_only'])
        self.assertFalse(result[0]['top'][-1]['context_only'])
        self.assertEqual([len(post['comments']) for post in result[0]['top']], [1] * 5)

    def test_skips_issues_without_registry_names_before_comment_requests(self):
        calls = []

        def http(url, headers=None):
            calls.append(url)
            if url.endswith('/rate_limit'):
                return rate_limit(5000)
            return [dict(issue(1), title='How do I configure a build?', body='No model mentioned')]

        log = StringIO()
        with redirect_stderr(log):
            result = fetch_github(repos=['openai/codex'], token='fake', now=NOW, http_get=http)

        self.assertEqual(result[0]['top'], [])
        self.assertFalse(any(urlsplit(url).path.endswith('/comments') for url in calls))
        self.assertIn('registry_matches=0', log.getvalue())
        self.assertIn('irrelevant_skipped=1', log.getvalue())

    def test_seeded_repo_tools_and_config_comments(self):
        self.assertEqual(len(REPO_TOOLS), 9)
        self.assertEqual(REPO_TOOLS['QwenLM/qwen-code'], 'Qwen Code')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'repos.txt'
            path.write_text('# seed\nopenai/codex # note\nopenai/codex\n')
            calls = []
            def http(url, headers=None):
                calls.append(url)
                return rate_limit(1000) if url.endswith('/rate_limit') else []
            result = fetch_github(repos_path=path, token='fake', now=NOW, http_get=http)
            self.assertEqual(len(calls), 2)
            self.assertEqual(result[0]['community'], 'openai/codex')

    def test_quota_error_keeps_recent_issue_and_stops_later_repositories(self):
        calls = []

        def http(url, headers=None):
            calls.append(url)
            if url.endswith('/rate_limit'):
                return rate_limit(5000)
            if urlsplit(url).path.endswith('/issues/1/comments'):
                raise HTTPError(url, 403, 'API rate limit exceeded', {}, BytesIO(b'{"message":"API rate limit exceeded"}'))
            return [issue(1)]

        result = fetch_github(repos=['openai/codex', 'anthropics/claude-code'], token='fake',
                              now=NOW, http_get=http)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(result[0]['top']), 1)
        self.assertEqual(result[0]['top'][0]['comments'], [])
        self.assertNotIn('/repos/anthropics/claude-code/issues?', '\n'.join(calls))

    def test_request_budget_caps_attempts_at_800(self):
        calls = []

        def http(url, headers=None):
            calls.append(url)
            return rate_limit(10000) if url.endswith('/rate_limit') else []

        api = GitHubAPI(http, {})
        api.start()
        for _ in range(805):
            try:
                api.get('https://api.github.com/repos/openai/codex/issues')
            except BudgetExhausted:
                break
        self.assertEqual(api.calls, 800)
        self.assertEqual(len(calls), 800)


if __name__ == '__main__':
    unittest.main()
