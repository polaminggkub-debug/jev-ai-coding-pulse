"""Regression: build metadata and range data use item dates, not judging dates."""
import json
from pathlib import Path
import tempfile
import unittest

from build import build
from test_build import item, write_dataset


class BuildDateTests(unittest.TestCase):
    def test_judged_today_written_twenty_days_ago(self):
        row = item('old-comment', '2026-09-08', 'Opus is good', 20)
        labels = {'2026-09-28': [dict(id='old-comment', subject='Claude Opus',
                  label='praise', created_utc='2026-09-28T12:00:00Z')]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_dataset(root, [row], labels)
            build(root, root / 'pulse.html')
            page = (root / 'pulse.html').read_text()
        def payload(name):
            return json.loads(page.split(f'id="{name}" type="application/json">')[1].split('</script>')[0])
        self.assertEqual(payload('pulse-data')[0]['date'], '2026-09-08')
        self.assertEqual(payload('pulse-data')[0]['created_utc'], row['created_utc'])
        self.assertEqual(payload('pulse-meta')['days'], ['2026-09-08'])
        self.assertLess(page.index('id="use-today"'), page.index('id="timeline"'))

    def test_parent_then_judged_fallback_reaches_page(self):
        for parent, expected in [('2026-09-07T12:00:00Z', '2026-09-07'), (None, '2026-09-28')]:
            with self.subTest(parent=parent), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                row = item('missing-date', '2026-09-08', 'Opus is good', 20)
                row['created_utc'] = None
                row['parent_created_utc'] = parent
                labels = {'2026-09-28': [dict(id='missing-date', subject='Claude Opus',
                          label='praise', judged_at='2026-09-28T12:00:00Z')]}
                write_dataset(root, [row], labels)
                build(root, root / 'pulse.html')
                page = (root / 'pulse.html').read_text()
                data = json.loads(page.split('id="pulse-data" type="application/json">')[1].split('</script>')[0])
                self.assertEqual(data[0]['date'], expected)


if __name__ == '__main__':
    unittest.main()
