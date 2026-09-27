# Task 5: default view + "going sour / heating up" alerts

Owner goal: open the page and immediately see if people started trashing (or loving) a model today.

## Default range
Default stays **7 days** for the ranking, chart and Use-today cards (enough opinions to be stable).

## Trend alerts (new strip at the very top, above "Use today")
For every family (and every version with enough data), compare two windows ending at the selected end date:
- **Now** = last 48 hours (by comment `created_utc`), **Before** = the 7 days before that.
- Show an alert when Now has ≥15 opinions, Before has ≥20 opinions, and |Score(Now) − Score(Before)| ≥ 15 points.
  - Drop → red chip: "⚠️ Going sour: Grok — score −37 → −58 in the last 2 days (46 opinions)" + link to its most-voted
    complaint in the Now window.
  - Rise → green chip: "📈 Heating up: Qwen — +10 → +35 in the last 2 days (31 opinions)" + its top praise.
- Sort by size of the change, show at most 5; if none: "No big mood swings in the last 2 days."
- Brand-new names with ≥15 opinions in Now and <5 in Before get "🆕 Suddenly talked about: <name>".
- Each ranking row also gets a tiny trend arrow (▲/▼ with the point change) when the same rule fires for it.
Put the window logic in a small pure function with unit tests (drop, rise, too few opinions, new name).
Update the UI test. `scripts/check.sh` must pass.
