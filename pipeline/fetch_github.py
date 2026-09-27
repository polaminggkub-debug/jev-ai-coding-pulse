"""Free GitHub issue/comment adapter with repository-scoped tool context."""
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

try:
    from .github_api import BudgetExhausted, GitHubAPI
    from .source_utils import api_url, epoch, get_json, in_window, iso_utc, now_epoch, source_listing
except ImportError:
    from github_api import BudgetExhausted, GitHubAPI
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


def _repos(path):
    names = [line.split('#', 1)[0].strip() for line in Path(path).read_text().splitlines()]
    return list(dict.fromkeys(name for name in names if name))


def _bot(row):
    user = row.get('user') or {}
    name = str(user.get('login') or '').casefold()
    return user.get('type') == 'Bot' or name.endswith('[bot]') or name == 'automoderator'


def _pages(url, api, **params):
    seen = set()
    page = 1
    while True:
        try:
            rows = api.get(api_url(url, per_page=100, page=page, **params))
        except BudgetExhausted:
            break
        if not isinstance(rows, list):
            raise ValueError('GitHub listing was not a list')
        fresh = [row for row in rows if row.get('id') not in seen]
        for row in fresh:
            seen.add(row.get('id'))
            yield row
        if len(rows) < 100 or not fresh:
            break
        page += 1


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


def _issue_number(comment):
    path = urlsplit(str(comment.get('issue_url') or '')).path.rstrip('/')
    try:
        return int(path.rsplit('/', 1)[-1])
    except (TypeError, ValueError):
        return None


def _recent_comments(repo, now, api):
    url = f'{BASE}/{repo}/issues/comments'
    comments = {}
    try:
        rows = _pages(url, api, since=iso_utc(now - 5 * 86400))
        for row in rows:
            number = _issue_number(row)
            if number is None or _bot(row) or not in_window(row.get('created_at'), now):
                continue
            comments.setdefault(number, []).append(_comment(row, repo))
    except Exception as error:
        print(f'GitHub comments partial in {repo}: {type(error).__name__}', file=sys.stderr)
    return comments


def _fetch_repo(repo, now, api):
    rows = _pages(f'{BASE}/{repo}/issues', api, state='all',
                  sort='updated', direction='desc', since=iso_utc(now - 5 * 86400))
    issues = [row for row in rows if not _bot(row) and 'pull_request' not in row]
    comments = _recent_comments(repo, now, api) if issues else {}
    posts = [post for row in issues
             if (post := _issue(row, repo, now, comments.get(row.get('number'), []))) is not None]
    return source_listing('github', repo, posts)


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
    for repo in repo_names:
        if api.stopped or api.calls >= api.max_calls or api.remaining <= api.reserve:
            break
        attempted += 1
        try:
            output.append(_fetch_repo(repo, now, api))
        except Exception as error:
            print(f'GitHub repository skipped {repo}: {type(error).__name__}', file=sys.stderr)
    print(f'GitHub collection: repositories={attempted}/{len(repo_names)} api_calls={api.calls}',
          file=sys.stderr)
    if api.stopped or api.calls >= api.max_calls or api.remaining <= api.reserve:
        omitted = len(repo_names) - attempted
        print(f'GitHub collection partial: {_budget_reason(api)}; omitted_repositories={omitted}',
              file=sys.stderr)
    return output


if __name__ == '__main__':
    import json
    print(json.dumps(fetch_github(), ensure_ascii=False))
