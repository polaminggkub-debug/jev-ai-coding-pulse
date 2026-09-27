# Task 2: durable Jev judgments + scheduled runs

Context: see README.md and `pipeline/`. Python 3 stdlib only. You have NO network and NO API key: never call Jev or
Arctic Shift; use fakes in tests. The goal: we pay only for Jev (OpenRouter); every Jev answer is stored forever and
reused, and nothing is ever judged twice.

## 1. Storage (replace `data/classify_cache.json` and `data/labeled.json` as the source of truth)
- `data/judgments/YYYY-MM.jsonl` (month of the comment's `created_utc`): append-only, one line per Jev answer:
  `{"id","kind","subject","q","label","probs","created_utc","judged_at"}`. `q` = question version string
  (e.g. `"sentiment-v1"`) defined next to the question in classify.py. A pair is "already judged" when
  `(id, subject, q)` exists in any month file. Changing the question text means bumping `q`.
- `data/items/YYYY-MM.jsonl`: per judged item, the metadata the page needs (id, kind, sub, score, link, thread,
  thread_score, thread_url, subject, zone, version, short text ≤400 chars). Scores may be updated in place on rerun.
- `data/daily/YYYY-MM-DD.json`: per-day aggregate per family and per version (praise/complaint/mixed/no_opinion counts,
  opinion count), keyed by comment date. Rebuilt from the jsonl files, never from Jev.
- One-time migration: import the existing `data/classify_cache.json` + `data/labeled.json` + `data/raw.json` into the new
  layout (created_utc may be missing for old rows; fall back to judged date). Then delete the old files.

## 2. Fetching (`fetch.py`)
- Subreddits come from `config/subreddits.txt` (one per line, `#` comments). Seed it with:
  AgentsOfAI AutoGPT ChatGPTCoding ChatGPTPro ClaudeAI ClaudeCode CursorAI GeminiAI GithubCopilot LLM LLMDevs LocalLLM
  LocalLLaMA PromptEngineering QualityAssurance Qwen_AI ZaiGLM aipromptprogramming codex cursor google_antigravity grok
  kimi kiroIDE opencodeCLI vibecoding OpenAI Anthropic OpenAIDev GoogleGeminiAI Bard DeepSeek MiniMax_AI MistralAI
  ollama unsloth huggingface LocalAIServers openrouter AI_Agents mcp CLine kilocode windsurf Jetbrains Replit lovable
  ExperiencedDevs
- Each run: posts from the last 5 days per subreddit, keep the top 8 by score, fetch their comments. Store
  `created_utc` on posts and comments. Threads older than 5 days are no longer fetched. Be polite: ≤4 concurrent requests,
  retry with backoff, and one failing subreddit must not fail the run.

## 3. Page
`build.py` reads the new storage. Add a time-range switch: Today / 7 days / 30 days (default 7 days), computed from
the stored data only. Keep everything else the page already does.

## 4. Scheduled run
`.github/workflows/pulse.yml`: cron twice a day (00:00 and 12:00 UTC) + manual dispatch. Steps: checkout, python 3.12,
run fetch → classify → build, commit changed `data/` and the built page back to the repo, deploy the page to GitHub
Pages. Secret name: `OPENROUTER_API_KEY`. Add a hard cap: classify stops after 8000 new Jev calls per run and logs it.

## Done when
- `python3 -m unittest discover -s pipeline` passes, with tests for: no re-judging across month files, bumping `q`
  re-judges, migration keeps every existing judgment, daily aggregates, the 8000-call cap.
- `python3 pipeline/build.py` works offline from the migrated data.
- Each file ≲300 lines. Update README.md. Commit on a new branch `feature/durable-store` (branch from current HEAD).
