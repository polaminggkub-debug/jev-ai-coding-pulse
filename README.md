# Jev Reddit Pulse

Open `pulse.html` directly in a browser. It embeds its data, styles, and vanilla
JavaScript and makes no external requests. Source links open the original community when clicked.
The covered UTC period and Thai update time appear under the title. The next update
is calculated from the workflow cron; new-opinion counts come from the latest
classification run (older datasets without run stats show “unknown”). Today / 7 days /
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
comment dates fall back to the parent post date, then the recorded judgment date,
or the oldest legacy file
modification time when no judgment date exists. Old timestamps are approximate.

## Durable data

- `data/judgments/YYYY-MM.jsonl`: append-only answers, partitioned by the item's
  UTC creation month. Each records `id`, `kind`, `subject`, `q`, `label`, `probs`,
  `created_utc`, and `judged_at`. All month files participate in deduplication.
- `data/items/YYYY-MM.jsonl`: metadata and excerpts of at most 400 characters.
  These rows supply the comment details and links shown on the page. Timestamp
  provenance distinguishes item, parent, and judged-time fallbacks so later
  source dates can repair older fallback dates.
- `data/daily/YYYY-MM-DD.json`: family and family/version counts plus an
  `opinions` list with the item ID, family, version, label, and UTC creation
  time. The page builder joins these opinion records to their item rows.
- `data/incoming.json`: latest fetch input, never the judgment source of truth.
- `data/run-stats.json`: latest classification run counts and completion time,
  embedded into the page during the offline build.

`QUESTION_VERSION` lives beside `Q` in `pipeline/classify.py`. **Bump the version
whenever changing the question text.** Only missing `(id, subject, q)` triples
call Jev. New question versions retain old answers; daily counts and the page use
the most recently judged answer per item/family, avoiding duplicate counts.
IDs carry a source prefix; Reddit posts retain their additional `post:` prefix.
Legacy judgment files remain append-only and their IDs are normalized when read,
so adding source tracking does not repeat old decisions. Item metadata carries
`source` and `community`, including explicit Reddit defaults for old rows.
Successful answers are flushed and synced before
proceeding. A local file lock serializes classifier runs. Failures remain retryable
on the next run. Each run makes at most 12,000 new decision requests, including
failed requests, and logs when this cap is reached; there are no hidden API retries.

The builder reads only daily files and items; it checks that the stored family
and version counts agree with each day's `opinions` list. Existing daily files
that predate `opinions` can be upgraded offline with
`python3 -c 'from pipeline import store; store.rebuild_daily("data")'`. Praise,
complaint, and mixed percentages use opinions as their denominator. The UI calls
praise “liked” and complaint “disliked”; Score is liked% minus disliked%.
Ranking bars show liked, mixed, and disliked shares from left to right. Chart
backgrounds show positive/negative scores, and rings identify each model's zone.
A history note appears when a selected range reaches before the first data day.
Families need 20 opinions in the selected period to
rank. Mentions include neutral rows. These are Reddit sentiment summaries, not
model benchmarks. Time filtering applies to all views and requires no new judging.

Trend alerts compare the last 48 hours ending at midnight UTC immediately after
the selected date with the preceding seven days, using comment timestamps.
Families and named versions need at least 15 opinions now, 20 before, and a
15-point score change to trigger a rise or drop. Newly discussed names need
15 opinions now and fewer than five before. The strip shows up to five alerts,
with the largest score changes first and new names after them. Rise/drop alerts
link to the most-voted praise/complaint in the recent window when available;
ranking and version rows show the corresponding change. The ranking, chart, and
Use-today cards still default to seven days.

## Collection and scheduled publishing

```sh
python3 pipeline/fetch.py
GITHUB_TOKEN=... python3 pipeline/fetch_sources.py
OPENROUTER_API_KEY=... python3 pipeline/classify.py
python3 pipeline/build.py
```

Collection uses Arctic Shift, with subreddits in `config/subreddits.txt` (one per
line, `#` comments allowed). It selects the top 25 qualifying posts by score from the
last five days per subreddit and fetches their comments, retaining timestamps.
At most four requests run concurrently; failures retry with exponential backoff,
and a failed subreddit does not abort other subreddits. Jev uses OpenRouter.
Offline tests use fakes and never need a network connection or API key.

`.github/workflows/pulse.yml` runs at 00:00, 06:00, 12:00, and 18:00 UTC and supports manual
execution. Add the repository secret `OPENROUTER_API_KEY`, enable Actions write
permission for repository contents, and choose **GitHub Actions** as the Pages
source. The workflow fetches, classifies, builds, commits changed data/page files,
and deploys `pulse.html` as the Pages site's `index.html`. Workflow concurrency
serializes scheduled/manual runs so they cannot overlap judgments or commits.

## Dates and quality filtering

Item timestamps determine all daily grouping and chart ranges. Missing comment
timestamps fall back to their parent post, then the recorded judgment time.
Quality filtering runs before Jev: threads older than three days need score 10;
threads up to three days old need five comments. Settled comments with score zero or below,
deleted/removed text, and AutoModerator comments are skipped. Thresholds are
named constants and tested with offline fixtures.

## Sources and community bias

The collection job also reads Hacker News, GitHub issues and comments, Bluesky,
Dev.to, and Lobsters through free endpoints. GitHub repositories are configured
in `config/github_repos.txt`; the scheduled workflow supplies its GitHub token.
Each run fetches at most five issues per repository and ten comments per issue.
Issues must mention a registry name in their title or body before comments are
fetched. GitHub classification has a separate 300-call budget per run, including
failed attempts; existing judgments remain cached. Collection and classification
log their counts.
Bluesky is skipped with a reason if its public search is unavailable or requires
authentication. A failed source does not discard successful sources. Collection
snapshots are inputs to the same quality, classification, and durable store path
as Reddit. Offline tests inject HTTP responses; they never call these services.

The source filter applies to the selected time range. “Where the data comes from”
shows opinion counts, including the busiest Reddit communities. Community tastes
requires 30 opinions per community and 20 per family. Each cell shows its raw
score and its difference from the community's average. Fair score averages these
differences across communities, weighted by opinion count, using cells with at
least 10 opinions. It measures relative reception inside communities; it does
not establish model quality or remove all sampling bias.

Reddit keeps its original `sentiment-v1` question and cache. Other sources use a
generic post/comment question under `sentiment-source-v1`. Each question must be
versioned when its wording changes. GitHub repository context supplies the
repository's own tool as an implicit mention, including replies that do not
repeat the tool's name. Recent replies can retain an older parent for context
without judging the old parent again as a new post.

## Worth reading today

The header links to `reads.html`, a separate daily and seven-day top-ten list.
Candidates need at least five judged opinions. Engagement (comments + score)
is normalized within each community's trailing 30 days, then multiplied by the
share of praise and complaint. A cached, versioned Jev yes/no decision must
have probability at least 0.6 before a thread appears. The curator persists
attempts before calls and limits itself to 60 calls per UTC day.

Run `python3 pipeline/curator.py` after classification to curate new threads;
`python3 pipeline/build.py` builds both pages offline from saved records. The
Pages workflow stages `pulse.html` as `index.html`, plus `reads.html` and
`sources.html`. All pages share navigation. Sources contains the source chart and
community heatmap; GitHub issues remain visible there but are excluded from main
rankings, recommendations, alerts, and buzz scores. Main scores count Reddit, HN,
Dev.to, and Lobsters. For a code-only publication, manually run the Pages workflow
with `refresh_data` disabled to build from saved data without fetching or classifying.
Version details retain raw sentiment scores when family ranking uses Fair scores.

The 24h ranking keeps the same families and seven-day ordering as 7d. Each row
adds a 24h score and direction versus 7d when it has at least eight opinions;
otherwise it shows a muted dash. Use today and alerts use 24h data when there
are at least eight opinions, falling back to seven days with a `(7d)` label.
