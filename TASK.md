# Task: turn the demo pipeline into a browsable "Jev Reddit Pulse" demo page

Context: `pipeline/` holds a working throwaway demo (Python 3 stdlib only). `fetch.py` pulls top Reddit threads + comments
from the Arctic Shift API into `data/raw.json`; `classify.py` asks Jev (a classifier model, OpenRouter) whether each
comment praises/complains about a model, writing `data/labeled.json`; `build.py` renders `pulse.html`.
Scripts currently use bare relative paths; make them work when run from the repo root.
Focus: AI models and tools **for coding**. Zones: `us` (US frontier), `open` (China + open-weight), `tool` (coding tools).

You have NO network and NO API key. Do not call Jev or Arctic Shift. Work only from `data/*.json`.

## 1. Model versions (no Jev calls)
Each labeled mention currently has a `subject` = model family (e.g. "Claude Opus"). Add a `version` field:
1. Explicit version in the comment text → use it (e.g. "opus 5.5" → "Opus 5.5", "qwen3.8" → "Qwen 3.8", "gpt-6" → "GPT-6").
2. Else a version in the thread title → use that.
3. Else `version = null` (counts toward the family only; never guess).
Known GPT-6 nicknames: Astra, Sol, Luna, Terra → versions "GPT-6 Astra", "GPT-6 Sol", "GPT-6 Luna", "GPT-6 Terra".
Also add Xiaomi MiMo (`\bmimo\b`, zone `open`) to `registry.py`.
Put version extraction in its own module with a `unittest` file covering the three rules and the nicknames.

## 2. Incremental re-runs (dedupe by comment id)
`classify.py` must keep a store of already-judged `(comment_id, subject)` pairs in `data/` and only send pairs not seen
before. Re-running with no new data must make zero Jev calls. Thread scores may be refreshed without re-judging.
Add a unittest for this using a fake `decide` function.

## 3. The page (`build.py` → `pulse.html`)
Single static HTML file, data embedded as JSON, vanilla JS, no external requests. Keep the existing look (CSS tokens,
light/dark). Must work at phone width with no horizontal scroll.
- **Quick view by default:** per zone, one row per model family: praise/mixed/complaint bar, %s, opinion count.
- **Detail on demand:** click a family row to expand its versions (each with its own bar and %s, plus "version unknown"),
  the best-voted praise quote and complaint quote (with link + ▲score), and its top threads. An "expand all" toggle too.
- **Search / pick any model:** a search box at the top plus clickable chips for every family and version found in the
  data (not only the top ones). Selecting one shows just that model's card, even if it has few mentions.
- Keep "Most talked about" and the per-zone "best right now" pick (require ≥20 opinions for the pick).

## Done when
- `python3 -m unittest discover -s pipeline` passes.
- `python3 pipeline/build.py` produces `pulse.html` from the existing `data/labeled.json` without network.
- Each file ≲300 lines. Commit your work on branch `feature/pulse-demo` with a clear message.
