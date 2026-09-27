# Jev Reddit Pulse

Open `pulse.html` directly in a browser. It embeds its data, styles, and vanilla
JavaScript and makes no external requests. Source links open Reddit when clicked.
Use Today / 7 days / 30 days (default 7) to filter by UTC comment/post date, ending
today. Family rows start collapsed; expand them to inspect versions, excerpts,
and threads. Search filters model choices, and chips isolate families or versions.

## Offline build and checks

Python 3's standard library is sufficient (macOS/Linux; CI uses Python 3.12):

```sh
python3 -m unittest discover -s pipeline
python3 pipeline/build.py
node pipeline/test_pulse_ui.js  # optional dependency-free UI interaction checks
```

The checked-in data is already migrated. To import a legacy checkout offline:

```sh
python3 pipeline/migrate.py
python3 pipeline/build.py
```

Migration combines `classify_cache.json`, `labeled.json`, and `raw.json`, verifies
that judgments were saved, then deletes these three files. It is safe to rerun.
Identical cache/label copies coalesce; differing answers are preserved. Missing
comment dates fall back to the recorded judgment date, or the oldest legacy file
modification time when no judgment date exists. Old timestamps are approximate.

## Durable data

- `data/judgments/YYYY-MM.jsonl`: append-only answers, partitioned by the item's
  UTC creation month. Each records `id`, `kind`, `subject`, `q`, `label`, `probs`,
  `created_utc`, and `judged_at`. All month files participate in deduplication.
- `data/items/YYYY-MM.jsonl`: metadata and excerpts of at most 400 characters.
  Reruns refresh scores while retaining historical items.
- `data/daily/YYYY-MM-DD.json`: derived family and family/version label counts,
  plus `opinion` (all labels except `no_opinion`), keyed by creation date.
- `data/incoming.json`: latest fetch input, never the judgment source of truth.

`QUESTION_VERSION` lives beside `Q` in `pipeline/classify.py`. **Bump the version
whenever changing the question text.** Only missing `(id, subject, q)` triples
call Jev. New question versions retain old answers; daily counts and the page use
the most recently judged answer per item/family, avoiding duplicate counts.
Post IDs carry a `post:` prefix. Successful answers are flushed and synced before
proceeding. A local file lock serializes classifier runs. Failures remain retryable
on the next run. Each run makes at most 8,000 new decision requests, including
failed requests, and logs when this cap is reached; there are no hidden API retries.

The builder reads the durable store and rebuilds daily counts offline. Known
versions are extracted before text truncation; unknown versions remain `null`.
Opinion bars exclude neutral mentions. Picks require 20 opinions and rank by
(praise − complaint) / opinions, then opinion count and name. Most-talked-about
counts include neutral mentions. These are Reddit sentiment summaries, not model
benchmarks. Time filtering applies to all these views and requires no new judging.

## Collection and scheduled publishing

```sh
python3 pipeline/fetch.py
OPENROUTER_API_KEY=... python3 pipeline/classify.py
python3 pipeline/build.py
```

Collection uses Arctic Shift, with subreddits in `config/subreddits.txt` (one per
line, `#` comments allowed). It selects the top eight posts by score from the
last five days per subreddit and fetches their comments, retaining timestamps.
At most four requests run concurrently; failures retry with exponential backoff,
and a failed subreddit does not abort other subreddits. Jev uses OpenRouter.
Offline tests use fakes and never need a network connection or API key.

`.github/workflows/pulse.yml` runs at 00:00 and 12:00 UTC and supports manual
execution. Add the repository secret `OPENROUTER_API_KEY`, enable Actions write
permission for repository contents, and choose **GitHub Actions** as the Pages
source. The workflow fetches, classifies, builds, commits changed data/page files,
and deploys `pulse.html` as the Pages site's `index.html`. Workflow concurrency
serializes scheduled/manual runs so they cannot overlap judgments or commits.
