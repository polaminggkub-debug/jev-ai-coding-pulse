"""Dev.to AI/model article search and free article comments API."""
import sys

try:
    from .devto_api import DevToAPI
    from .quality import comment_qualifies
    from .registry import R
    from .source_utils import api_url, attach_context, call_json, epoch, in_window, now_epoch, source_id, source_listing
    from .source_utils import get_json, plain_text
except ImportError:
    from devto_api import DevToAPI
    from quality import comment_qualifies
    from registry import R
    from source_utils import api_url, attach_context, call_json, epoch, in_window, now_epoch, source_id, source_listing
    from source_utils import get_json, plain_text

BASE = 'https://dev.to/api/articles'
TAG_ALIASES = {'Claude Code': 'claude', 'Claude Opus': 'claude', 'Claude Sonnet': 'claude',
               'GPT / ChatGPT': 'chatgpt', 'Gemini': 'gemini', 'Codex': 'codex'}


def _tags():
    return list(dict.fromkeys(['ai', 'claude', *[TAG_ALIASES.get(name, name.lower().split()[0])
                                                   for name, _, _ in R]]))


def _flatten(rows):
    for row in rows if isinstance(rows, list) else []:
        yield row
        yield from _flatten(row.get('children', []))


def _comments(article_id, http_get, now):
    url = api_url('https://dev.to/api/comments', a_id=article_id, per_page=1000)
    rows = call_json(http_get, url)
    comments = []
    for raw in _flatten(rows):
        created = raw.get('created_at') or raw.get('createdAt')
        if not in_window(created, now):
            continue
        author = raw.get('user') or {}
        comment = {'id': source_id('devto', raw.get('id_code') or raw.get('id')), 'body': plain_text(raw.get('body_html') or raw.get('body_markdown')),
                   'created_utc': epoch(created), 'score': raw.get('positive_reactions_count'),
                   'author': author.get('username') or raw.get('user_name'),
                   'url': raw.get('url') or ('https://dev.to' + raw['path'] if raw.get('path') else '')}
        if comment_qualifies(comment, now=now):
            comments.append(attach_context(comment, 'devto', 'Dev.to'))
    return comments


def _article(raw, http_get, now):
    created = raw.get('published_at') or raw.get('created_at')
    if not in_window(created, now) or int(raw.get('positive_reactions_count') or 0) < 5:
        return None
    article_id = raw.get('id')
    try:
        comments = _comments(article_id, http_get, now) if article_id else []
    except Exception as error:
        print(f"Dev.to comments for {article_id} unavailable: {type(error).__name__} "
              f"(status={getattr(error, 'code', 'unknown')})", file=sys.stderr)
        comments = []
    url = raw.get('url') or raw.get('canonical_url') or ''
    return attach_context({'id': source_id('devto', article_id or url),
        'title': raw.get('title') or '', 'selftext': plain_text(raw.get('description')),
        'score': raw.get('positive_reactions_count'), 'num_comments': raw.get('comments_count', 0),
        'created_utc': epoch(created), 'url': url, 'comments': comments}, 'devto', 'Dev.to')


def _articles(tag, http_get, now):
    seen = set()
    for page in range(1, 11):
        rows = call_json(http_get, api_url(BASE, tag=tag, top=5, per_page=100, page=page))
        if not isinstance(rows, list):
            return
        fresh = [row for row in rows if row.get('id') not in seen]
        for row in fresh:
            seen.add(row.get('id'))
            yield row
        if len(rows) < 100 or not fresh:
            return
        if all(not in_window(row.get('published_at') or row.get('created_at'), now) for row in rows):
            return


def fetch_devto(*, now=None, http_get=None):
    """Search AI plus every registered model family through Dev.to tags."""
    now = now_epoch(now)
    http_get = DevToAPI(get_json) if http_get is None else http_get
    articles = {}
    for tag in _tags():
        try:
            for raw in _articles(tag, http_get, now):
                if source_id('devto', raw.get('id')) in articles:
                    continue
                article = _article(raw, http_get, now)
                if article:
                    articles[article['id']] = article
        except Exception as error:
            print(f"Dev.to tag {tag} skipped: {type(error).__name__} "
                  f"(status={getattr(error, 'code', 'unknown')})", file=sys.stderr)
    return [source_listing('devto', 'Dev.to', list(articles.values()))]


if __name__ == '__main__':
    import json
    print(json.dumps(fetch_devto(), ensure_ascii=False))
