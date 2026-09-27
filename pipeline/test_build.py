import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build as build_module
from build import build, load_mentions


def stamp(value):
    return dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp()


def item(item_id, day, text, score):
    return {
        'id': item_id, 'kind': 'comment', 'sub': 'Example', 'score': score,
        'link': f'https://reddit.test/{item_id}', 'thread': 'A coding discussion',
        'thread_score': 12, 'thread_url': 'https://reddit.test/thread',
        'subject': 'Claude Opus', 'zone': 'us', 'version': 'Opus 5.5', 'text': text,
        'created_utc': stamp(day + 'T12:00:00'),
    }


def bump(groups, name, label):
    counts = groups.setdefault(name, dict(praise=0, complaint=0, mixed=0, no_opinion=0, opinion=0))
    counts[label] += 1
    counts['opinion'] += label != 'no_opinion'


def write_dataset(root, rows, labels):
    (root / 'items').mkdir(parents=True)
    (root / 'daily').mkdir(parents=True)
    (root / 'items' / '2026-01.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    for day, opinions in labels.items():
        families, versions = {}, {}
        for opinion in opinions:
            bump(families, opinion['subject'], opinion['label'])
            if opinion.get('version'):
                version_counts = versions.setdefault(opinion['subject'], {})
                bump(version_counts, opinion['version'], opinion['label'])
        data = {
            'families': families, 'versions': versions, 'opinions': opinions,
        }
        (root / 'daily' / (day + '.json')).write_text(json.dumps(data), encoding='utf-8')


class BuildTests(unittest.TestCase):
    def test_build_reads_all_daily_items_without_judgments(self):
        first = item('comment-1', '2026-01-02', 'Opus is wonderful', 31)
        second = item('comment-2', '2026-01-03', 'Opus is too slow', 18)
        opinions = {
            '2026-01-02': [dict(id='comment-1', subject='Claude Opus', version='Opus 5.5',
                                label='praise', q='sentiment-v1', probs={'praise': 0.98},
                                created_utc=first['created_utc'])],
            '2026-01-03': [dict(id='comment-2', subject='Claude Opus', version='Opus 5.5',
                                label='complaint', q='sentiment-v1', probs={'complaint': 0.93},
                                created_utc=second['created_utc'])],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_dataset(root, [first, second], opinions)
            output = root / 'pulse.html'
            with patch.object(build_module.store, 'load_mentions',
                              side_effect=AssertionError('Build must not read judgments')):
                self.assertEqual(build(root, output), 2)
            page = output.read_text(encoding='utf-8')
            data = json.loads(page.split('id="pulse-data" type="application/json">')[1]
                              .split('</script>')[0])
            meta = json.loads(page.split('id="pulse-meta" type="application/json">')[1]
                              .split('</script>')[0])
            self.assertEqual([row['label'] for row in data], ['praise', 'complaint'])
            self.assertEqual([row['date'] for row in data], ['2026-01-02', '2026-01-03'])
            self.assertEqual(data[0]['text'], first['text'])
            self.assertEqual(data[0]['link'], first['link'])
            self.assertEqual(data[0]['q'], 'sentiment-v1')
            self.assertEqual(meta['days'], ['2026-01-02', '2026-01-03'])
            self.assertEqual(meta['startDate'], '2026-01-02')
            self.assertEqual(meta['endDate'], '2026-01-03')
            self.assertTrue(meta['updatedAt'].endswith('Z'))

    def test_offline_legacy_embedding_preserves_versions_and_escapes_script_markup(self):
        row = dict(subject='Claude Opus', text='Opus 5.5 </script><script>alert(1)</script>',
                   thread='Opus 4', link='https://reddit.test/comment', zone='us', label='praise')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'labeled.json'
            output = Path(directory) / 'pulse.html'
            source.write_text(json.dumps([row, row]), encoding='utf-8')
            with patch('urllib.request.urlopen', side_effect=AssertionError('Network forbidden')):
                self.assertEqual(build(source, output), 1)
            page = output.read_text(encoding='utf-8')
            encoded = page.split('id="pulse-data" type="application/json">')[1].split('</script>')[0]
            data = json.loads(encoded)
            self.assertEqual(data[0]['version'], 'Opus 5.5')
            self.assertEqual(data[0]['label'], 'praise')
            self.assertNotIn('</script>', encoded)
            self.assertNotIn('<script src=', page)
            self.assertNotIn('<link ', page)
            sources = [*build_module.ASSETS.glob('*.py'), *build_module.ASSETS.glob('*.js'),
                       *build_module.ASSETS.glob('*.css')]
            self.assertTrue(sources)
            self.assertTrue(all(len(path.read_text(encoding='utf-8').splitlines()) <= 300
                                for path in sources))

    def test_all_vendored_logos_are_embedded_and_required_time_controls_exist(self):
        row = item('comment-1', '2026-01-02', 'Opus is great', 4)
        labels = {'2026-01-02': [dict(id='comment-1', subject='Claude Opus', label='praise',
                                      created_utc=row['created_utc'])]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_dataset(root, [row], labels)
            output = root / 'pulse.html'
            build(root, output)
            page = output.read_text(encoding='utf-8')
        logos = json.loads(page.split('id="pulse-logos" type="application/json">')[1]
                           .split('</script>')[0])
        self.assertEqual(set(logos), {path.stem for path in build_module.LOGOS.glob('*.svg')})
        self.assertTrue(all('<svg' in logo for logo in logos.values()))
        for element_id in ('trend-alerts', 'use-today', 'chart', 'covered-period', 'date-prev', 'date-next',
                           'date-end', 'back-latest', 'range-today', 'range-7', 'range-30',
                           'range-status', 'history-note', 'expand'):
            self.assertIn(f'id="{element_id}"', page)
        self.assertLess(page.index('id="trend-alerts"'), page.index('id="use-today"'))

    def test_count_only_daily_records_explain_the_required_offline_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'daily').mkdir()
            (root / 'daily' / '2026-01-02.json').write_text(
                json.dumps({'families': {'Claude Opus': {'opinion': 1}}}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'store.rebuild_daily'):
                build(root, root / 'pulse.html')

    def test_stale_daily_aggregates_cannot_hide_label_rows(self):
        row = item('comment-1', '2026-01-02', 'Opus is great', 4)
        labels = {'2026-01-02': [dict(id='comment-1', subject='Claude Opus', version='Opus 5.5',
                                      label='praise', created_utc=row['created_utc'])]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_dataset(root, [row], labels)
            daily = root / 'daily' / '2026-01-02.json'
            counts = json.loads(daily.read_text(encoding='utf-8'))
            counts['families']['Claude Opus']['praise'] = 0
            daily.write_text(json.dumps(counts), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'aggregates do not match'):
                build(root, root / 'pulse.html')

    def test_preserves_existing_version_and_extracts_unknown_versions(self):
        rows = [dict(subject=subject, text=text, thread=title, link=str(index))
                for index, (subject, text, title) in enumerate([
                    ('Claude Opus', 'Opus is good', 'Coding discussion'),
                    ('Qwen', 'Qwen is good', 'Qwen 3.8 release')])]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'labels.json'
            source.write_text(json.dumps(rows), encoding='utf-8')
            loaded = load_mentions(source)
        self.assertEqual([row['version'] for row in loaded], [None, 'Qwen 3.8'])

    def test_preserves_an_existing_version_before_legacy_comment_truncation(self):
        row = dict(subject='Claude Opus', text='Opus is good', thread='Opus 4',
                   version='Opus 5.5', link='https://reddit.test/comment')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'labels.json'
            source.write_text(json.dumps([row]), encoding='utf-8')
            loaded = load_mentions(source)
        self.assertEqual(loaded[0]['version'], 'Opus 5.5')


if __name__ == '__main__':
    unittest.main()
