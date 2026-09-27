"""Offline tests for thread eligibility, ranking, and durable Jev answers."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import curator
import curator_decisions
import store

NOW = dt.datetime.fromisoformat("2026-09-28T12:00:00+00:00").timestamp()
TODAY = "2026-09-28"


def add_thread(root, slug, labels, *, score=20, comments=10, community="Example",
               source="reddit", day=TODAY, title=None):
    created = dt.datetime.fromisoformat(f"{day}T10:00:00+00:00").timestamp()
    title = title or f"{slug} AI coding tools comparison"
    items, judgments = [], []
    for index, entry in enumerate(labels):
        if isinstance(entry, tuple):
            item_id, subject, label = entry
        else:
            item_id, subject, label = f"{slug}-c{index}", "Claude Code", entry
        link = f"https://discussion.test/{source}/{slug}#comment-{item_id}"
        items.append({"id": item_id, "kind": "comment", "source": source,
            "community": community, "thread": title,
            "thread_url": f"https://discussion.test/{source}/{slug}",
            "thread_created_utc": created, "created_utc": created,
            "parent_created_utc": created, "thread_score": score,
            "thread_comments": comments, "score": index, "link": link,
            "subject": subject, "text": f"{item_id} {label} experience with {subject}"})
        judgments.append({"id": item_id, "kind": "comment", "subject": subject,
            "q": "sentiment-v1", "label": label, "probs": {label: 0.9},
            "created_utc": created, "judged_at": created + index})
    item_dir, judgment_dir = Path(root) / "items", Path(root) / "judgments"
    item_dir.mkdir(parents=True, exist_ok=True)
    judgment_dir.mkdir(parents=True, exist_ok=True)
    month = day[:7]
    with (item_dir / f"{month}.jsonl").open("a", encoding="utf-8") as handle:
        handle.writelines(json.dumps(row) + "\n" for row in items)
    with (judgment_dir / f"{month}.jsonl").open("a", encoding="utf-8") as handle:
        handle.writelines(json.dumps(row) + "\n" for row in judgments)


def five_praises(slug, subject="Claude Code"):
    return [(f"{slug}-c{i}", subject, "praise") for i in range(5)]


class CuratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "data"

    def tearDown(self):
        self.temp.cleanup()

    def test_five_opinions_and_item_subject_dedup_drive_candidate_eligibility(self):
        labels = five_praises("multi")
        labels[4] = ("multi-c3", "Codex", "complaint")
        add_thread(self.root, "multi", labels)
        rows = store.load_mentions(self.root)
        rows.append(dict(rows[0]))

        ranked = curator.ranked_candidates(rows, NOW)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["opinions"], 5)
        self.assertEqual(ranked[0]["comments"], 10)
        self.assertEqual(set(ranked[0]["models"]), {"Claude Code", "Codex"})
        self.assertEqual(curator_decisions._decision_state(ranked[0])["text"].count("multi-c3"), 1)

    def test_neutral_judgments_lower_heat_and_heated_threshold_uses_all_labels(self):
        add_thread(self.root, "neutral", ["praise"] * 5 + ["no_opinion"] * 95)
        add_thread(self.root, "debate", ["praise"] * 3 + ["complaint"] * 3 + ["no_opinion"] * 4)

        ranked = {row["title"].split()[0]: row
                  for row in curator.ranked_candidates(store.load_mentions(self.root), NOW)}

        self.assertAlmostEqual(ranked["neutral"]["heat"], 0.05)
        self.assertNotEqual(ranked["neutral"]["label"], "🔥 Heated debate")
        self.assertAlmostEqual(ranked["debate"]["heat"], 0.6)
        self.assertEqual(ranked["debate"]["label"], "🔥 Heated debate")

    def test_engagement_uses_midpoint_percentiles_for_each_community(self):
        add_thread(self.root, "low", ["praise"], score=10, comments=0)
        add_thread(self.root, "middle", ["praise"], score=20, comments=0)
        add_thread(self.root, "high", five_praises("high"), score=30, comments=0)
        add_thread(self.root, "alone", five_praises("alone"), score=100, comments=0,
                   community="OneThread")

        ranked = {row["title"].split()[0]: row
                  for row in curator.ranked_candidates(store.load_mentions(self.root), NOW)}

        self.assertAlmostEqual(ranked["high"]["engagement_percentile"], 5 / 6)
        self.assertAlmostEqual(ranked["alone"]["engagement_percentile"], 0.5)
        self.assertAlmostEqual(ranked["alone"]["rank_score"], 0.5)

    def test_jev_answers_are_cached_and_only_yes_at_least_point_six_is_shown(self):
        for slug in ("keep", "lowprob", "reject"):
            add_thread(self.root, slug, five_praises(slug))
        called = []

        def decide(state, questions):
            called.append((state, questions))
            title = state["text"].splitlines()[0]
            choice, probability = (("yes", 0.8) if "keep" in title else
                                   ("yes", 0.59) if "lowprob" in title else ("no", 0.9))
            return {"s": {"choice": choice, "probabilities": {choice: probability}}}

        first = curator.curate(self.root, decide, now=NOW)
        again = curator.curate(self.root, decide, now=NOW)
        payload = curator.reads_payload(self.root, now=NOW)
        answers = list(store.read_rows(self.root / "curation"))

        self.assertEqual(first["calls"], 3)
        self.assertEqual(again["calls"], 0)
        self.assertEqual(len(called), 3)
        self.assertIn("Answer yes or no", called[0][1]["s"]["instructions"])
        self.assertEqual([row["title"] for row in payload["daily"][TODAY]],
                         ["keep AI coding tools comparison"])
        self.assertEqual(len(answers), 3)
        self.assertTrue(all(row["q"] == curator.QUESTION_VERSION for row in answers))

    def test_failed_calls_count_toward_daily_cap_and_are_not_retried(self):
        for slug in ("first", "second", "third"):
            add_thread(self.root, slug, five_praises(slug))
        calls = []

        def fail(_state, _questions):
            calls.append(True)
            raise RuntimeError("offline")

        first = curator.curate(self.root, fail, now=NOW, max_calls=2)
        same_day = curator.curate(self.root, fail, now=NOW, max_calls=2)
        next_day = curator.curate(self.root, fail, now=NOW + 86400, max_calls=2)

        self.assertEqual(first["calls"], 2)
        self.assertEqual(first["failed"], 2)
        self.assertEqual(same_day["calls"], 0)
        self.assertEqual(next_day["calls"], 1)
        self.assertEqual(len(calls), 3)
        attempts = list(store.read_rows(self.root / "curation-attempts"))
        self.assertEqual(len(attempts), 3)

    def test_hard_limit_is_sixty_even_when_caller_requests_more(self):
        for index in range(61):
            slug = f"bulk-{index:02d}"
            add_thread(self.root, slug, five_praises(slug))

        result = curator.curate(self.root,
            lambda *_: {"s": {"choice": "yes", "probabilities": {"yes": 0.8}}},
            now=NOW, max_calls=100)

        self.assertEqual(curator.MAX_DAILY_CALLS, 60)
        self.assertEqual(result["calls"], 60)
        self.assertEqual(len(list(store.read_rows(self.root / "curation-attempts"))), 60)

    def test_call_budget_rolls_over_when_one_run_crosses_utc_midnight(self):
        add_thread(self.root, "midnight-a", five_praises("midnight-a"))
        add_thread(self.root, "midnight-b", five_praises("midnight-b"))
        before = dt.datetime.fromisoformat("2026-09-28T23:59:58+00:00").timestamp()
        after = dt.datetime.fromisoformat("2026-09-29T00:00:01+00:00").timestamp()
        clock = [before, before, after, after, after, after]

        with patch.object(curator_decisions.time, "time", side_effect=clock):
            result = curator.curate(self.root,
                lambda *_: {"s": {"choice": "yes", "probabilities": {"yes": 0.8}}},
                max_calls=1)

        self.assertEqual(result["calls"], 2)
        attempts = list(store.read_rows(self.root / "curation-attempts"))
        self.assertEqual({store.date(row["attempted_at"]) for row in attempts},
                         {"2026-09-28", "2026-09-29"})


if __name__ == "__main__":
    unittest.main()
