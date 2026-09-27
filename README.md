# Jev Reddit Pulse

Open `pulse.html` directly in a browser. It embeds its data, styles, and vanilla
JavaScript and makes no external requests. Source links open Reddit when clicked.
The covered UTC period and update time appear under the title. Today / 7 days /
30 days (default 7) set the range; the date controls move its end across days
with data, and **Back to latest** returns to the newest day. Expand a family row
to inspect versions, excerpts, and threads. Chips show the ten most-mentioned
families; search also finds versions.

## Checks

Run `scripts/check.sh` before every merge. It compiles the Python sources,
checks source size, imports, function lengths, and external page loads, then runs
the Python and Node UI tests.

## Offline build

Python 3's standard library is sufficient (macOS/Linux; CI checks Python 3.11,
3.12, and 3.13):

```sh
scripts/check.sh
python3 pipeline/build.py
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
  These rows supply the comment details and links shown on the page.
- `data/daily/YYYY-MM-DD.json`: family and family/version counts plus an
  `opinions` list with the item ID, family, version, label, and UTC creation
  time. The page builder joins these opinion records to their item rows.
- `data/incoming.json`: latest fetch input, never the judgment source of truth.

`QUESTION_VERSION` lives beside `Q` in `pipeline/classify.py`. **Bump the version
whenever changing the question text.** Only missing `(id, subject, q)` triples
call Jev. New question versions retain old answers; daily counts and the page use
the most recently judged answer per item/family, avoiding duplicate counts.
Post IDs carry a `post:` prefix. Successful answers are flushed and synced before
proceeding. A local file lock serializes classifier runs. Failures remain retryable
on the next run. Each run makes at most 8,000 new decision requests, including
failed requests, and logs when this cap is reached; there are no hidden API retries.

The builder reads only daily files and items; it checks that the stored family
and version counts agree with each day's `opinions` list. Existing daily files
that predate `opinions` can be upgraded offline with
`python3 -c 'from pipeline import store; store.rebuild_daily("data")'`. Praise,
complaint, and mixed percentages use opinions as their denominator; Net is
praise% minus complaint%. Families need 20 opinions in the selected period to
rank. Mentions include neutral rows. These are Reddit sentiment summaries, not
model benchmarks. Time filtering applies to all views and requires no new judging.

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
