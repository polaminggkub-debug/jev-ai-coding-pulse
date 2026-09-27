"""GitHub adapter tests use fake HTTP exclusively."""
import tempfile
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit

from fetch_github import fetch_github, REPO_TOOLS
from source_utils import iso_utc

NOW = 1_800_000_000


def issue(number, *, age=1, user=None):
    return dict(id=number, number=number, title='An actual coding issue', body='Opus broke',
                user=user or {'login': 'developer', 'type': 'User'}, comments=8,
                created_at=iso_utc(NOW - age * 86400),
                html_url=f'https://github.com/openai/codex/issues/{number}',
                reactions={'total_count': 4})


class GitHubTests(unittest.TestCase):
    def test_token_absence_skips_without_http(self):
        def forbidden(*args, **kwargs):
            self.fail('Missing credentials must not issue HTTP requests')
        self.assertEqual(fetch_github(token='', http_get=forbidden), [])

    def test_recent_human_issues_and_comments_keep_native_metadata(self):
        calls = []

        def http(url, headers=None):
            calls.append((url, headers))
            if '/comments?' in url:
                return [dict(id=22, body='Useful detail', user={'login': 'dev'},
                             created_at=iso_utc(NOW - 3600), html_url=url + '#22'),
                        dict(id=23, body='bot', user={'login': 'ci[bot]'},
                             created_at=iso_utc(NOW - 3600)),
                        dict(id=24, body='old', user={'login': 'dev'},
                             created_at=iso_utc(NOW - 7 * 86400))]
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

    def test_pagination_repo_failures_and_old_parent_context(self):
        pages = []

        def http(url, headers=None):
            if '/broken/' in url:
                raise OSError('fixture failure')
            query = parse_qs(urlsplit(url).query)
            page = int(query['page'][0])
            if '/comments?' in url:
                return [dict(id=9, body='Recent Opus detail', user={'login': 'dev'},
                             created_at=iso_utc(NOW - 3600))]
            pages.append(page)
            return [issue(n, age=7) for n in range(100)] if page == 1 else [issue(101)]

        result = fetch_github(repos=['broken/repo', 'openai/codex'], token='fake', now=NOW, http_get=http)
        self.assertEqual(pages, [1, 2])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['top']), 101)
        self.assertTrue(result[0]['top'][0]['context_only'])
        self.assertFalse(result[0]['top'][-1]['context_only'])

    def test_seeded_repo_tools_and_config_comments(self):
        self.assertEqual(len(REPO_TOOLS), 9)
        self.assertEqual(REPO_TOOLS['QwenLM/qwen-code'], 'Qwen Code')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'repos.txt'
            path.write_text('# seed\nopenai/codex # note\nopenai/codex\n')
            calls = []
            result = fetch_github(repos_path=path, token='fake', now=NOW,
                                  http_get=lambda url, headers=None: calls.append(url) or [])
            self.assertEqual(len(calls), 1)
            self.assertEqual(result[0]['community'], 'openai/codex')


if __name__ == '__main__':
    unittest.main()
