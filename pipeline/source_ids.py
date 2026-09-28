"""Recover stable source-prefixed item identities."""
from urllib.parse import urlsplit

try:
    from .source_identity import prefixed_id
except ImportError:
    from source_identity import prefixed_id


def _path_id(link, kind):
    """Recover a stable ID from a source URL when an adapter omits it."""
    parts = [part for part in urlsplit(link or '').path.split('/') if part]
    try:
        index = parts.index('comments')
        if kind == 'comment' and len(parts) > index + 3:
            return parts[-1]
        if len(parts) > index + 1:
            return parts[index + 1]
    except ValueError:
        pass
    return ''


def _pair_id(kind, raw_id, link, source='reddit'):
    item_id = str(raw_id or _path_id(link, kind) or '')
    if not item_id:
        return ''
    if kind == 'post' and not item_id.startswith('post:'):
        item_id = f'post:{item_id}'
    return prefixed_id(source, item_id)
