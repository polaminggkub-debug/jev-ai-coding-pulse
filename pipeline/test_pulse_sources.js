// Exercise shipped source controls, community thresholds and independent fair math.
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
const h = harness(rows, {});
h.run(['pulse.js', 'pulse-sources.js', 'pulse-community.js', 'pulse-trends.js',
  'pulse-trend-ui.js', 'pulse-rank.js', 'pulse-chart.js']);
const P = h.context.Pulse;
assert.equal(h.ids['source-chart'].children.length, 6);
assert.match(text(h.ids['source-chart']), /Reddit.*41.*GitHub.*40/);
assert.match(text(h.ids['community-heatmap']), /Positive/);
assert.match(text(h.ids['community-heatmap']), /Negative/);
assert.doesNotMatch(text(h.ids['community-heatmap']), /Tiny|Rare/);
assert.match(text(h.ids['community-heatmap']), /vs avg \+25/);
assert.match(text(h.ids['community-heatmap']), /loves.*A.*hates.*B/);
assert.equal(P.chartModels.find(m => m.subject === 'A').stats.net, 25);
assert.equal(P.chartModels.find(m => m.subject === 'B').stats.net, -25);
h.ids['score-mode'].value = 'fair'; h.ids['score-mode'].events.change();
assert.equal(P.chartModels.find(m => m.subject === 'A').stats.net, 25);
assert.equal(P.chartModels.find(m => m.subject === 'B').stats.net, -25);
assert.match(h.ids.chart.innerHTML, /Fair score/);
assert.match(text(h.ids.zones), /Fair score unavailable/);
h.ids['source-filter'].value = 'reddit'; h.ids['source-filter'].events.change();
assert.equal(P.rowsForRange().length, 41);
// Positive community baseline is +75; A is +100, hence Fair +25, not raw +100.
assert.equal(P.chartModels.find(m => m.subject === 'A').stats.net, 25);
assert.equal(P.chartModels.find(m => m.subject === 'B').stats.net, -25);
assert.doesNotMatch(text(h.ids['community-heatmap']), /Negative/);
assert.ok(h.ids.zones.querySelectorAll('.source-icon').length > 0);
assert.equal(h.ids.zones.querySelector('.source-icon').getAttribute('aria-label'), 'Reddit');
h.ids['score-mode'].value = 'raw'; h.ids['score-mode'].events.change();
assert.equal(P.chartModels.find(m => m.subject === 'A').stats.net, 100);
h.ids['source-filter'].value = 'hn'; h.ids['source-filter'].events.change();
assert.equal(P.rowsForRange().length, 0);
assert.equal(h.ids.chart.querySelectorAll('.point').length, 0);
assert.doesNotMatch(h.ids.chart.innerHTML, /NaN|Infinity/);
console.log('Source filters, Fair scores and community heatmap checks passed.');
