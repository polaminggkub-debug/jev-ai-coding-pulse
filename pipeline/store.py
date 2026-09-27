"""Append-only decisions, refreshable metadata, and derived UTC daily counts."""
import datetime as dt
import json
import fcntl
from contextlib import contextmanager
import os
from pathlib import Path

LABELS = ("praise", "complaint", "mixed", "no_opinion")


@contextmanager
def run_lock(root, name):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / ('.' + name + '.lock')).open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def timestamp(value=None):
    if value is None:
        return dt.datetime.now(dt.timezone.utc).timestamp()
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.timestamp()
    return float(value)


def date(value):
    return dt.datetime.fromtimestamp(timestamp(value), dt.timezone.utc).date().isoformat()


def resolved_created_utc(item, judgment=None):
    """Resolve event time: item, parent post, judgment creation, then judgment time."""
    judgment = judgment or {}
    source = _created_source(item, judgment)
    item_date = item.get('created_utc') if source == 'item' else None
    parent_date = (item.get('parent_created_utc') or item.get('post_created_utc')
                   if source == 'parent' else None)
    for value in (item_date, parent_date, judgment.get('created_utc'),
                  judgment.get('judged_at'), item.get('judged_at')):
        if value is not None and value != '':
            return value
    return None


def read_rows(directory):
    for path in sorted(Path(directory).glob('*.jsonl')):
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                yield json.loads(line)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    temporary.replace(path)


def append_judgment(root, row):
    path = Path(root) / 'judgments' / (date(row['created_utc'])[:7] + '.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def append_item(root, row, *, fallback=None):
    item = {k: v for k, v in row.items() if k != 'comment_id'}
    item['text'] = (item.get('text') or '')[:400]
    created = resolved_created_utc(item) if fallback is None else resolved_created_utc(
        item, {'judged_at': fallback})
    if created is None:
        raise ValueError('Item has no creation date or parent post date')
    path = Path(root) / 'items' / (date(created)[:7] + '.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(item, ensure_ascii=False, separators=(',', ':')) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def judgment_index(root):
    return {(r['id'], r['subject'], r['q']): r for r in read_rows(Path(root) / 'judgments')}


def _created_source(item, judgment=None):
    source = item.get('created_utc_source')
    if source in {'item', 'parent', 'judged'}:
        return source
    created = item.get('created_utc')
    if created is not None:
        # Older runs copied the current time into both records when source and
        # parent timestamps were absent. Recover that provenance once.
        if judgment and judgment.get('created_utc') is not None and judgment.get('judged_at') is not None:
            values = (created, judgment['created_utc'], judgment['judged_at'])
            if len({timestamp(value) for value in values}) == 1:
                if item.get('parent_created_utc') is not None or item.get('post_created_utc') is not None:
                    return 'parent'
                return 'judged'
        return 'item'
    if item.get('parent_created_utc') is not None or item.get('post_created_utc') is not None:
        return 'parent'
    return 'judged' if item.get('judged_at') is not None else None


def _merge_item(item, previous, judgment):
    """Refresh metadata without losing a known item date or retaining a fallback."""
    previous_source = _created_source(previous, judgment)
    if item.get('created_utc') is None and previous_source == 'item':
        item['created_utc'] = previous.get('created_utc')
    if item.get('parent_created_utc') is None:
        item['parent_created_utc'] = previous.get('parent_created_utc')
    if item.get('judged_at') is None:
        item['judged_at'] = previous.get('judged_at')
    if item.get('created_utc') is not None:
        item['created_utc_source'] = 'item'
    elif item.get('parent_created_utc') is not None:
        item['created_utc_source'] = 'parent'
    elif item.get('judged_at') is not None:
        item['created_utc_source'] = 'judged'
    return item


def update_items(root, rows):
    directory = Path(root) / 'items'
    items = {(r['id'], r['subject']): r for r in read_rows(directory)}
    judgments = {}
    for judgment in read_rows(Path(root) / 'judgments'):
        key = (judgment['id'], judgment['subject'])
        if key not in judgments or timestamp(judgment['judged_at']) >= timestamp(judgments[key]['judged_at']):
            judgments[key] = judgment
    fields = ('id', 'kind', 'sub', 'score', 'link', 'thread', 'thread_score',
              'thread_url', 'subject', 'zone', 'version', 'text', 'created_utc',
              'parent_created_utc', 'post_created_utc', 'judged_at', 'created_utc_source')
    for row in rows:
        item = {field: row.get(field) for field in fields}
        item['text'] = (item['text'] or '')[:400]
        key = (item['id'], item['subject'])
        incoming_source = _created_source(item)
        if incoming_source:
            item['created_utc_source'] = incoming_source
        if key in items:
            item = _merge_item(item, items[key], judgments.get(key))
        items[key] = item
    months = {}
    for item in items.values():
        created = resolved_created_utc(item)
        if created is None:
            continue
        months.setdefault(date(created)[:7], []).append(item)
    directory.mkdir(parents=True, exist_ok=True)
    for month, values in months.items():
        path = directory / (month + '.jsonl')
        temporary = path.with_suffix('.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n'
                                     for r in sorted(values, key=lambda r: (r['id'], r['subject']))), encoding='utf-8')
        temporary.replace(path)
    for path in directory.glob('*.jsonl'):
        if path.stem not in months:
            path.unlink()


def load_mentions(root):
    """Latest answer per item/family, so question upgrades don't double counts."""
    latest = {}
    for row in read_rows(Path(root) / 'judgments'):
        key = (row['id'], row['subject'])
        if key not in latest or timestamp(row['judged_at']) >= timestamp(latest[key]['judged_at']):
            latest[key] = row
    items = {(r['id'], r['subject']): r for r in read_rows(Path(root) / 'items')}
    result = []
    for key, judgment in latest.items():
        item = items.get(key, {})
        row = dict(item)
        row.update(judgment)
        row['created_utc'] = resolved_created_utc(item, judgment)
        row['comment_id'] = row['id']
        result.append(row)
    return result


def rebuild_daily(root):
    days = {}
    for row in load_mentions(root):
        created = resolved_created_utc(row)
        if created is None:
            continue
        day = days.setdefault(date(created), {'families': {}, 'versions': {}, 'opinions': []})
        groups = [(day['families'], row['subject'])]
        if row.get('version'):
            versions = day['versions'].setdefault(row['subject'], {})
            groups.append((versions, row['version']))
        for group, name in groups:
            counts = group.setdefault(name, dict.fromkeys((*LABELS, 'opinion'), 0))
            counts[row['label']] += 1
            counts['opinion'] += row['label'] != 'no_opinion'
        day['opinions'].append({
            'id': row['id'], 'subject': row['subject'], 'version': row.get('version'),
            'label': row['label'], 'q': row.get('q'), 'probs': row.get('probs'),
            'created_utc': created,
        })
    directory = Path(root) / 'daily'
    directory.mkdir(parents=True, exist_ok=True)
    for day, counts in days.items():
        write_json(directory / (day + '.json'), counts)
    for path in directory.glob('*.json'):
        if path.stem not in days:
            path.unlink()
    return days
