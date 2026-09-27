"""Offline contract: identical external IDs survive six sources through the page."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from build import build
from classify import classify
import store

NOW = 1_800_000_000
SOURCES = ('reddit', 'hn', 'github', 'bluesky', 'devto', 'lobsters')


def listing(source):
    community = 'Example' if source == 'reddit' else source.upper()
    url = 'https://example.test/' + source + '/thread'
    post = dict(id='same-post', title='Coding experience', selftext='',
                score=20, num_comments=8, created_utc=NOW - 86400,
                permalink='/r/Example/comments/same-post/thread/', url=url,
                source=source, community=community,
                comments=[dict(id='same-comment', body='Opus is great for coding',
                               score=6, created_utc=NOW - 3600, author='human',
                               url=url + '/comment')])
    return dict(source=source, community=community, top=[post])


class SourcePipelineTests(unittest.TestCase):
    def test_recent_github_reply_inherits_tool_without_judging_old_parent(self):
        raw = listing('github')
        post = raw['top'][0]
        post.update(created_utc=NOW - 20 * 86400, context_only=True,
                    implicit_subjects=[{'name': 'Codex', 'zone': 'tool'}])
        post['comments'][0].update(body='This makes coding so much easier', score=None)
        calls = []

        def decide(state, _questions):
            calls.append(state)
            return {'s': {'choice': 'praise', 'probabilities': {'praise': .9}}}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incoming = root / 'incoming.json'
            incoming.write_text(json.dumps([raw]))
            with patch('classify.time.time', return_value=NOW):
                rows = classify(incoming, root, decide)
            self.assertEqual([r['subject'] for r in rows], ['Codex'])
            self.assertEqual([r['kind'] for r in rows], ['comment'])
            self.assertEqual(len(calls), 1)
            self.assertEqual(rows[0]['thread_comments'], 8)
            self.assertEqual(rows[0]['thread_created_utc'], NOW - 20 * 86400)

    def test_scheduled_input_classifies_reddit_and_other_sources_together(self):
        calls = []
        def decide(state, _questions):
            calls.append(state)
            return {'s': {'choice': 'praise', 'probabilities': {'praise': .9}}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incoming = root / 'incoming.json'
            incoming.write_text(json.dumps([listing('reddit')]))
            (root / 'incoming-sources.json').write_text(json.dumps([listing('hn')]))
            with patch('classify.RAW_PATH', incoming), patch('classify.time.time', return_value=NOW):
                rows = classify(incoming, root, decide)
            self.assertEqual({row['source'] for row in rows}, {'reddit', 'hn'})
            self.assertEqual(len(calls), 2)

    def test_legacy_daily_rows_keep_their_reddit_community(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'items').mkdir()
            item = dict(id='old', subject='Codex', sub='LocalLLaMA',
                        created_utc=NOW, text='Useful coding experience')
            (root / 'items' / '2027-01.jsonl').write_text(json.dumps(item) + '\n')
            store.append_judgment(root, dict(id='old', subject='Codex', q='v1',
                created_utc=NOW, judged_at=NOW, label='praise'))
            store.rebuild_daily(root)
            day = root / 'daily' / (store.date(NOW) + '.json')
            summary = json.loads(day.read_text())
            for row in summary['opinions']:
                row['id'] = 'old'
                row.pop('source', None)
                row.pop('community', None)
            day.write_text(json.dumps(summary))
            output = root / 'pulse.html'
            build(root, output)
            encoded = output.read_text().split('id="pulse-data" type="application/json">')[1].split('</script>')[0]
            self.assertEqual(json.loads(encoded)[0]['community'], 'LocalLLaMA')

    def test_six_sources_do_not_collide_and_rebuild_without_rejudging(self):
        calls = []

        def decide(state, _questions):
            calls.append(state)
            return {'s': {'choice': 'praise', 'probabilities': {'praise': .9}}}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incoming = root / 'incoming.json'
            incoming.write_text(json.dumps({s: listing(s) for s in SOURCES}))
            with patch('classify.time.time', return_value=NOW), patch(
                    'urllib.request.urlopen', side_effect=AssertionError('Network forbidden')):
                first = classify(incoming, root, decide)
                second = classify(incoming, root, decide)
                output = root / 'pulse.html'
                build(root, output)
            self.assertEqual(len(calls), 6)
            self.assertEqual(len(first), len(second))
            self.assertEqual({r['source'] for r in second}, set(SOURCES))
            self.assertEqual(len({r['id'] for r in second}), 6)
            self.assertTrue(all(r['id'].startswith(r['source'] + ':') for r in second))
            self.assertTrue(all(r['community'] for r in second))
            self.assertEqual(len(list(store.read_rows(root / 'judgments'))), 6)
            page = output.read_text()
            encoded = page.split('id="pulse-data" type="application/json">')[1].split('</script>')[0]
            self.assertEqual({r['source'] for r in json.loads(encoded)}, set(SOURCES))


if __name__ == '__main__':
    unittest.main()
