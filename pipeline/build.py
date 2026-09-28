"""Build an offline, self-contained Pulse page from daily records and items."""
import datetime
import json
from pathlib import Path

try:
    from . import store, update_info, reads, navigation
    from .source_identity import normalize_item, normalize_judgment
    from .versions import extract_version
except ImportError:
    import store
    import reads
    import navigation
    import update_info
    from source_identity import normalize_item, normalize_judgment
    from versions import extract_version

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent
LOGOS = ROOT / 'assets' / 'logos'
SCRIPTS = ('pulse.js', 'pulse-sources.js', 'pulse-community.js', 'pulse-trends.js',
           'pulse-trend-ui.js', 'pulse-rank.js', 'pulse-chart.js')


def _prepare_mentions(rows):
    """Keep one page row per mention and fill versions for legacy data."""
    seen = set()
    result = []
    for original in rows:
        row = normalize_item(original)
        # Curator-only thread context would be repeated for every ranking row.
        row.pop('thread_top_comment', None)
        key = (row.get('comment_id') or row.get('id') or row.get('link'), row.get('subject'))
        if key in seen:
            continue
        seen.add(key)
        if any(row.get(field) is not None for field in
               ('created_utc', 'parent_created_utc', 'post_created_utc', 'judged_at')):
            row['created_utc'] = store.resolved_created_utc(row, row)
            row['date'] = store.date(row['created_utc'])
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
    items = [normalize_item(row) for row in store.read_rows(Path(root) / 'items')]
    item_by_key = {(row.get('id'), row.get('subject')): row for row in items}
    rows = []
    for path in sorted((Path(root) / 'daily').glob('*.json')):
        day = path.stem
        try:
            datetime.date.fromisoformat(day)
            summary = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        opinions = summary.get('opinions')
        if summary.get('families') and opinions is None:
            raise ValueError(
                f'{path} lacks per-comment labels; regenerate daily data with store.rebuild_daily first')
        if _daily_totals(opinions or []) != (summary.get('families', {}), summary.get('versions', {})):
            raise ValueError(f'{path} aggregates do not match its per-comment labels')
        for opinion in opinions or []:
            normalized = normalize_judgment(opinion, item_by_key.get(
                (normalize_item(opinion).get('id'), opinion.get('subject'))))
            try:
                opinion_day = store.date(normalized.get('created_utc') or day)
            except (TypeError, ValueError, OverflowError):
                opinion_day = day
            if opinion_day != day:
                raise ValueError(f'{path} contains an opinion with a mismatched UTC date')
            item = item_by_key.get((normalized.get('id'), normalized.get('subject')))
            if item is None:
                raise ValueError(f'{path} contains an opinion without a matching item')
            row = dict(item)
            row.update(normalized)
            row['version'] = normalized.get('version') or item.get('version')
            row['created_utc'] = store.resolved_created_utc(
                item, dict(normalized, judged_at=normalized.get('judged_at') or day))
            row['date'] = store.date(row['created_utc'])
            rows.append(row)
    prepared = _prepare_mentions(rows)
    if len(prepared) != len(rows):
        raise ValueError('Daily records contain duplicate item and family pairs')
    return prepared, sorted({row['date'] for row in prepared})


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


TIME_CONTROLS = '''<section aria-label="Choose a time range"><h2>Time range</h2>
<div id="time-range" role="group" aria-label="Time range">
<button id="range-today" type="button" aria-pressed="false">24h</button>
<button id="range-7" type="button" aria-pressed="true">7 days</button>
<button id="range-30" type="button" aria-pressed="false">30 days</button>
<span id="range-opinions" class="m" role="status"></span>
<button id="date-prev" type="button" aria-label="Earlier end date">◀</button>
<label for="date-end">End date</label><select id="date-end" aria-label="End date"></select>
<button id="date-next" type="button" aria-label="Later end date">▶</button>
<button id="back-latest" type="button">Back to latest</button></div>
<p id="range-status" class="m" role="status"></p><p id="history-note" class="m" role="status" hidden></p></section>
'''

SOURCE_SECTIONS = '''<section aria-label="Data sources"><h2>Where the data comes from</h2>
<label for="source-filter">Source filter</label><select id="source-filter" aria-label="Source filter">
<option value="all">All sources</option><option value="reddit">Reddit</option><option value="hn">Hacker News</option>
<option value="github">GitHub</option><option value="bluesky">Bluesky</option>
<option value="devto">Dev.to</option><option value="lobsters">Lobsters</option></select>
<p class="m">The source filter changes the charts on this page only. GitHub issues are bug reports — not counted in main score.</p>
<div id="source-chart" aria-label="Opinions by source"></div>
<h3>Top Reddit communities</h3><div id="reddit-communities"></div></section>
<section aria-label="Community tastes"><h2>Community tastes</h2>
<p class="m">Community rows need 30 opinions; the GitHub bug-report row is always shown when present. Family columns need 20. Each cell shows its score and how it differs from that community’s average.</p>
<div id="community-heatmap"></div></section>
'''


def _page(rows, meta, output):
    css = '\n'.join((ASSETS / name).read_text(encoding='utf-8')
                    for name in ('pulse.css', 'pulse-sources.css'))
    body = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jev Reddit Pulse</title><style>{css}</style></head>
<body>{navigation.nav("index.html")}<header><h1>Jev Reddit Pulse</h1><button id="theme" type="button">Toggle light/dark</button></header>
<p id="update-info" class="m" role="status"></p>
<p id="covered-period" class="m" role="status"></p>
<section id="trend-alerts" aria-label="Trend alerts"><h2>Trend alerts</h2></section>
<section id="use-today" aria-label="Use today"><h2>Use today</h2></section>
<p class="m">Score counts Reddit, HN, Dev.to, Lobsters. GitHub issues are shown under Sources.</p>
<p class="m">Rankable families need 8 opinions for 24h, or 20 for 7/30 days. Reddit sentiment is not a benchmark.</p>
{TIME_CONTROLS}
<section aria-label="Buzz versus love"><h2>Buzz vs love</h2><div id="chart"></div></section>
<section aria-label="Score method"><h2>Score method</h2>
<label for="score-mode">Ranking and chart score</label><select id="score-mode" aria-label="Ranking and chart score">
<option value="raw">Raw score</option><option value="fair">Fair score</option></select>
<p class="m">Fair score weights each family’s difference from its community’s average by cell size (minimum 10 opinions per community).</p></section>
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


def _sources_page(rows, meta, output):
    css = '\n'.join((ASSETS / name).read_text(encoding='utf-8')
                    for name in ('pulse.css', 'pulse-sources.css'))
    body = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sources &amp; communities · Jev Reddit Pulse</title><style>{css}</style></head>
<body>{navigation.nav("sources.html")}<header><h1>Sources &amp; communities</h1>
<button id="theme" type="button">Toggle light/dark</button></header>
<p id="update-info" class="m" role="status"></p>
<p id="covered-period" class="m" role="status"></p>
<main>{TIME_CONTROLS}{SOURCE_SECTIONS}</main>
{_embedded('pulse-logos', _logos())}
{_embedded('pulse-meta', dict(meta, page='sources'))}
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
    meta = update_info.metadata(rows, days, source, ROOT / '.github/workflows/pulse.yml')
    _page(rows, meta, output)
    _sources_page(rows, meta, Path(output).with_name("sources.html"))
    return len(rows)


if __name__ == '__main__':
    print(f'Built pulse.html from {build()} mentions (offline).')
    print(f'Built reads.html with {reads.build()} curated threads (offline).')
