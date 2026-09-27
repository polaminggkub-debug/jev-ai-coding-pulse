# Task 8: "Worth reading" — a separate curator page

Offline tests only; `scripts/check.sh` must pass. Leave changes uncommitted if git is blocked.

Build a second page `reads.html` (deployed next to `index.html`, linked from the main page header as "📚 Worth
reading today"). The main page stays focused on "who is liked / disliked".

- For each day, pick the **top 10 threads** across all sources about AI coding models/tools.
- Candidate pool: threads with ≥ 5 judged opinions in our store (any source). Rank by
  `engagement × heat`, where engagement = comments + score, **normalised per community** (percentile within its own
  community over the last 30 days, so big subreddits don't win just by size) and heat = share of praise+complaint
  opinions (debate/strong feelings beat neutral chatter).
- Before showing, ask Jev once per candidate (cheap, ≤ 60 calls/day): yes/no "Is this thread worth reading for a
  developer deciding which AI coding model or tool to use (real experience, comparisons, regressions, tips — not memes
  or news reposts)?" Keep threads with p ≥ 0.6. Store the answer like other judgments (question version, never re-asked).
- Each card: title (link), community + source icon, date, ▲score · 💬comments, which models it's about (logos), a
  label by code: "🔥 Heated debate" (praise and complaint both ≥ 30%), "👍 People love it", "👎 People are angry",
  and the single most-voted comment (one line).
- Day selector (◀ ▶, default today; fall back to the latest day with data), and "This week" view (top 10 of 7 days).
- Same look/tokens/dark mode as the main page, phone-friendly.
