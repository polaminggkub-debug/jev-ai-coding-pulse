# Task 7: every free source, source tracking, and community bias

Offline tests only (fake HTTP); `scripts/check.sh` must pass. Leave changes uncommitted if git is blocked.
Test fixtures print "failed r/Broken" on purpose; that is expected.

## 1. Sources (all free, no paid APIs)
Every stored item gets `source` (`reddit` default for existing rows, `hn`, `github`, `bluesky`, `devto`, `lobsters`)
and `community` (subreddit, `HN`, `owner/repo`, `Bluesky`, `Dev.to`, `Lobsters`). Ids are prefixed by source.
Search **every family in `registry.py`**, not only the big ones, so small models get coverage too.
- **Hacker News**: Algolia `search_by_date`, no auth, stories + comments of the last 5 days per family name; keep
  stories with points ≥ 10 and comments under such stories.
- **GitHub Issues + comments**, `GITHUB_TOKEN`, last 5 days, skip bots. Repos in `config/github_repos.txt`, seeded:
  anthropics/claude-code, openai/codex, sst/opencode, google-gemini/gemini-cli, QwenLM/qwen-code, cline/cline,
  Kilo-Org/kilocode, Aider-AI/aider, continuedev/continue. A repo's own tool counts as mentioned, plus any family in text.
- **Bluesky**: public AppView `app.bsky.feed.searchPosts` (no auth; if it now requires auth, skip the source cleanly
  and log why), per family name, last 5 days, posts with ≥ 5 likes + their replies.
- **Dev.to**: `https://dev.to/api/articles?tag=ai` / `?tag=claude` etc. plus comments API; articles with ≥ 5 reactions.
- **Lobsters**: `https://lobste.rs/t/ai.json` and `/t/vibecoding.json`, stories + comments, score ≥ 5.
Each fetcher is its own module; one failing source never fails the run. Same quality rules, same classify/store path.

## 2. Page
- **"Where the data comes from"**: a chart of opinions by source (and top communities within Reddit) for the selected
  range, with counts.
- **Community tastes**: a heatmap, rows = communities with enough data (≥ 30 opinions), columns = families with
  ≥ 20 opinions; cell = score, green↔red. Beside each community: "loves most" / "hates most".
- **Bias correction**: some communities complain about everything (GitHub issues are mostly bug reports). Show each
  cell also as "vs this community's average" and add a toggle **Raw score / Fair score** for the ranking and chart,
  where Fair score averages each family's score across communities relative to that community's own baseline,
  weighting by opinion count (min 10 per cell). Explain it in one line on the page.
- A source filter (All / Reddit / HN / GitHub / Bluesky / Dev.to / Lobsters) and a source icon next to quotes.
- `pulse.yml`: run all fetchers after Reddit.
