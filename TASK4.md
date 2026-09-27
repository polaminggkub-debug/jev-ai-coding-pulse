# Task 4: make likes vs dislikes obvious at a glance

Owner feedback: the ranking rows are unreadable (green on the right of a centred bar, red on the left, and a bare
"+21" nobody understands), and the Buzz-vs-love chart has no colour for good/bad or for zones. Offline only.
Keep `scripts/check.sh` green and update the UI tests for the new structure.

## 1. Ranking rows (every zone, and the version rows inside details)
Replace the centred diverging bar with ONE left-to-right 100% bar per model:
- green segment first (left) = **Liked %**, then a muted grey segment = **Mixed %**, then red (right) = **Disliked %**.
- Print the numbers on the row in plain words: left of the bar "👍 55% liked", right of the bar "👎 28% disliked".
- Replace "Net +21" with a small pill "Score +21" coloured green/red, and give it a tooltip
  (`title`) "Score = liked % − disliked %".
- Keep the opinion count, but word it as "452 people's opinions".
- Add one legend line at the top of the ranking area: "👍 liked · mixed · 👎 disliked — share of opinions about each
  model for coding. Score = liked − disliked."
- Same wording on the Use-today cards: under the big number write "Score (liked − disliked)" and show
  "👍 55% · 👎 28%" next to it.

## 2. Buzz-vs-love chart
- Tint the background: area above the zero line very light green, below it very light red (low opacity, readable in
  both themes). Label the halves on the y-axis: "👍 more liked" above, "👎 more disliked" below.
- Colour-code zones: each point gets a ring + label colour by zone — US frontier, Coding tools, China + open —
  using three distinct, colour-blind-safe hues defined as CSS tokens (light/dark). Add a legend with the three zones.
- The inspected-point line ("Grok · Net −37 · 199 opinions") becomes "Grok · 👍 30% · 👎 67% · Score −37 · 199 opinions".
- Rename the y-axis title to "Score (liked − disliked)".

## 3. Honest time range
If the selected range starts before the first day we have data, show a small note:
"History starts <first day> — longer ranges fill in as daily runs accumulate."
Leave changes uncommitted if the sandbox blocks git.
