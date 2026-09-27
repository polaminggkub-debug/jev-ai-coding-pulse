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


def _legacy_records(legacy, key, metadata, fallback):
    item = dict(metadata.get(key, {}))
    judged = legacy.get('judged_at') or item.get('judged_at') or fallback
    created = legacy.get('created_utc') or item.get('created_utc') or judged
    kind = item.get('kind') or ('post' if key[0].startswith('post:') else 'comment')
    item.update(id=key[0], subject=key[1], kind=kind, created_utc=created)
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
    metadata = jobs_from_raw(raw)
    for row in labels:
        key = identity(row)
        metadata[key] = {**metadata.get(key, {}), **row, 'id': key[0]}
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
        item, judgment = _legacy_records(legacy, key, metadata, fallback)
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
