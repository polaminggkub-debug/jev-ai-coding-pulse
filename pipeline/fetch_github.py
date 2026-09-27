"""Free GitHub issue/comment adapter with repository-scoped tool context."""
import os
from pathlib import Path
import sys

try:
    from .source_utils import api_url, epoch, get_json, in_window, iso_utc, now_epoch, source_listing
except ImportError:
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


def _pages(url, http_get, headers, **params):
    seen = set()
    page = 1
    while True:
        rows = http_get(api_url(url, per_page=100, page=page, **params), headers=headers)
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


def _issue(row, repo, now, http_get, headers):
    url = f"{BASE}/{repo}/issues/{row['number']}/comments"
    comments = [_comment(comment, repo) for comment in _pages(
        url, http_get, headers, since=iso_utc(now - 5 * 86400))
        if not _bot(comment) and in_window(comment.get('created_at'), now)]
    created = epoch(row.get('created_at'))
    recent = in_window(created, now)
    if not recent and not comments:
        return None
    return dict(id=f"issue:{row['id']}", title=row.get('title') or '',
                selftext=row.get('body') or '', score=(row.get('reactions') or {}).get('total_count'),
                num_comments=row.get('comments') or 0, created_utc=created,
                url=row.get('html_url'), comments=comments, source='github', community=repo,
                implicit_subjects=_subjects(repo), context_only=not recent)


def _fetch_repo(repo, now, http_get, headers):
    rows = _pages(f'{BASE}/{repo}/issues', http_get, headers, state='all',
                  sort='updated', direction='desc', since=iso_utc(now - 5 * 86400))
    posts = []
    for row in rows:
        if _bot(row) or 'pull_request' in row:
            continue
        try:
            post = _issue(row, repo, now, http_get, headers)
            if post:
                posts.append(post)
        except Exception as error:
            print(f"GitHub issue skipped in {repo}: {type(error).__name__}", file=sys.stderr)
    return source_listing('github', repo, posts)


def fetch_github(*, now=None, http_get=None, token=None, repos=None, repos_path=REPOS_PATH):
    token = os.environ.get('GITHUB_TOKEN', '') if token is None else token
    if not token:
        print('Skipping GitHub: GITHUB_TOKEN is not configured.', file=sys.stderr)
        return []
    http_get = get_json if http_get is None else http_get
    now = now_epoch(now)
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    output = []
    for repo in _repos(repos_path) if repos is None else dict.fromkeys(repos):
        try:
            output.append(_fetch_repo(repo, now, http_get, headers))
        except Exception as error:
            print(f'GitHub repository skipped {repo}: {type(error).__name__}', file=sys.stderr)
    return output


if __name__ == '__main__':
    import json
    print(json.dumps(fetch_github(), ensure_ascii=False))
