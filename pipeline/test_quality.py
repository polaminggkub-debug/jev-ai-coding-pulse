"""Offline boundary checks for data-quality thresholds."""

import unittest

from quality import (
    MIN_RECENT_THREAD_COMMENTS,
    MIN_SETTLED_COMMENT_SCORE,
    MIN_SETTLED_THREAD_SCORE,
    SETTLED_THREAD_AGE_DAYS,
    SECONDS_PER_DAY,
    comment_qualifies,
    thread_qualifies,
)

NOW = 200 * SECONDS_PER_DAY


class QualityTests(unittest.TestCase):
    def test_named_thresholds_match_the_specification(self):
        self.assertEqual(SETTLED_THREAD_AGE_DAYS, 3)
        self.assertEqual(MIN_SETTLED_THREAD_SCORE, 10)
        self.assertEqual(MIN_RECENT_THREAD_COMMENTS, 5)
        self.assertEqual(MIN_SETTLED_COMMENT_SCORE, 0)

    def test_settled_threads_need_ten_votes_and_recent_threads_need_five_comments(self):
        settled = {"created_utc": NOW - 4 * SECONDS_PER_DAY, "num_comments": 0}
        self.assertFalse(thread_qualifies({**settled, "score": 9}, now=NOW))
        self.assertTrue(thread_qualifies({**settled, "score": 10}, now=NOW))

        recent = {"created_utc": NOW - 2 * SECONDS_PER_DAY, "score": 1000}
        self.assertFalse(thread_qualifies({**recent, "num_comments": 4}, now=NOW))
        self.assertTrue(thread_qualifies({**recent, "num_comments": 5}, now=NOW))

    def test_thread_age_boundary_switches_after_three_days(self):
        exactly_three_days = NOW - 3 * SECONDS_PER_DAY
        just_over = exactly_three_days - 1
        self.assertTrue(thread_qualifies(
            {"created_utc": exactly_three_days, "score": 0, "num_comments": 5}, now=NOW))
        self.assertFalse(thread_qualifies(
            {"created_utc": just_over, "score": 9, "num_comments": 5}, now=NOW))
        self.assertTrue(thread_qualifies(
            {"created_utc": just_over, "score": 10, "num_comments": 0}, now=NOW))

    def test_comment_score_gate_applies_after_three_days_and_uses_parent_date(self):
        settled = {"body": "A useful comment", "created_utc": None, "score": 0}
        old_parent = NOW - 4 * SECONDS_PER_DAY
        self.assertFalse(comment_qualifies(settled, now=NOW, parent_created_utc=old_parent))
        self.assertTrue(comment_qualifies({**settled, "score": 1}, now=NOW,
                                          parent_created_utc=old_parent))
        self.assertTrue(comment_qualifies(settled, now=NOW,
                                         parent_created_utc=NOW - 2 * SECONDS_PER_DAY))

    def test_comment_score_boundary_switches_after_three_days(self):
        exactly_three_days = NOW - 3 * SECONDS_PER_DAY
        just_over = exactly_three_days - 1
        comment = {"body": "A useful comment", "score": 0}
        self.assertTrue(comment_qualifies(
            {**comment, "created_utc": exactly_three_days}, now=NOW))
        self.assertFalse(comment_qualifies(
            {**comment, "created_utc": just_over}, now=NOW))
        self.assertTrue(comment_qualifies(
            {**comment, "created_utc": just_over, "score": 1}, now=NOW))

    def test_removed_empty_and_automoderator_comments_are_skipped(self):
        for body in ("[deleted]", "[removed]", "  [REMOVED]  ", ""):
            self.assertFalse(comment_qualifies({"body": body, "score": 5}, now=NOW))
        self.assertFalse(comment_qualifies(
            {"body": "I like Opus 5.5", "author": "AutoModerator", "score": 5}, now=NOW))
        self.assertTrue(comment_qualifies(
            {"body": "I like Opus 5.5", "author": "human", "score": 0}, now=NOW))


if __name__ == "__main__":
    unittest.main()
