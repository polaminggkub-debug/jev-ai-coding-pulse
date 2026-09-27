# Jev AI Coding Pulse — project brief for an outside reviewer

You are reviewing a small personal project and proposing ideas. Read the whole brief, then produce the output described
in **Your task** at the end. Everything below is the current, verified state as of 28 Sep 2026.

## 1. Why it exists
The owner is a solo developer in Thailand who codes daily with AI agents (Claude Code on Opus 5.5 as the orchestrator,
Codex/GPT-6 Astra and OpenCode as implementation workers). Model quality in real use drifts week to week ("nerfed",
new releases, rate limits), and benchmarks do not reflect it. He used to read Reddit every day to learn which models
people praise or trash **for coding**. This project automates that: it reads AI subreddits continuously and answers
"what should I use today, and what is going sour right now?"

Owner preferences that constrain ideas:
- Wants to open one page and understand it in seconds; long text or dense charts are rejected.
- Wants it **free except the Jev API** (paid via OpenRouter). No paid hosting, no paid databases.
- Coding use only. Three zones on one page: 🇺🇸 US frontier models, 🛠 coding tools, 🇨🇳 China + open-weight models.
- Personal use first; public later if good.

## 2. What Jev is (important: it cannot write text)
Jev (TypeSafe AI, reached through OpenRouter `~typesafe/jev-latest`, endpoint `/api/alpha/decisions`) is a fast
classifier model. It answers typed questions only — **choice**, **yes/no**, **score** — with calibrated
probabilities, in well under a second. It never generates free text, so it cannot summarise or rewrite; it can only
pick among options (e.g. choose the most informative sentence from candidates).
Measured cost: ~2,000 judgments ≈ US$0.04. A full day of 48 subreddits ≈ 1,800–2,000 judgments.

## 3. How it works today
Repo: https://github.com/polaminggkub-debug/jev-ai-coding-pulse (public). Live page:
https://polaminggkub-debug.github.io/jev-ai-coding-pulse/ . Python 3 stdlib only + vanilla JS; no frameworks.

Pipeline (GitHub Actions `pulse.yml`, cron 00:00 and 12:00 UTC, plus manual runs):
1. **fetch** — for each of 48 subreddits in `config/subreddits.txt`, pull posts from the last 5 days from the free
   Arctic Shift Reddit archive API, keep the top 8 by score, and fetch their comments. (Reddit's own JSON API
   returns 403 without auth; RSS lacks scores and rate-limits hard, so Arctic Shift is the source.)
2. **mention detection** — regex registry (`pipeline/registry.py`) finds model/tool families in each post/comment.
   Version extraction (`versions.py`): explicit version in the comment → else version in the thread title → else
   unknown; never guessed. GPT-6 nicknames (Astra, Sol, Luna, Terra) map to versions.
3. **classify** — for each unseen (item id, family, question version) pair, ask Jev one choice question:
   praise / complaint / mixed / no_opinion, "as a tool for writing code or agentic coding".
4. **store** — append-only `data/judgments/YYYY-MM.jsonl` (every Jev answer kept forever, never re-asked),
   `data/items/YYYY-MM.jsonl` (metadata: link, score, thread, short text), `data/daily/YYYY-MM-DD.json`
   (aggregates rebuilt from storage, never from Jev). Bumping the question version re-judges; otherwise reruns cost 0.
   Hard cap: 8,000 new Jev calls per run.
5. **build** — one static HTML page with data embedded; deployed to GitHub Pages; bot commits data back to the repo.

Guards/CI: `scripts/check.sh` (compile, file ≤500 lines / function ≤50 lines, stdlib-only imports, no external URLs
in the page, unit + UI tests); CI matrix Python 3.11–3.13. Implementation is done by Codex (GPT-6 Astra, medium
effort) under `jev-watch`, a supervisor that also uses Jev to stop looping/stalled workers; Claude reviews.

## 4. What the page shows
- **Trend alerts** (top): compares the last 48 h against the 7 days before; flags a model when |Δscore| ≥ 15 with
  enough opinions (≥15 now, ≥20 before). "⚠️ Going sour", "📈 Heating up", "🆕 Suddenly talked about".
- **Use today**: one card per zone with the best rankable model (≥20 opinions), its most-discussed version, score,
  top-voted praise quote, runner-up.
- **Ranking per zone**: logo, one left-to-right bar (green liked → grey mixed → red disliked), "👍 52% liked /
  👎 31% disliked", Score pill (= liked% − disliked%), trend arrow, opinion count; click for versions, quotes, threads.
- **Buzz vs love chart**: x = opinions (log), y = score; green/red halves; points are brand logos ringed by zone colour.
- **Search + top-10 model chips**; time range Today / 7 days (default) / 30 days with ◀ ▶ to step back in time.

Snapshot (7 days): Claude Code +28, Claude Opus +21 (mostly 5.5), Qwen +20; GPT/ChatGPT −22 (626 opinions),
Gemini −31, Grok −37, Cursor −31. Alerts: Codex +21 → −27 and GPT-6 Sol +9 → −36 in the last 2 days.

## 5. In progress / known limits
- **30-day backfill** running locally (day by day, top 5 threads per subreddit per day, comments from each thread's
  first 3 days). 5 of 24 days done, ~17k judgments so far, ≈ $1 total expected. Some subreddits intermittently fail
  on Arctic Shift (rate limits); failures are retried on later runs.
- **Accuracy**: spot check ≈ 70–75% correct per comment. Main error: one comment judging several models
  ("Cursor is bad, Opus is great"). Aggregates are usable; single labels are not.
- **Score lag**: Arctic Shift updates vote counts 2–3 days late, so "top threads" skew older.
- **Registry is manual**: brand-new model names are missed until added (Jev can pick names only from candidates).
- **Sarcasm, memes, off-topic (image generation, pricing politics)** leak into sentiment.
- Subreddits differ wildly in volume; r/ChatGPT-style general subs were excluded on purpose.

## 6. Ideas already rejected (do not re-propose)
Generative summaries by another LLM (owner wants Jev-only), paid hosting/DB, Supabase (reserved for his job),
benchmarks, running his own evals, scraping Reddit with his login.

## Your task
Propose improvements, ranked by value to the owner. For each idea give: what it is (1–2 sentences), why it helps
him specifically, rough Jev cost per day, effort (S/M/L), and any risk. Cover at least: better accuracy with Jev's
choice/yes-no/score primitives, discovering new model names automatically, making the page even faster to read,
alerts delivered to him (still free), and better use of the stored history. Keep the answer short and scannable;
write it in Thai.
