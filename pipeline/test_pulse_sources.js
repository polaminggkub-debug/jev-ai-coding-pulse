// Exercise the Sources page with only the elements its generated HTML provides.
const assert = require('node:assert/strict');
const {harness, text} = require('./ui_harness');
function batch(subject, community, praise, complaint, source = 'reddit') {
  return Array.from({length: praise + complaint}, (_, i) => ({subject, community, sub: community,
    source, label: i < praise ? 'praise' : 'complaint', created_utc: '2026-09-27T12:00:00Z',
    kind: 'comment', text: `${community} comment ${i}`, score: i, zone: 'us'}));
}
const rows = [...batch('A', 'Positive', 20, 0), ...batch('B', 'Positive', 15, 5),
  ...batch('A', 'Negative', 5, 15, 'github'), ...batch('B', 'Negative', 0, 20, 'github'),
  ...batch('Rare', 'Tiny', 1, 0)];
const h = harness(rows, {page: 'sources'});
// Remove ranking-only controls from the fake DOM so boot matches sources.html.
for (const id of ['trend-alerts', 'use-today', 'chart', 'search', 'score-mode', 'zones',
  'chips', 'selection', 'expand']) delete h.ids[id];
h.run(['pulse.js', 'pulse-sources.js', 'pulse-community.js', 'pulse-trends.js',
  'pulse-trend-ui.js', 'pulse-rank.js', 'pulse-chart.js']);
const P = h.context.Pulse;
assert.equal(P.page, 'sources');
assert.equal(P.rowsForRange().length, 81, 'Sources retains all source rows by default');
assert.equal(h.ids['source-chart'].children.length, 6, 'Every source remains visible');
assert.match(text(h.ids['source-chart']), /Reddit.*41.*GitHub.*40/);
assert.match(text(h.ids['community-heatmap']), /Positive/);
assert.match(text(h.ids['community-heatmap']), /GitHub — bug reports — not counted in main score/);
assert.doesNotMatch(text(h.ids['community-heatmap']), /Tiny|Rare/);

h.ids['source-filter'].value = 'reddit';
h.ids['source-filter'].events.change();
assert.equal(P.rowsForRange().length, 41, 'The page-local filter changes its source rows');
assert.match(text(h.ids['source-chart']), /Reddit.*41.*GitHub.*0/);
assert.doesNotMatch(text(h.ids['community-heatmap']), /GitHub — bug reports/);

h.ids['source-filter'].value = 'github';
h.ids['source-filter'].events.change();
assert.equal(P.rowsForRange().length, 40);
assert.match(text(h.ids['community-heatmap']), /GitHub — bug reports — not counted in main score/,
  'The GitHub bug-report row appears even without the community threshold');
assert.doesNotMatch(text(h.ids['community-heatmap']), /Positive/);

h.ids['source-filter'].value = 'hn';
h.ids['source-filter'].events.change();
assert.equal(P.rowsForRange().length, 0);
assert.match(text(h.ids['community-heatmap']), /Need a community/);

// Fair-score math remains covered using only Reddit, within the main-score allowlist.
const fairRows = [...batch('A', 'Acme', 20, 0), ...batch('B', 'Acme', 20, 0),
  ...batch('A', 'Other', 20, 0), ...batch('B', 'Other', 10, 10)];
const fair = harness(fairRows, {days: ['2026-09-27'], startDate: '2026-09-27', endDate: '2026-09-27'});
fair.run(['pulse.js', 'pulse-sources.js', 'pulse-community.js', 'pulse-trends.js',
  'pulse-trend-ui.js', 'pulse-rank.js', 'pulse-chart.js']);
const FP = fair.context.Pulse;
assert.equal(FP.chartModels.find(model => model.subject === 'A').stats.net, 100);
assert.equal(FP.chartModels.find(model => model.subject === 'B').stats.net, 50);
fair.ids['score-mode'].value = 'fair'; fair.ids['score-mode'].events.change();
assert.equal(FP.chartModels.find(model => model.subject === 'A').stats.net, 25);
assert.equal(FP.chartModels.find(model => model.subject === 'B').stats.net, -25);
console.log('Sources page, source filter, GitHub bug-report row and community heatmap checks passed.');
