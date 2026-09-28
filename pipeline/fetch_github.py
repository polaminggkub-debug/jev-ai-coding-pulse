"""Free GitHub issue/comment adapter with repository-scoped tool context."""
import os
from pathlib import Path
import sys

try:
    from .github_api import BudgetExhausted, GitHubAPI
    from .registry import mentions
    from .source_utils import api_url, epoch, get_json, in_window, iso_utc, now_epoch, source_listing
except ImportError:
    from github_api import BudgetExhausted, GitHubAPI
    from registry import mentions
    from source_utils import api_url, epoch, get_json, in_window, iso_utc, now_epoch, source_listing

REPOS_PATH = Path(__file__).resolve().parents[1] / 'config' / 'github_repos.txt'
REPO_TOOLS = {
    'anthropics/claude-code': 'Claude Code', 'openai/codex': 'Codex',
    'sst/opencode': 'OpenCode', 'google-gemini/gemini-cli': 'Gemini CLI',
    'QwenLM/qwen-code': 'Qwen Code', 'cline/cline': 'Cline',
    'Kilo-Org/kilocode': 'Kilo Code', 'Aider-AI/aider': 'Aider',
    'continuedev/continue': 'Continue',
}
BASE = 'https://api.github.com/repos'
MAX_ISSUES_PER_REPO = 5
MAX_COMMENTS_PER_ISSUE = 10


def _repos(path):
    names = [line.split('#', 1)[0].strip() for line in Path(path).read_text().splitlines()]
    return list(dict.fromkeys(name for name in names if name))


def _bot(row):
    user = row.get('user') or {}
    name = str(user.get('login') or '').casefold()
    return user.get('type') == 'Bot' or name.endswith('[bot]') or name == 'automoderator'


def _subjects(repo):
    name = REPO_TOOLS.get(repo, repo.split('/')[-1])
    return [{'name': name, 'zone': 'tool'}]


def _comment(row, repo):
    reactions = row.get('reactions') or {}
    return dict(id=f"comment:{row['id']}", body=row.get('body') or '',
                score=reactions.get('total_count'), created_utc=epoch(row.get('created_at')),
                author=(row.get('user') or {}).get('login'), url=row.get('html_url'),
                source='github', community=repo, implicit_subjects=_subjects(repo))


def _issue(row, repo, now, comments):
    created = epoch(row.get('created_at'))
    recent = in_window(created, now)
    if not recent and not comments:
        return None
    return dict(id=f"issue:{row['id']}", title=row.get('title') or '',
                selftext=row.get('body') or '', score=(row.get('reactions') or {}).get('total_count'),
                num_comments=row.get('comments') or 0, created_utc=created,
                url=row.get('html_url'), comments=comments, source='github', community=repo,
                implicit_subjects=_subjects(repo), context_only=not recent)


def _matches_registry(row):
    text = f"{row.get('title') or ''}\n{row.get('body') or ''}"
    return bool(mentions(text))


def _recent_comments(repo, number, now, api):
    url = f'{BASE}/{repo}/issues/{number}/comments'
    try:
        rows = api.get(api_url(url, per_page=MAX_COMMENTS_PER_ISSUE, page=1,
                              since=iso_utc(now - 5 * 86400)))
        if not isinstance(rows, list):
            raise ValueError('GitHub comments listing was not a list')
        rows = rows[:MAX_COMMENTS_PER_ISSUE]
        comments = [_comment(row, repo) for row in rows
                    if not _bot(row) and in_window(row.get('created_at'), now)]
        return comments, len(rows), len(comments)
    except Exception as error:
        print(f'GitHub comments partial in {repo}#{number}: {type(error).__name__}', file=sys.stderr)
        return [], 0, 0


def _latest_issues(repo, now, api):
    url = f'{BASE}/{repo}/issues'
    rows = api.get(api_url(url, per_page=MAX_ISSUES_PER_REPO, page=1, state='all',
                          sort='updated', direction='desc', since=iso_utc(now - 5 * 86400)))
    if not isinstance(rows, list):
        raise ValueError('GitHub listing was not a list')
    return rows[:MAX_ISSUES_PER_REPO]


def _can_request(api):
    return not api.stopped and api.calls < api.max_calls and api.remaining > api.reserve


def _fetch_repo(repo, now, api):
    rows = _latest_issues(repo, now, api)
    eligible = [row for row in rows if not _bot(row) and 'pull_request' not in row]
    issues = [row for row in eligible if _matches_registry(row)]
    stats = {'issues_fetched': len(rows), 'registry_matches': len(issues),
             'irrelevant_skipped': len(eligible) - len(issues), 'issues_kept': 0,
             'comments_fetched': 0, 'comments_kept': 0}
    posts = []
    for row in issues:
        comments = []
        fetched = kept = 0
        if _can_request(api):
            comments, fetched, kept = _recent_comments(repo, row.get('number'), now, api)
        stats['comments_fetched'] += fetched
        stats['comments_kept'] += kept
        post = _issue(row, repo, now, comments)
        if post is not None:
            posts.append(post)
    stats['issues_kept'] = len(posts)
    return source_listing('github', repo, posts), stats


def _budget_reason(api):
    if api.stop_reason:
        return api.stop_reason
    return 'reserve reached' if api.remaining <= api.reserve else 'request cap reached'


def fetch_github(*, now=None, http_get=None, token=None, repos=None, repos_path=REPOS_PATH):
    token = os.environ.get('GITHUB_TOKEN', '') if token is None else token
    if not token:
        print('Skipping GitHub: GITHUB_TOKEN is not configured.', file=sys.stderr)
        return []
    http_get = get_json if http_get is None else http_get
    now = now_epoch(now)
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    api = GitHubAPI(http_get, headers)
    try:
        api.start()
    except BudgetExhausted:
        print('Skipping GitHub: request quota is unavailable.', file=sys.stderr)
        return []
    repo_names = _repos(repos_path) if repos is None else list(dict.fromkeys(repos))
    output = []
    attempted = 0
    totals = {'issues_fetched': 0, 'registry_matches': 0, 'irrelevant_skipped': 0,
              'issues_kept': 0, 'comments_fetched': 0, 'comments_kept': 0}
    for repo in repo_names:
        if not _can_request(api):
            break
        attempted += 1
        try:
            listing, stats = _fetch_repo(repo, now, api)
            output.append(listing)
            for name, value in stats.items():
                totals[name] += value
        except Exception as error:
            print(f'GitHub repository skipped {repo}: {type(error).__name__}', file=sys.stderr)
    print('GitHub collection: ' + ' '.join(
        [f'repositories={attempted}/{len(repo_names)}'] +
        [f'{name}={value}' for name, value in totals.items()] + [f'api_calls={api.calls}']),
        file=sys.stderr)
    if not _can_request(api):
        omitted = len(repo_names) - attempted
        print(f'GitHub collection partial: {_budget_reason(api)}; omitted_repositories={omitted}',
              file=sys.stderr)
    return output


if __name__ == '__main__':
    import json
    print(json.dumps(fetch_github(), ensure_ascii=False))
