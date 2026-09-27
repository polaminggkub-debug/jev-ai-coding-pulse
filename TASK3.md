# Task 3: redesign the page so it reads in 5 seconds

Work on top of the current branch. Offline only (no network). Logos are vendored in `assets/logos/*.svg` (MIT,
@lobehub/icons); inline them into the built page. Mono logos use `currentColor`, so tint them with the text color.
Logo map: Claude Opus/Sonnet/Haiku/Fable/Claude Code → claude; GPT/ChatGPT → openai; Codex → codex; Gemini, Gemma →
gemini/gemma; Grok → grok; DeepSeek; Qwen; Kimi; GLM → glm; MiniMax; Mistral; Llama → llama; Xiaomi MiMo → mimo;
Cursor; Copilot; OpenCode. No logo → a neutral circle with the first letter.

Terms: praise% / complaint% are shares of opinions (praise+complaint+mixed). **Net** = praise% − complaint%,
shown signed (e.g. +27, −50). A model is **rankable** with ≥20 opinions in the selected time range.

## 1. "Use today" strip (top of page, first thing seen)
One card per zone (🇺🇸 US frontier · 🛠 Coding tools · 🇨🇳 China + open): the rankable model with the highest Net.
Card shows: logo, name, its most-discussed version (e.g. "mostly Opus 5.5"), Net as a big number, opinion count,
and the best-voted praise quote (one line, links to the comment). Under it, one small line: "runner-up: <name> +N".
If no model in the zone is rankable: "Not enough talk yet".

## 2. Per-zone ranking (replaces the 3-colour stacked bars)
Rows sorted by Net: logo · name · Net (signed, coloured green/red) · a thin **diverging** bar centred on zero
(praise grows right in green, complaint grows left in red; mixed is not drawn) · "330 opinions" in muted text.
Non-rankable models go in a collapsed "Not enough data (N)" row at the bottom. Clicking a row expands the existing
detail (versions, quotes, threads). In the detail, list only versions with ≥3 mentions; fold the rest into "other".

## 3. Buzz vs love chart (one chart, below the strip)
Scatter of rankable models: x = opinions (log scale), y = Net (−100..+100, zero line drawn). Each point is the model's
logo (24px). Quadrant labels in muted text: top-right "Loved & hot", top-left "Loved, quiet", bottom-right
"Hot but hated", bottom-left "Ignore". Hover/tap shows name, Net, opinions. Inline SVG, no chart library.

## 4. Model chips
Show only the 10 most-mentioned families as chips (with logos), plus the search box. Versions are no longer chips;
search still finds families and versions. Drop the "Show all models" button.

## Constraints
Keep the light/dark tokens, phone width with no horizontal scroll, and all existing tests passing; update the UI test
for the new structure. Files ≲300 lines (split JS/CSS if needed). Leave changes uncommitted if the sandbox blocks git.

## 5. Time: what period am I looking at, and can I go back?
- Always show the covered period under the title, e.g. "Comments from 22 Sep – 27 Sep 2026 · updated 27 Sep 12:00 UTC".
- Keep the Today / 7 days / 30 days switch, and add a date picker (or ◀ ▶ buttons) that moves the whole page to an
  earlier end date, built only from `data/daily/*.json` + `data/items/`. Dates with no data are disabled. A "Back to
  latest" link returns to now. Everything on the page (strip, ranking, chart, chips) follows the selected period.

## 6. Guards + CI (mirror ~/jev-watch, adapted to Python stdlib)
- `scripts/check_structure.py`: fail if any `.py`/`.js`/`.css` source file is > 500 lines or any Python/JS function
  is > 50 lines, if `pipeline/` imports anything outside the stdlib or itself, or if the page loads any external URL.
- `scripts/check.sh` (= the one command to run before merging): `python3 -m compileall -q pipeline scripts`,
  structure check, `python3 -m unittest discover -s pipeline`, `node pipeline/test_pulse_ui.js`.
- `.github/workflows/ci.yml`: on push to main and pull_request, `permissions: contents: read`, concurrency cancel;
  job "guards" (compile + structure) and job "test" matrix over python 3.11/3.12/3.13 on ubuntu-latest running the
  unit tests plus the Node UI test (node 22). Keep `pulse.yml` (scheduled run) separate.
- Add a "Checks" section to README.md: run `scripts/check.sh` before every merge.

## Done when
`scripts/check.sh` passes locally; the built page shows the covered period and can step back to earlier dates.
