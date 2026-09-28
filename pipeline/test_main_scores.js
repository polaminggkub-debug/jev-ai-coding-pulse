// Ensure bug trackers and other non-score sources cannot enter the main score.
const assert = require('node:assert/strict');
const {harness, text} = require('./ui_harness');

function batch(subject, source, label, count, day = '2026-09-27') {
  return Array.from({length: count}, (_, index) => ({subject, source, label, kind: 'comment', zone: 'us',
    community: source === 'github' ? 'owner/repo' : source, sub: source,
    created_utc: `${day}T12:00:00Z`, text: `${source} ${subject} ${index}`, score: index,
    link: `https://example.test/${source}/${subject}/${index}`}));
}

const rows = [
  ...batch('Shared', 'reddit', 'praise', 20),
  ...batch('Shared', 'github', 'complaint', 60),
  ...batch('GitHub cheer', 'github', 'praise', 60),
  ...batch('Bug Tracker', 'github', 'complaint', 40),
  ...batch('Sky only', 'bluesky', 'praise', 40),
  ...batch('Reddit win', 'reddit', 'praise', 30),
  ...batch('HN win', 'hn', 'praise', 25),
  ...batch('Dev win', 'devto', 'praise', 25),
  ...batch('Lobsters win', 'lobsters', 'praise', 25),
  ...batch('Main trend', 'hn', 'praise', 20, '2026-09-20'),
  ...batch('Main trend', 'hn', 'complaint', 20),
  ...batch('GitHub trend', 'github', 'praise', 20, '2026-09-20'),
  ...batch('GitHub trend', 'github', 'complaint', 20)
];
const meta = {days: ['2026-09-20', '2026-09-27'], startDate: '2026-09-20', endDate: '2026-09-27'};
const main = harness(rows, meta);
main.run(['pulse.js', 'pulse-sources.js', 'pulse-trends.js', 'pulse-trend-ui.js', 'pulse-community.js',
  'pulse-rank.js', 'pulse-chart.js']);
const P = main.context.Pulse;

assert.equal(P.page, 'rankings');
assert.deepEqual(Array.from(new Set(P.rowsForRange().map(row => row.source))).sort(),
  ['devto', 'hn', 'lobsters', 'reddit']);
assert.ok(P.rowsForRange().every(row => P.mainSourceIds.includes(row.source)),
  'The default main dataset is restricted to its explicit four-source allowlist');
assert.equal(P.chartModels.find(model => model.subject === 'Shared').stats.net, 100,
  'GitHub complaints cannot drag down a model that also has Reddit praise');
assert.ok(!P.chartModels.some(model => ['Bug Tracker', 'Sky only', 'GitHub trend'].includes(model.subject)),
  'GitHub and Bluesky families are absent from the default ranking');
assert.doesNotMatch(text(main.ids['use-today']), /Bug Tracker|Sky only|GitHub trend/,
  'Use today uses the same filtered dataset');
assert.doesNotMatch(main.ids.chart.innerHTML, /Bug Tracker|GitHub trend|Sky only/,
  'The buzz chart uses the same filtered dataset');
assert.ok(P.trendAlerts.some(alert => alert.subject === 'Main trend'), 'Allowed-source alerts still render');
assert.ok(!P.trendAlerts.some(alert => alert.subject === 'GitHub trend'),
  'GitHub trends cannot create main-page alerts');

// On Sources, the full six-source set remains inspectable. Its GitHub aggregate
// row must survive both the 30-opinion community cutoff and an empty family list.
const sources = harness([batch('Low-volume issue', 'github', 'complaint', 3)[0]],
  {...meta, page: 'sources'});
delete sources.ids['score-mode'];
sources.run(['pulse.js', 'pulse-sources.js', 'pulse-community.js', 'pulse-trends.js', 'pulse-trend-ui.js',
  'pulse-rank.js', 'pulse-chart.js']);
const SP = sources.context.Pulse;
assert.equal(SP.page, 'sources');
assert.equal(SP.rowsForRange().length, 1, 'Sources page keeps GitHub rows in the unfiltered range');
assert.match(text(sources.ids['community-heatmap']), /GitHub — bug reports — not counted in main score/,
  'Low-volume GitHub issues have a visible, explicitly excluded aggregate row');
const heatBody = sources.ids['community-heatmap'].querySelector('tbody');
assert.equal(heatBody.querySelectorAll('tr').length, 1,
  'A GitHub aggregate row renders below the community and family thresholds');
assert.equal(heatBody.querySelector('tr').children[1].textContent, '1');
assert.equal(typeof sources.ids['source-filter'].events.change, 'function',
  'Source filter binds when score-mode is absent');
sources.ids['source-filter'].value = 'reddit';
sources.ids['source-filter'].events.change();
assert.equal(SP.rowsForRange().length, 0, 'Sources-page source filter still filters independently');

// Conversely, the ranking score-mode must bind when its template has no source filter.
const ranking = harness([
  ...batch('Fair candidate', 'reddit', 'praise', 20),
  ...batch('Reddit counter', 'reddit', 'complaint', 20),
  ...batch('Fair candidate', 'github', 'complaint', 20),
  ...batch('GitHub cheer', 'github', 'praise', 20)
], meta);
delete ranking.ids['source-filter'];
ranking.run(['pulse.js', 'pulse-sources.js', 'pulse-trends.js', 'pulse-trend-ui.js', 'pulse-community.js',
  'pulse-rank.js', 'pulse-chart.js']);
ranking.ids['score-mode'].value = 'fair';
ranking.ids['score-mode'].events.change();
assert.equal(ranking.context.Pulse.scoreMode, 'fair', 'Score mode binds when source-filter is absent');
assert.equal(ranking.context.Pulse.chartModels.find(model => model.subject === 'Fair candidate').fairNet, 100,
  'GitHub opinions cannot shift Fair score baselines');

console.log('Main score source exclusion and Sources GitHub visibility checks passed.');
