"""Public Bluesky AppView search. Authentication-required services are skipped."""
import sys

try:
    from .quality import comment_qualifies
    from .registry import R
    from .source_utils import api_url, attach_context, call_json, epoch, get_json, in_window, iso_utc, now_epoch, source_id, source_listing
except ImportError:
    from quality import comment_qualifies
    from registry import R
    from source_utils import api_url, attach_context, call_json, epoch, get_json, in_window, iso_utc, now_epoch, source_id, source_listing

SEARCH = 'https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts'
THREAD = 'https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread'


def _replies(node, source, now):
    output = []
    for child in (node.get('replies') or []):
        post = child.get('post') or {}
        record = post.get('record') or {}
        created = record.get('createdAt')
        if in_window(created, now):
            item = {'id': source_id(source, post.get('uri')), 'body': record.get('text', ''),
                    'created_utc': epoch(created), 'score': post.get('likeCount'),
                    'author': (post.get('author') or {}).get('handle'),
                    'url': f"https://bsky.app/profile/{(post.get('author') or {}).get('handle','')}/post/{str(post.get('uri','')).rsplit('/',1)[-1]}"}
            if comment_qualifies(item, now=now):
                output.append(attach_context(item, source, 'Bluesky'))
        output.extend(_replies(child, source, now))
    return output


def _thread(post, http_get, now):
    uri = post.get('uri')
    data = call_json(http_get, api_url(THREAD, uri=uri, depth=2, parentHeight=0))
    root = data.get('thread', {}) if isinstance(data, dict) else {}
    return _replies(root, 'bluesky', now)


def _post(raw, http_get, now):
    post = raw.get('post') or raw
    record = post.get('record') or {}
    created = record.get('createdAt')
    if not in_window(created, now) or int(post.get('likeCount') or 0) < 5:
        return None
    author = (post.get('author') or {}).get('handle', '')
    uri = post.get('uri', '')
    replies = _thread(post, http_get, now) if post.get('replyCount') else []
    return attach_context({'id': source_id('bluesky', uri), 'title': record.get('text', '')[:180],
        'selftext': record.get('text', ''), 'score': post.get('likeCount'),
        'num_comments': post.get('replyCount', 0), 'created_utc': epoch(created),
        'url': f"https://bsky.app/profile/{author}/post/{uri.rsplit('/',1)[-1]}",
        'comments': replies}, 'bluesky', 'Bluesky')


def _search(family, http_get, now):
    cursor, seen = None, set()
    for _ in range(10):
        params = dict(q=family, limit=100, sort='latest', since=iso_utc(now - 5 * 86400))
        if cursor:
            params['cursor'] = cursor
        payload = call_json(http_get, api_url(SEARCH, **params))
        yield from payload.get('posts', [])
        cursor = payload.get('cursor')
        if not cursor or cursor in seen:
            return
        seen.add(cursor)


def fetch_bluesky(*, now=None, http_get=None):
    """Search every family; one authorization/rate failure skips Bluesky cleanly."""
    posts = {}
    http_get = get_json if http_get is None else http_get
    now = now_epoch(now)
    for family, _, _ in R:
        try:
            for raw in _search(family, http_get, now):
                uri = (raw.get('post') or raw).get('uri')
                if source_id('bluesky', uri) in posts:
                    continue
                post = _post(raw, http_get, now)
                if post:
                    posts[post['id']] = post
        except Exception as error:
            print(f"Skipping Bluesky search: {error}", file=sys.stderr)
            return []
    return [source_listing('bluesky', 'Bluesky', list(posts.values()))]


if __name__ == '__main__':
    import json
    print(json.dumps(fetch_bluesky(), ensure_ascii=False))
