// Regression coverage for the rolling 24-hour range and its ranking threshold.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {harness, text} = require('./ui_harness');
const scripts = ['pulse.js', 'pulse-sources.js', 'pulse-community.js', 'pulse-trends.js', 'pulse-trend-ui.js', 'pulse-rank.js', 'pulse-chart.js'];
const DAY = 86400000;
function row(id, subject, label, zone, created_utc) {
  return {id, subject, label, zone, kind: 'comment', created_utc, score: 1,
    text: `${subject} ${id}`, link: `https://reddit.com/${id}`,
    thread_url: `https://reddit.com/thread/${id}`, thread: `Thread ${id}`, thread_score: 1};
}
function click(h, id) { h.ids[id].events.click({preventDefault() {}}); }
function familyNames(section) {
  return section.children.filter(n => n.className === 'rank-model').map(n =>
    n.children[0].querySelector('.model-name').textContent);
}
function allFamilyNames(section) {
  return section.querySelectorAll('.rank-model').map(n =>
    n.children[0].querySelector('.model-name').textContent);
}
function zone(h, code) {
  return h.ids.zones.querySelectorAll('.zone-section').find(section =>
    section.children[0].textContent.toLowerCase().includes(({us: 'us frontier', tool: 'coding tools', open: 'china + open'})[code]));
}
function lowGroup(section) { return section.querySelector('.low-data'); }

function testRangeButtonLabel() {
  const page = fs.readFileSync(`${__dirname}/../pulse.html`, 'utf8');
  assert.match(page, /<button id="range-today"[^>]*>24h<\/button>/,
    'The one-day range button is labelled 24h');
}

function testRollingWindowAndHistoricalEnd() {
  const latest = Date.parse('2026-09-28T00:30:00Z');
  const start = latest - DAY;
  const historicalEnd = Date.parse('2026-09-26T23:45:00Z');
  const historicalStart = historicalEnd - DAY;
  const rows = [
    row('before-latest-start', 'Before', 'praise', 'us', start - 1),
    row('latest-start-edge', 'Start edge', 'praise', 'us', start),
    row('latest-middle-neutral', 'Neutral', 'no_opinion', 'us', '2026-09-27T12:00:00Z'),
    row('latest-end-edge', 'End edge', 'complaint', 'us', latest / 1000),
    row('after-selected-history', 'Later', 'praise', 'us', '2026-09-27T00:30:00Z'),
    row('before-history-start', 'Old', 'praise', 'us', historicalStart - 1),
    row('history-start-edge', 'Historical start', 'praise', 'us', historicalStart),
    row('history-end-edge', 'Historical end', 'praise', 'us', historicalEnd),
    row('latest-newest', 'Newest', 'praise', 'us', latest)
  ];
  const meta = {days: ['2026-09-25', '2026-09-26', '2026-09-27'],
    startDate: '2026-09-25', endDate: '2026-09-27', updatedAt: '2026-09-27T12:00:00Z'};
  const h = harness(rows, meta); h.run(scripts);
  const P = h.context.Pulse;

  assert.equal(P.timestampOf({created_utc: start}), start, 'Numeric millisecond timestamps are kept in milliseconds');
  assert.equal(P.timestampOf({created_utc: latest / 1000}), latest, 'Numeric second timestamps convert to milliseconds');
  click(h, 'range-today');
  assert.equal(P.rangeDays, 1);
  assert.match(h.ids['range-status'].textContent, /24h ending 2026-09-28T00:30:00\.000Z/,
    '24h ends at the newest item time, even when it is after the frozen wall clock and metadata date');
  assert.deepEqual(new Set(P.rowsForRange().map(item => item.id)),
    new Set(['latest-start-edge', 'latest-middle-neutral', 'latest-end-edge', 'after-selected-history', 'latest-newest']),
    'The exact start and end are inclusive, while an item one millisecond before the start is excluded across midnight');
  assert.equal(h.ids['range-opinions'].textContent, '4 opinions in this range',
    'The range count excludes neutral mentions');

  click(h, 'date-prev');
  assert.equal(h.ids['date-end'].value, '2026-09-26');
  assert.match(h.ids['range-status'].textContent, /24h ending 2026-09-26T23:45:00\.000Z/,
    'A historical date uses its newest item timestamp');
  assert.deepEqual(new Set(P.rowsForRange().map(item => item.id)),
    new Set(['history-start-edge', 'history-end-edge']), 'Historical start and end edges are inclusive');
  click(h, 'back-latest');
  assert.match(h.ids['range-status'].textContent, /24h ending 2026-09-28T00:30:00\.000Z/,
    'Back to latest restores the newest overall item timestamp');
}

function opinions(subject, count, zoneName, day) {
  const stamp = Date.parse(`${day}T12:00:00Z`);
  return Array.from({length: count}, (_, i) => row(`${subject}-${i}`, subject, 'praise', zoneName, stamp + i));
}
function thresholdHarness() {
  const rows = [
    ...opinions('Twenty', 20, 'us', '2026-09-27'),
    ...opinions('Nineteen', 19, 'us', '2026-09-27'),
    ...opinions('Eight', 8, 'us', '2026-09-27'),
    ...opinions('Seven', 7, 'us', '2026-09-27'),
    ...opinions('Old context', 10, 'us', '2026-09-25'),
    ...opinions('Tool below minimum', 7, 'tool', '2026-09-27'),
    ...opinions('Open below minimum', 3, 'open', '2026-09-27'),
    row('zero-opinion', 'Zero opinions', 'no_opinion', 'open', '2026-09-27T12:00:00Z')
  ];
  const meta = {days: ['2026-09-20', '2026-09-25', '2026-09-27', '2026-09-28'],
    startDate: '2026-09-20', endDate: '2026-09-28'};
  const h = harness(rows, meta); h.run(scripts);
  return h;
}

function testSevenAndThirtyDayThresholds(h) {
  const P = h.context.Pulse;
  assert.equal(P.rankingMinimum(), 20, 'Seven-day rankings keep the twenty-opinion minimum');
  assert.equal(h.ids['range-opinions'].textContent, '74 opinions in this range');
  assert.ok(familyNames(zone(h, 'us')).includes('Twenty'));
  assert.ok(!familyNames(zone(h, 'us')).includes('Nineteen'));
  assert.equal(lowGroup(zone(h, 'us')).open, false);
  assert.equal(lowGroup(zone(h, 'us')).children[0].textContent, 'Not enough data yet (4)');
  assert.match(text(lowGroup(zone(h, 'us'))), /Nineteen/);
  assert.equal(lowGroup(zone(h, 'tool')).children[0].textContent, 'Not enough data yet (1)');
  assert.match(text(lowGroup(zone(h, 'tool'))), /Tool below minimum/);
  assert.equal(lowGroup(zone(h, 'open')).children[0].textContent, 'Not enough data yet (2)');
  assert.match(text(lowGroup(zone(h, 'open'))), /Zero opinions/);
  click(h, 'range-30');
  assert.equal(P.rankingMinimum(), 20, 'Thirty-day rankings retain the twenty-opinion minimum');
  assert.equal(h.ids['range-opinions'].textContent, '74 opinions in this range');
  const us30d = zone(h, 'us');
  assert.ok(familyNames(us30d).includes('Twenty'));
  assert.ok(!familyNames(us30d).includes('Nineteen'));
  assert.equal(lowGroup(us30d).children[0].textContent, 'Not enough data yet (4)');
  assert.match(text(lowGroup(us30d)), /Nineteen/);
}

function test24HourThresholdAndChart(h) {
  const P = h.context.Pulse;
  click(h, 'range-7');
  const usSevenDayRows = allFamilyNames(zone(h, 'us'));
  click(h, 'range-today');
  assert.equal(P.rankingMinimum(), 8, 'The 24h chart keeps its eight-opinion minimum');
  assert.equal(h.ids['range-opinions'].textContent, '64 opinions in this range');
  const usToday = zone(h, 'us');
  assert.deepEqual(allFamilyNames(usToday), usSevenDayRows,
    '24h ranking retains the complete seven-day family row list and order');
  assert.deepEqual(familyNames(usToday), ['Twenty'], 'The ranked list keeps the 7d minimum');
  assert.equal(lowGroup(usToday).open, false);
  assert.equal(lowGroup(usToday).children[0].textContent, 'Not enough data yet (4)');
  assert.match(text(lowGroup(usToday)), /Eight/);
  assert.match(text(lowGroup(usToday)), /Seven/);
  const todayCell = usToday.querySelector('.rank-24h');
  assert.equal(todayCell.querySelector('.rank-24h-value').textContent, 'Score +100');
  assert.equal(todayCell.querySelector('.rank-24h-delta').textContent, '=0');
  const sparseCell = usToday.querySelectorAll('.rank-model').find(item =>
    item.querySelector('.model-name').textContent === 'Seven').querySelector('.rank-24h');
  assert.equal(sparseCell.querySelector('.rank-24h-value').textContent, '—');
  assert.equal(sparseCell.querySelector('.rank-24h-value').getAttribute('title'),
    'fewer than 8 opinions in 24h');
  assert.equal(lowGroup(zone(h, 'tool')).children[0].textContent, 'Not enough data yet (1)');
  assert.equal(lowGroup(zone(h, 'open')).children[0].textContent, 'Not enough data yet (2)');
  const points24h = h.ids.chart.querySelectorAll('.point').map(point => point.getAttribute('aria-label'));
  assert.ok(points24h.some(label => label.startsWith('Eight ·')), 'The 24h chart includes a family at the eight-opinion minimum');
  assert.ok(!points24h.some(label => label.startsWith('Seven ·')), 'The 24h chart excludes families below its axis minimum');
  const point = h.ids.chart.querySelectorAll('.point').find(item => item.getAttribute('aria-label').startsWith('Eight ·'));
  const pointX = Number(point.getAttribute('transform').match(/translate\((-?[\d.]+)/)[1]) + 12;
  assert.ok(pointX >= 64, 'The eight-opinion point stays on or inside the 24h chart minimum');
}

function testTodayUses24HourOrSevenDayFallback() {
  const rows = [
    ...opinions('Fresh', 12, 'us', '2026-09-27').map(item => ({...item, label: 'praise'})),
    ...opinions('Fresh', 8, 'us', '2026-09-25').map(item => ({...item, label: 'complaint'})),
    ...opinions('Deteriorating', 8, 'us', '2026-09-27').map(item => ({...item, label: 'complaint'})),
    ...opinions('Deteriorating', 12, 'us', '2026-09-25').map(item => ({...item, label: 'praise'})),
    ...opinions('Sparse tool', 7, 'tool', '2026-09-27').map(item => ({...item, label: 'praise'})),
    ...opinions('Sparse tool', 13, 'tool', '2026-09-25').map(item => ({...item, label: 'complaint'}))
  ];
  const h = harness(rows, {days: ['2026-09-25', '2026-09-27'],
    startDate: '2026-09-20', endDate: '2026-09-27'});
  h.run(scripts);
  click(h, 'range-today');
  const fresh = h.ids.zones.querySelectorAll('.rank-model').find(item =>
    item.querySelector('.model-name').textContent === 'Fresh').querySelector('.rank-24h');
  assert.equal(fresh.querySelector('.rank-24h-label').textContent, '24h');
  assert.equal(fresh.querySelector('.rank-24h-value').textContent, 'Score +100');
  assert.equal(fresh.querySelector('.rank-24h-delta').textContent, '▲80');
  const deteriorating = h.ids.zones.querySelectorAll('.rank-model').find(item =>
    item.querySelector('.model-name').textContent === 'Deteriorating').querySelector('.rank-24h');
  assert.equal(deteriorating.querySelector('.rank-24h-delta').textContent, '▼120');
  const cards = h.ids['use-today'].querySelectorAll('.use-card');
  assert.match(text(cards[0]), /Fresh/);
  assert.match(text(cards[0]), /12 people's opinions/);
  assert.match(text(cards[1]), /Sparse tool/);
  assert.match(text(cards[1]), /\(7d\)/, 'Use today labels its seven-day fallback');
  assert.equal(cards[1].querySelector('.use-net').textContent, '−30',
    'Use today shows the seven-day score when recent opinion count is below eight');
  assert.match(text(cards[1]), /20 people's opinions/);
}

function testFairScoreDoesNotInventDailyComparison() {
  const rows = opinions('Fair sparse', 8, 'us', '2026-09-27');
  const h = harness(rows, {days: ['2026-09-27'], startDate: '2026-09-27', endDate: '2026-09-27'});
  h.run(scripts);
  h.context.Pulse.scoreMode = 'fair';
  h.context.Pulse.render();
  click(h, 'range-today');
  const cell = h.ids.zones.querySelector('.rank-24h');
  assert.equal(cell.querySelector('.rank-24h-value').textContent, 'Fair score unavailable');
  assert.equal(cell.querySelector('.rank-24h-delta'), null,
    'A fair score with no qualifying community baseline has no fabricated delta');
}

testRangeButtonLabel();
testRollingWindowAndHistoricalEnd();
const h = thresholdHarness();
testSevenAndThirtyDayThresholds(h);
test24HourThresholdAndChart(h);
testTodayUses24HourOrSevenDayFallback();
testFairScoreDoesNotInventDailyComparison();
console.log('24h range and ranking regression checks passed.');
