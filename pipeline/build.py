"""Build an offline, self-contained Pulse page from the checked-in labels."""
import datetime
import json
from pathlib import Path

from versions import extract_version

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent


def load_mentions(path):
    rows = json.loads(Path(path).read_text())
    seen = set()
    result = []
    for original in rows:
        row = dict(original)
        key = (row.get('comment_id') or row['link'], row['subject'])
        if key in seen:
            continue
        seen.add(key)
        if 'version' not in row:
            row['version'] = extract_version(row['subject'], row['text'], row['thread'])
        result.append(row)
    return result


def build(source=ROOT / 'data/labeled.json', output=ROOT / 'pulse.html'):
    rows = load_mentions(source)
    # Escape HTML delimiters so even hostile Reddit text cannot close the script.
    payload = json.dumps(rows, ensure_ascii=True).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    css = (ASSETS / 'pulse.css').read_text()
    js = (ASSETS / 'pulse.js').read_text()
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jev Reddit Pulse</title><style>{css}</style></head>
<body><header><h1>Jev Reddit Pulse</h1><button id="theme" type="button">Toggle light/dark</button></header>
<p class="sub">Coding sentiment from Reddit · {len(rows):,} mentions judged by Jev · static demo built {datetime.date.today()}</p>
<p class="m">Opinion percentages exclude neutral mentions. Picks require at least 20 opinions and rank by praise minus complaint share. Reddit sentiment is not a benchmark.</p>
<section aria-label="Find a model"><label for="search">Search any family or version</label>
<input id="search" type="search" placeholder="Try Opus, GPT-6, Qwen…" autocomplete="off">
<div id="chips" aria-label="Model choices"></div><button id="clear" type="button">Show all models</button>
<p id="selection" role="status"></p></section>
<section><h2>🔥 Most talked about</h2><div id="buzz"></div><p class="m">Ranked by all mentions, including neutral mentions.</p></section>
<label class="expand"><input id="expand" type="checkbox"> Expand all model details</label>
<p class="legend">🟢 Praise · 🟡 Mixed · 🔴 Complaint</p>
<main id="zones"></main>
<script id="pulse-data" type="application/json">{payload}</script><script>{js}</script>
</body></html>'''
    Path(output).write_text(page)
    return len(rows)


if __name__ == '__main__':
    print(f'Built pulse.html from {build()} mentions (offline).')
