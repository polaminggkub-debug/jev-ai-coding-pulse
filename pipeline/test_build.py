import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build as build_module
from build import build, load_mentions


class BuildTests(unittest.TestCase):
    def test_default_build_reads_the_durable_data_directory(self):
        row = dict(id='comment-1', comment_id='comment-1', subject='Claude Opus', text='Opus 5.5',
                   thread='Opus 5.5', link='https://reddit.com/comment-1', created_utc=1,
                   label='praise', zone='us')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'pulse.html'
            with patch('store.load_mentions', return_value=[row]) as load, \
                    patch('migrate.migrate') as migrate, patch('store.rebuild_daily') as daily:
                self.assertEqual(build(output=output), 1)
            self.assertEqual(load.call_args.args[0], build_module.ROOT / 'data')
            self.assertEqual(migrate.call_args.args[0], build_module.ROOT / 'data')
            self.assertEqual(daily.call_args.args[0], build_module.ROOT / 'data')
            self.assertIn('Today', output.read_text())
            self.assertIn('7 days', output.read_text())
            self.assertIn('30 days', output.read_text())

    def test_offline_embedding_versions_and_script_escape(self):
        row = dict(subject='Claude Opus', text='Opus 5.5 </script><script>alert(1)</script>',
                   thread='Opus 4', link='https://reddit.com/test', zone='us')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'labeled.json'
            output = Path(directory) / 'pulse.html'
            source.write_text(json.dumps([row, row]))
            with patch('urllib.request.urlopen', side_effect=AssertionError('Network forbidden')):
                self.assertEqual(build(source, output), 1)
            page = output.read_text()
            payload = page.split('type="application/json">')[1].split('</script>')[0]
            data = json.loads(payload)
            self.assertEqual(data[0]['version'], 'Opus 5.5')
            self.assertEqual(data[0]['text'], row['text'])
            self.assertNotIn('</script>', payload)
            self.assertNotIn('<script src=', page)
            self.assertNotIn('<link ', page)
            self.assertLessEqual(len(page.splitlines()), 300)

    def test_preserves_version_extracted_before_comment_truncation(self):
        row = dict(subject='Claude Opus', text='Opus is great', thread='Opus 4',
                   version='Opus 5.5', link='https://reddit.com/test')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'labels.json'
            source.write_text(json.dumps([row]))
            self.assertEqual(load_mentions(source)[0]['version'], 'Opus 5.5')

    def test_unknown_is_null_and_thread_fallback_is_used(self):
        rows = [dict(subject='Qwen', text='Qwen is good', thread=title, link=str(i))
                for i, title in enumerate(['Coding discussion', 'Qwen3.8 release'])]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'labels.json'
            source.write_text(json.dumps(rows))
            self.assertEqual([r['version'] for r in load_mentions(source)], [None, 'Qwen 3.8'])


if __name__ == '__main__':
    unittest.main()
