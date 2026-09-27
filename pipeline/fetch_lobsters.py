"""Lobsters AI and vibecoding tag stories with their recent comments."""
import sys

try:
    from .quality import comment_qualifies
    from .source_utils import attach_context, call_json, epoch, in_window, maybe_int, now_epoch, source_id, source_listing
    from .source_utils import get_json, plain_text
except ImportError:
    from quality import comment_qualifies
    from source_utils import attach_context, call_json, epoch, in_window, maybe_int, now_epoch, source_id, source_listing
    from source_utils import get_json, plain_text

TAGS = ('ai', 'vibecoding')
BASE = 'https://lobste.rs'


def _comments(rows, now):
    output = []
    for raw in rows or []:
        created = raw.get('created_at')
        if not in_window(created, now):
            continue
        author = raw.get('commenting_user')
        if isinstance(author, dict):
            author = author.get('username')
        elif not isinstance(author, str):
            author = None
        comment = {'id': source_id('lobsters', raw.get('short_id') or raw.get('id')),
                   'body': plain_text(raw.get('comment')), 'score': maybe_int(raw.get('score')),
                   'created_utc': epoch(created), 'author': author,
                   'url': raw.get('url')}
        if comment_qualifies(comment, now=now):
            output.append(attach_context(comment, 'lobsters', 'Lobsters'))
    return output


def _story(raw, http_get, now):
    created = raw.get('created_at')
    if not in_window(created, now) or maybe_int(raw.get('score')) is None or int(raw['score']) < 5:
        return None
    comments = []
    if raw.get('short_id'):
        detail = call_json(http_get, f"{BASE}/s/{raw['short_id']}.json")
        comments = _comments(detail.get('comments', []), now)
    return attach_context({'id': source_id('lobsters', raw.get('short_id') or raw.get('id')),
        'title': raw.get('title') or '', 'selftext': '', 'score': maybe_int(raw.get('score')),
        'num_comments': raw.get('comment_count', len(comments)), 'created_utc': epoch(created),
        'url': raw.get('short_id_url') or f"{BASE}/s/{raw.get('short_id', '')}", 'comments': comments}, 'lobsters', 'Lobsters')


def fetch_lobsters(*, now=None, http_get=None):
    """Fetch both requested tag feeds; an unavailable tag does not discard the other."""
    now, http_get = now_epoch(now), get_json if http_get is None else http_get
    stories = {}
    for tag in TAGS:
        try:
            rows = call_json(http_get, f'{BASE}/t/{tag}.json')
            for raw in rows if isinstance(rows, list) else []:
                story = _story(raw, http_get, now)
                if story:
                    stories[story['id']] = story
        except Exception as error:
            print(f"Lobsters tag {tag} skipped: {type(error).__name__}", file=sys.stderr)
    return [source_listing('lobsters', 'Lobsters', list(stories.values()))]


if __name__ == '__main__':
    import json
    print(json.dumps(fetch_lobsters(), ensure_ascii=False))
