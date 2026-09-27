# TASK7 / TASK8 verification

Run `scripts/check.sh` from the repository root. Tests use fake HTTP and fake
Jev answers; no API credentials or live network are required. The fixture log
`failed r/Broken` is intentional.

## TASK7

- Exercise free-source adapters with bounded dates, pagination, thresholds,
  family coverage, and source-level failure isolation.
- Classify identical raw IDs from all six sources, rerun, and build the page:
  IDs must remain distinct and cached decisions must prevent repeat calls.
- Preserve existing judgments while adding source/community metadata.
- Change date range, source, and Raw/Fair score controls; verify displayed
  counts, ranking/chart scores, heatmap thresholds, and quote attribution.

## TASK8

- Deduplicate threads/items and require five judged opinions; normalize
  engagement within each community's trailing 30-day population.
- Persist versioned curator answers and attempts, enforce 60 calls per UTC day,
  and exclude candidates below the 0.6 relevance threshold.
- Verify daily top 10 and seven-day top 10 selection, navigation, card metadata,
  labels, model identity, and the highest-voted comment.
- Build and stage both offline pages for Pages deployment.

## Verification boundary

Local source and interaction checks pass for Timeline removal and TASK7.
A Vivaldi walkthrough of the rebuilt page verified named subreddit rows, the
source bars and heatmap, an empty Hacker News filter, and changed family scores
and chart coordinates after switching Raw to Fair. Screenshots were captured
in the coordinating conversation. This uses the existing Reddit data snapshot;
live non-Reddit collection is verified separately by the deployment workflow.

The shared GitHub comment-quality regression exercises classification with
recent zero-score, settled zero-score, and removed-text comments. Legacy daily
records have a regression ensuring original subreddit names survive ID-prefix
normalization. Duplicate judgment lines use the final line for the same
id/subject/question, without adding duplicate daily opinions.

API contracts checked during the repair:
- [Forem comments API](https://developers.forem.com/api/v1#tag/comments):
  `/api/comments?a_id=...`, with nested children and `id_code` identities.
- [Bluesky search lexicon](https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/searchPosts.json):
  search results contain direct post views.

TASK8 was rendered in Vivaldi with a separate synthetic five-card fixture.
Daily and weekly controls changed the card set, previous-day navigation changed
the seven-day window, and light/dark themes rendered correctly. At 390 CSS pixels,
controls and cards fit a single-column phone layout. The empty production-cache
page displays a named date option and an honest no-picks state. This fixture is
not included in the deployed data.

The complete offline check suite passes, including actual reads DOM handlers and
card rendering, cached decisions, rejection below 0.6, daily attempt limits,
community percentiles, and neutral-opinion heat denominators.
A green test suite alone does not establish live source coverage; release and
live collection evidence is recorded separately in the coordinating report.

## First live collection and recovery

Run `36348702393` committed its collected data and 42 curated picks, then Pages
deployment failed because GitHub issue-by-issue comment requests exhausted the
installation API allowance. Saved input contained HN, GitHub, and Dev.to data;
Bluesky returned 403 (the task explicitly permits a clean skip), and Lobsters
exposed a parser mismatch. Those operational findings are separate from the
offline test result.

Additional source contracts checked during recovery:
- [Algolia item response](https://hn.algolia.com/api/v1/items/1) supplies nested
  comments rather than a `num_comments` field. The HN regression exercises a
  parent found solely through a comment search and counts nested replies.
- [Forem article query](https://developers.forem.com/api/v1#tag/articles): tag
  results use popularity order, so `top=5` constrains them to the requested
  publication window. An unavailable comment endpoint no longer drops an
  otherwise eligible article or causes repeated requests across tags.

Recovery regressions reproduce the GitHub quota exhaustion before the fix,
then verify bulk repository comment grouping, an 800-attempt ceiling, a
100-request deployment reserve, and retained partial pages. Lobsters fixtures
reproduce the string-valued `commenting_user` response from both public tag
feeds; string and mapping author formats are accepted.
