"""Idempotent import of legacy cache/labels/raw before deleting those sources."""
import json
from pathlib import Path

try:
    from . import store
    from .classify import jobs_from_raw, _pair_id, QUESTION_VERSION
    from .versions import extract_version
    from .registry import R
except ImportError:
    import store
    from classify import jobs_from_raw, _pair_id, QUESTION_VERSION
    from versions import extract_version
    from registry import R


def identity(row):
    return (str(row.get('id') or row.get('comment_id') or
                _pair_id(row.get('kind', 'comment'), '', row.get('link', ''))), row['subject'])


def signature(row):
    return (row['id'], row['subject'], row['q'], row['label'],
            json.dumps(row.get('probs'), sort_keys=True), store.timestamp(row['judged_at']))


def migrate(root):
    with store.run_lock(root, 'migration'):
        return _migrate(root)


def _legacy_records(legacy, key, metadata, fallback, raw_has_item=False):
    item = dict(metadata.get(key, {}))
    judged = legacy.get('judged_at') or item.get('judged_at') or fallback
    source_created = item.get('created_utc')
    parent_created = item.get('parent_created_utc') or item.get('post_created_utc')
    legacy_created = legacy.get('created_utc')
    same_as_judged = (legacy_created is not None and judged is not None
                      and store.timestamp(legacy_created) == store.timestamp(judged))
    if source_created is not None:
        item['created_utc_source'] = 'item'
    elif parent_created is not None:
        item['created_utc_source'] = 'parent'
    elif legacy_created is not None and not same_as_judged and not raw_has_item:
        source_created = legacy_created
        item['created_utc'] = legacy_created
        item['created_utc_source'] = 'item'
    else:
        item['created_utc'] = None
        item['judged_at'] = store.timestamp(judged)
        item['created_utc_source'] = 'judged'
    created = source_created or parent_created or (legacy_created if not raw_has_item else None) or judged
    kind = item.get('kind') or ('post' if key[0].startswith('post:') else 'comment')
    item.update(id=key[0], subject=key[1], kind=kind)
    for field, default in [('text', ''), ('sub', ''), ('link', ''), ('thread', ''),
                           ('thread_url', ''), ('score', 0), ('thread_score', 0)]:
        item.setdefault(field, default)
    if 'version' not in item:
        item['version'] = extract_version(key[1], item['text'], item['thread'])
    if not item.get('zone'):
        item['zone'] = next((zone for subject, zone, _ in R if subject == key[1]), 'tool')
    judgment = dict(id=key[0], kind=kind, subject=key[1], q=legacy.get('q') or QUESTION_VERSION,
                    label=legacy['label'], probs=legacy.get('probs'),
                    created_utc=store.timestamp(created), judged_at=store.timestamp(judged))
    return item, judgment


def _migrate(root):
    root = Path(root)
    paths = [root / name for name in ('classify_cache.json', 'labeled.json', 'raw.json')]
    if not any(p.exists() for p in paths):
        return 0
    cache, labels, raw = [json.loads(p.read_text(encoding='utf-8')) if p.exists()
                          else ({} if p.name == 'raw.json' else []) for p in paths]
    fallback = min(p.stat().st_mtime for p in paths if p.exists())
    metadata = jobs_from_raw(raw, apply_quality=False)
    raw_keys = set(metadata)
    for row in labels:
        key = identity(row)
        current = metadata.get(key, {})
        merged = {**current, **row, 'id': key[0]}
        # Raw event and parent dates beat timestamps copied from an old
        # judgment record, which may already contain a fallback date.
        if 'created_utc' in current:
            merged['created_utc'] = current.get('created_utc')
        if current.get('parent_created_utc') is not None:
            merged['parent_created_utc'] = current['parent_created_utc']
        metadata[key] = merged
    existing = {signature(r) for r in store.read_rows(root / 'judgments')}
    additions = []
    items = []
    # Preserve differing legacy answers too; identical cache/label copies coalesce.
    for legacy in [*cache, *labels]:
        if legacy.get('label') not in store.LABELS:
            continue
        key = identity(legacy)
        if not all(key):
            raise ValueError('Legacy judgment has no recoverable identity')
        item, judgment = _legacy_records(
            legacy, key, metadata, fallback, raw_has_item=key in raw_keys)
        items.append(item)
        sig = signature(judgment)
        if sig not in existing:
            additions.append(judgment)
            existing.add(sig)
    store.update_items(root, items)
    for judgment in additions:
        store.append_judgment(root, judgment)
    store.rebuild_daily(root)
    # Verify all source judgments are represented before removing the originals.
    saved = {signature(r) for r in store.read_rows(root / 'judgments')}
    if not existing <= saved:
        raise RuntimeError('Incomplete migration; legacy files retained')
    for path in paths:
        path.unlink(missing_ok=True)
    print(f'Migrated {len(additions)} legacy judgments')
    return len(additions)


if __name__ == '__main__':
    migrate(Path(__file__).resolve().parent.parent / 'data')
