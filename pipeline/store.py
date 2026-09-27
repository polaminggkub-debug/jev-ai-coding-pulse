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


def append_item(root, row):
    item = {k: v for k, v in row.items() if k != 'comment_id'}
    item['text'] = (item.get('text') or '')[:400]
    path = Path(root) / 'items' / (date(item['created_utc'])[:7] + '.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(item, ensure_ascii=False, separators=(',', ':')) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def judgment_index(root):
    return {(r['id'], r['subject'], r['q']): r for r in read_rows(Path(root) / 'judgments')}


def update_items(root, rows):
    directory = Path(root) / 'items'
    items = {(r['id'], r['subject']): r for r in read_rows(directory)}
    fields = ('id', 'kind', 'sub', 'score', 'link', 'thread', 'thread_score',
              'thread_url', 'subject', 'zone', 'version', 'text', 'created_utc')
    for row in rows:
        item = {field: row.get(field) for field in fields}
        item['text'] = (item['text'] or '')[:400]
        key = (item['id'], item['subject'])
        if key in items:
            item['created_utc'] = items[key]['created_utc']
        items[key] = item
    months = {}
    for item in items.values():
        months.setdefault(date(item['created_utc'])[:7], []).append(item)
    directory.mkdir(parents=True, exist_ok=True)
    for month, values in months.items():
        path = directory / (month + '.jsonl')
        temporary = path.with_suffix('.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n'
                                     for r in sorted(values, key=lambda r: (r['id'], r['subject']))), encoding='utf-8')
        temporary.replace(path)


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
        row = dict(items.get(key, {}), **judgment)
        row['comment_id'] = row['id']
        result.append(row)
    return result


def rebuild_daily(root):
    days = {}
    for row in load_mentions(root):
        day = days.setdefault(date(row['created_utc']), {'families': {}, 'versions': {}, 'opinions': []})
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
            'created_utc': row['created_utc'],
        })
    directory = Path(root) / 'daily'
    directory.mkdir(parents=True, exist_ok=True)
    for day, counts in days.items():
        write_json(directory / (day + '.json'), counts)
    for path in directory.glob('*.json'):
        if path.stem not in days:
            path.unlink()
    return days
