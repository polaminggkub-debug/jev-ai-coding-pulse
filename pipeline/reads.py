"""Build a self-contained, phone-friendly ``reads.html`` page."""
import json
from pathlib import Path

try:
    from . import curator, navigation
except ImportError:
    import curator
    import navigation

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent
LOGOS = ROOT / "assets" / "logos"


def _safe_json(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace(
        "&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _embedded(tag_id, value):
    return f'<script id="{tag_id}" type="application/json">{_safe_json(value)}</script>'


def _logos():
    return {path.stem: path.read_text(encoding="utf-8")
            for path in sorted(LOGOS.glob("*.svg"))}


def _page(payload, output):
    base_css = (ASSETS / "pulse.css").read_text(encoding="utf-8")
    reads_css = (ASSETS / "reads.css").read_text(encoding="utf-8")
    script = (ASSETS / "reads.js").read_text(encoding="utf-8")
    body = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Worth reading today · Jev Reddit Pulse</title>
<style>{base_css}\n{reads_css}</style></head>
<body class="reads-page">{navigation.nav("reads.html")}<header class="reads-header"><div><h1>📚 Worth reading today</h1>
<p class="m">Developer discussions about AI coding models and tools.</p></div>
<button id="theme" type="button" aria-label="Toggle light and dark theme">Toggle theme</button></header>
<main><section aria-label="Choose a day and view">
<div class="reads-controls"><div class="reads-day-controls" role="group" aria-label="Choose a day">
<button id="day-prev" type="button" aria-label="Previous day">◀</button>
<label for="read-day">Day</label><select id="read-day" aria-label="Day"></select>
<button id="day-next" type="button" aria-label="Next day">▶</button></div>
<div class="reads-view-controls" role="group" aria-label="Choose a view">
<button id="view-day" type="button" aria-pressed="true">That day</button>
<button id="view-week" type="button" aria-pressed="false">This week</button></div></div>
<p id="reads-status" class="m" role="status" aria-live="polite"></p>
<div id="reads-cards" class="reads-cards"></div>
</section></main>
{_embedded('reads-data', payload)}
{_embedded('reads-logos', _logos())}
<script>{script}</script>
</body></html>'''
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(body, encoding="utf-8")


def build(data_dir=curator.DATA, output=ROOT / "reads.html", *, now=None):
    """Write an offline reads page from persisted curation answers."""
    payload = curator.reads_payload(data_dir, now=now)
    _page(payload, output)
    return sum(len(rows) for rows in payload["daily"].values())


if __name__ == "__main__":
    print(f"Built reads.html with {build()} curated threads.")
