import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest

from update_info import metadata, next_run


class UpdateInfoTests(unittest.TestCase):
    def test_next_run_uses_workflow_and_rolls_over_utc_day(self):
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / 'pulse.yml'
            workflow.write_text('schedule:\n  - cron: "0 0,6,12,18 * * *"\n')
            self.assertEqual(next_run(workflow, dt.datetime(2026, 9, 28, 0, 4, tzinfo=dt.timezone.utc)),
                             '2026-09-28T06:00:00Z')
            self.assertEqual(next_run(workflow, dt.datetime(2026, 9, 28, 18, tzinfo=dt.timezone.utc)),
                             '2026-09-29T00:00:00Z')
            workflow.write_text('schedule:\n  - cron: "30 */6 * * *"\n')
            self.assertEqual(next_run(workflow, dt.datetime(2026, 9, 28, 0, 4, tzinfo=dt.timezone.utc)),
                             '2026-09-28T00:30:00Z')

    def test_metadata_embeds_run_stats_without_inventing_legacy_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / 'pulse.yml'
            workflow.write_text('- cron: "0 0,6,12,18 * * *"')
            now = dt.datetime(2026, 9, 28, 0, 4, tzinfo=dt.timezone.utc)
            self.assertEqual(metadata([], [], root, workflow, now)['runStats'], {})
            (root / 'run-stats.json').write_text(json.dumps({'newOpinions': 1811}))
            result = metadata([], ['2026-08-29', '2026-09-28'], root, workflow, now)
            self.assertEqual(result['runStats']['newOpinions'], 1811)
            self.assertEqual(result['nextUpdateAt'], '2026-09-28T06:00:00Z')
            self.assertEqual(result['startDate'], '2026-08-29')
            self.assertEqual(result['updatedAt'], '2026-09-28T00:04:00Z')


if __name__ == '__main__':
    unittest.main()
