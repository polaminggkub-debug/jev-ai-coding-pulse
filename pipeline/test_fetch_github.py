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
            if '/issues/comments?' in url:
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

    def test_issue_comments_use_one_bulk_endpoint_per_repository(self):
        calls = []

        def http(url, headers=None):
            calls.append(url)
            if url.endswith('/rate_limit'):
                return rate_limit(5000)
            if '/issues/comments?' in url:
                return [comment(22, 1), comment(23, 2)]
            return [issue(1), issue(2)]

        result = fetch_github(repos=['openai/codex'], token='fake', now=NOW, http_get=http)
        bulk_calls = [url for url in calls if '/issues/comments?' in url]
        per_issue_calls = [url for url in calls if '/issues/' in url and '/comments?' in url
                           and '/issues/comments?' not in url]

        self.assertEqual(len(bulk_calls), 1)
        self.assertEqual(per_issue_calls, [])
        self.assertEqual([len(post['comments']) for post in result[0]['top']], [1, 1])

    def test_remaining_quota_reserve_stops_later_repositories_and_keeps_prior_data(self):
        calls = []

        def http(url, headers=None):
            calls.append(url)
            if url.endswith('/rate_limit'):
                return rate_limit(102)
            if '/issues/comments?' in url:
                return [comment(22 + offset, 1) for offset in range(100)]
            if '/repos/openai/codex/issues?' in url:
                return [issue(1)]
            return [issue(2)]

        log = StringIO()
        with redirect_stderr(log):
            result = fetch_github(repos=['openai/codex', 'anthropics/claude-code'],
                                  token='fake', now=NOW, http_get=http)

        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0], 'https://api.github.com/rate_limit')
        self.assertIn('repositories=1/2 api_calls=3', log.getvalue())
        self.assertIn('partial: reserve reached; omitted_repositories=1', log.getvalue())
        self.assertEqual(len(result[0]['top']), 1)
        self.assertEqual(len(result[0]['top'][0]['comments']), 100)
        self.assertEqual(result[0]['top'][0]['comments'][0]['id'], 'comment:22')
        self.assertNotIn('/repos/anthropics/claude-code/issues?', '\n'.join(calls))

    def test_pagination_repo_failures_and_old_parent_context(self):
        pages = []

        def http(url, headers=None):
            if url.endswith('/rate_limit'):
                return rate_limit(5000)
            if '/broken/' in url:
                raise OSError('fixture failure')
            query = parse_qs(urlsplit(url).query)
            page = int(query['page'][0])
            if '/issues/comments?' in url:
                start = (page - 1) * 100 + 1
                end = min(page * 100, 101)
                return [comment(1000 + number, number) for number in range(start, end + 1)]
            pages.append(page)
            return [issue(n, age=7) for n in range(1, 101)] if page == 1 else [issue(101)]

        result = fetch_github(repos=['broken/repo', 'openai/codex'], token='fake', now=NOW, http_get=http)
        self.assertEqual(pages, [1, 2])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['top']), 101)
        self.assertTrue(result[0]['top'][0]['context_only'])
        self.assertFalse(result[0]['top'][-1]['context_only'])
        self.assertEqual([len(post['comments']) for post in result[0]['top']], [1] * 100 + [1])

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
            if '/issues/comments?' in url:
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
