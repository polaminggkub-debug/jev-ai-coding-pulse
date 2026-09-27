"""Build an offline, self-contained Pulse page from daily records and items."""
import datetime
import json
from pathlib import Path

try:
    from . import store
    from .versions import extract_version
except ImportError:
    import store
    from versions import extract_version

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent
LOGOS = ROOT / 'assets' / 'logos'
SCRIPTS = ('pulse.js', 'pulse-trends.js', 'pulse-trend-ui.js', 'pulse-rank.js', 'pulse-chart.js')


def _prepare_mentions(rows):
    """Keep one page row per mention and fill versions for legacy data."""
    seen = set()
    result = []
    for original in rows:
        row = dict(original)
        key = (row.get('comment_id') or row.get('id') or row.get('link'), row.get('subject'))
        if key in seen:
            continue
        seen.add(key)
        if 'version' not in row:
            row['version'] = extract_version(row.get('subject'), row.get('text'), row.get('thread'))
        result.append(row)
    return result


def load_mentions(path):
    """Read a legacy labels JSON file for local compatibility and tests."""
    return _prepare_mentions(json.loads(Path(path).read_text(encoding='utf-8')))


def _daily_totals(opinions):
    """Recalculate stored counts from labels so malformed daily files cannot drop data."""
    families, versions = {}, {}
    for opinion in opinions:
        family = opinion.get('subject')
        groups = [(families, family)]
        if opinion.get('version'):
            groups.append((versions.setdefault(family, {}), opinion['version']))
        for counts_by_name, name in groups:
            counts = counts_by_name.setdefault(name, dict.fromkeys((*store.LABELS, 'opinion'), 0))
            label = opinion.get('label')
            if label not in store.LABELS:
                raise ValueError(f'Unsupported daily label: {label!r}')
            counts[label] += 1
            counts['opinion'] += label != 'no_opinion'
    return families, versions


def _read_history(root):
    """Join daily labels to items without reading judgments or refreshing data."""
    items = {}
    for row in store.read_rows(Path(root) / 'items'):
        try:
            day = store.date(row['created_utc'])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        items[(row.get('id'), row.get('subject'), day)] = row
    rows = []
    days = []
    for path in sorted((Path(root) / 'daily').glob('*.json')):
        day = path.stem
        try:
            datetime.date.fromisoformat(day)
            summary = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        if summary.get('families'):
            days.append(day)
        opinions = summary.get('opinions')
        if summary.get('families') and opinions is None:
            raise ValueError(
                f'{path} lacks per-comment labels; regenerate daily data with store.rebuild_daily first')
        if _daily_totals(opinions or []) != (summary.get('families', {}), summary.get('versions', {})):
            raise ValueError(f'{path} aggregates do not match its per-comment labels')
        for opinion in opinions or []:
            try:
                opinion_day = store.date(opinion.get('created_utc') or day)
            except (TypeError, ValueError, OverflowError):
                opinion_day = day
            if opinion_day != day:
                raise ValueError(f'{path} contains an opinion with a mismatched UTC date')
            item = items.get((opinion.get('id'), opinion.get('subject'), opinion_day))
            if item is None:
                raise ValueError(f'{path} contains an opinion without a matching item')
            row = dict(item)
            row.update(opinion)
            row['version'] = opinion.get('version') or item.get('version')
            row['date'] = day
            rows.append(row)
    prepared = _prepare_mentions(rows)
    if len(prepared) != len(rows):
        raise ValueError('Daily records contain duplicate item and family pairs')
    return prepared, sorted(set(days))


def _metadata(rows, days):
    dates = days or sorted({row['date'] for row in rows if row.get('date')})
    updated = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    return {
        'days': dates,
        'startDate': dates[0] if dates else None,
        'endDate': dates[-1] if dates else None,
        'updatedAt': updated.isoformat().replace('+00:00', 'Z'),
    }


def _json_payload(value):
    """Keep embedded JSON inert even when user comments contain script markup."""
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')).replace(
        '&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')


def _embedded(tag_id, value):
    return f'<script id="{tag_id}" type="application/json">{_json_payload(value)}</script>'


def _logos():
    return {path.stem: path.read_text(encoding='utf-8') for path in sorted(LOGOS.glob('*.svg'))}


def _scripts():
    missing = [name for name in SCRIPTS if not (ASSETS / name).is_file()]
    if missing:
        raise FileNotFoundError(f'Missing page scripts: {", ".join(missing)}')
    return '\n'.join(f'<script>{(ASSETS / name).read_text(encoding="utf-8")}</script>'
                     for name in SCRIPTS)


def _page(rows, meta, output):
    css = (ASSETS / 'pulse.css').read_text(encoding='utf-8')
    body = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jev Reddit Pulse</title><style>{css}</style></head>
<body><header><h1>Jev Reddit Pulse</h1><button id="theme" type="button">Toggle light/dark</button></header>
<p id="covered-period" class="m" role="status"></p>
<section id="trend-alerts" aria-label="Trend alerts"><h2>Trend alerts</h2></section>
<section id="use-today" aria-label="Use today"><h2>Use today</h2></section>
<p class="m">Rankable families need 20 opinions. Reddit sentiment is not a benchmark.</p>
<section aria-label="Choose a time range"><h2>Time range</h2>
<div id="time-range" role="group" aria-label="Time range">
<button id="range-today" type="button" aria-pressed="false">Today</button>
<button id="range-7" type="button" aria-pressed="true">7 days</button>
<button id="range-30" type="button" aria-pressed="false">30 days</button>
<button id="date-prev" type="button" aria-label="Earlier end date">◀</button>
<label for="date-end">End date</label><select id="date-end" aria-label="End date"></select>
<button id="date-next" type="button" aria-label="Later end date">▶</button>
<button id="back-latest" type="button">Back to latest</button></div>
<p id="range-status" class="m" role="status"></p><p id="history-note" class="m" role="status" hidden></p></section>
<section aria-label="Buzz versus love"><h2>Buzz vs love</h2><div id="chart"></div></section>
<section aria-label="Find a model"><label for="search">Search any family or version</label>
<input id="search" type="search" placeholder="Try Opus, GPT-6, Qwen…" autocomplete="off">
<div id="chips" aria-label="Model choices"></div><p id="selection" role="status"></p></section>
<label class="expand"><input id="expand" type="checkbox"> Expand all model details</label>
<main id="zones"></main>
{_embedded('pulse-logos', _logos())}
{_embedded('pulse-meta', meta)}
{_embedded('pulse-data', rows)}
{_scripts()}
</body></html>'''
    Path(output).write_text(body, encoding='utf-8')


def build(source=None, output=ROOT / 'pulse.html'):
    """Build using only daily history and items, or a legacy JSON fixture."""
    source = ROOT / 'data' if source is None else Path(source)
    if source.is_dir():
        rows, days = _read_history(source)
    else:
        rows, days = load_mentions(source), []
    _page(rows, _metadata(rows, days), output)
    return len(rows)


if __name__ == '__main__':
    print(f'Built pulse.html from {build()} mentions (offline).')
