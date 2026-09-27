// Behavioral acceptance for TASK3, using the shipped scripts and no network.
const assert = require('node:assert/strict');
const {harness, walk, text} = require('./ui_harness');
const fixture = (subject, label, version, score, day = '2026-09-27', zone = 'us') => ({
  subject, label, version, score, kind: 'comment', zone, text: `Quote ${score}`,
  link: 'https://reddit.com/comment', thread_url: 'https://reddit.com/thread',
  thread_score: 10, sub: 'Coding', thread: 'Thread', created_utc: `${day}T12:00:00Z`});
function repeated(subject, count, label, day = '2026-09-27', zone = 'us') {
  return Array.from({length: count}, (_, i) => fixture(subject, label, null, i, day, zone));
}
const rows = [
  ...Array.from({length: 20}, (_, i) => fixture('Claude Opus',
    i < 12 ? 'praise' : i < 16 ? 'mixed' : 'complaint', i < 10 ? 'Opus 5.5' : i < 11 ? 'Opus 4' : null, i)),
  ...repeated('Gemini', 20, 'mixed'), ...repeated('Grok', 40, 'complaint'),
  ...repeated('Rare', 19, 'praise'), ...repeated('Rare', 100, 'no_opinion'),
  ...repeated('Codex', 20, 'praise', '2026-09-27', 'tool'),
  ...repeated('Qwen', 1, 'praise', '2026-09-27', 'open'),
  ...repeated('Old champion', 20, 'praise', '2026-09-20'),
  fixture('Claude Opus', 'complaint', 'Opus 4', 900, '2026-09-25'),
  ...Array.from({length: 8}, (_, i) => fixture(`Small ${i}`, 'no_opinion', null, i))];
const meta = {days: ['2026-09-20', '2026-09-25', '2026-09-27'],
  startDate: '2026-09-20', endDate: '2026-09-27', updatedAt: '2026-09-27T12:00:00Z'};
const {ids, document, context, run} = harness(rows, meta, {claude: '<svg viewBox="0 0 24 24"><path/></svg>'});
run(['pulse.js', 'pulse-rank.js', 'pulse-chart.js']);
function click(id) { ids[id].events.click({preventDefault() {}}); }
function models() { return document.querySelectorAll('.rank-model'); }
function checkInitial() {
  assert.equal(ids['range-7']['aria-pressed'], 'true');
  assert.match(text(ids['covered-period']), /27 Sep 2026/);
  assert.match(text(ids['covered-period']), /updated.*27 Sep.*12:00.*UTC/);
  assert.match(text(ids['use-today']), /Claude Opus/);
  assert.match(text(ids['use-today']), /mostly Opus 5.5/);
  assert.match(text(ids['use-today']), /runner-up: Gemini \+0/);
  assert.match(text(ids['use-today']), /Not enough talk yet/);
  assert.match(text(ids['use-today']), /Quote 11/);
  assert.equal(ids.chips.children.length, 10, 'Only ten family chips');
  assert.ok(!text(ids.chips).includes('Opus 5.5'), 'Versions are not chips');
  assert.ok(models().every(d => !d.open), 'Models start collapsed');
  assert.match(text(ids.zones), /Not enough data/);
  assert.match(text(ids.zones), /other/i, 'Rare versions folded into other');
  assert.ok(!text(ids.zones).includes('Old champion'), 'Seven-day cutoff');
  for (const label of ['Loved & hot', 'Loved, quiet', 'Hot but hated', 'Ignore']) {
    assert.ok(text(ids.chart).includes(label), label);
  }
}
function checkRankingMath() {
  const us = ids.zones.children[0];
  const ranked = us.children.filter(n => n.className === 'rank-model');
  assert.match(text(ranked[0]), /Claude Opus/);
  assert.match(text(ranked[1]), /Gemini/);
  assert.match(text(ranked[2]), /Grok/);
  assert.ok(!ranked.some(n => text(n).includes('Rare')), 'Neutral mentions do not satisfy threshold');
  const bar = walk(ranked[0]).find(n => n.className === 'diverging');
  assert.equal(Number.parseFloat(bar.children[0].style.width), 50 * 5 / 21);
  assert.equal(Number.parseFloat(bar.children[1].style.width), 50 * 12 / 21);
  assert.equal(bar.children.length, 2, 'Mixed is excluded from diverging graphic');
  const versions = context.Pulse.versionRows(rows.filter(r => r.subject === 'Claude Opus'));
  assert.ok(!versions.some(v => v.name === 'Opus 4'), 'Two mentions must fold into Other');
  assert.equal(versions.find(v => v.name === 'Other').mentions, 11);
  assert.equal(context.Pulse.stats(rows.filter(r => r.subject === 'Rare')).opinions, 19);
  const low = us.children.find(n => n.className === 'low-data');
  assert.equal(low.open, false, 'Low-data group starts collapsed');
}
function checkChart() {
  const points = ids.chart.querySelectorAll('.point');
  assert.equal(points.length, 4, 'Only rankable models are plotted');
  assert.deepEqual(ids.chart.querySelectorAll('.point-label').map(n => text(n).trim()), ['Opus', 'Gemini', 'Grok', 'Codex']);
  assert.ok(!/NaN|Infinity/.test(ids.chart.innerHTML));
  const point = points.find(n => n['aria-label'].startsWith('Claude Opus'));
  const [x, y] = point.transform.match(/[-\d.]+/g).map(Number);
  assert.ok(Math.abs(x - (64 + Math.log(21 / 20) / Math.log(2) * 668 - 12)) < 1e-8);
  assert.ok(Math.abs(y - (52 + (100 - 100 / 3) / 200 * 304 - 12)) < 1e-8);
  point.events.click();
  assert.match(text(document.getElementById('chart-tip')), /Claude Opus.*Net \+33.*21 opinions/);
  assert.ok(points.every(n => n.tabindex === '0'), 'Keyboard-focusable points');
  const svg = walk(point).find(n => n.tag === 'svg');
  assert.equal(svg.width, '24'); assert.equal(svg.height, '24');
}
function checkPeriods() {
  click('range-today');
  assert.match(text(ids['use-today']), /\+40/);
  assert.match(text(ids['use-today']), /20 opinions/);
  click('date-prev');
  assert.equal(ids['date-end'].value, '2026-09-25', 'Skip missing 26 Sep');
  assert.match(text(ids['covered-period']), /25 Sep/);
  assert.match(text(ids['use-today']), /Not enough talk yet/);
  assert.ok(!/NaN|Infinity/.test(ids.chart.innerHTML), 'Empty plot has valid geometry');
  assert.ok(!text(ids.zones).includes('Grok'), 'Rankings follow past date');
  click('date-prev');
  assert.equal(ids['date-end'].value, '2026-09-20');
  assert.match(text(ids['use-today']), /Old champion/);
  assert.equal(ids['date-prev'].disabled, true);
  click('back-latest');
  assert.equal(ids['date-end'].value, '2026-09-27');
  assert.equal(ids['date-next'].disabled, true);
  click('range-30');
  assert.match(text(ids['use-today']), /Old champion/);
  click('range-7');
  const missing = ids['date-end'].children.find(n => n.value === '2026-09-26');
  assert.ok(missing?.disabled, 'No-data dates are disabled');
}
function checkSearchAndDetails() {
  ids.search.value = 'opus 5.5'; ids.search.events.input();
  assert.equal(models().length, 1, 'Version search finds owning family');
  assert.match(text(ids.zones), /Claude Opus/);
  ids.chips.children.find(n => text(n).includes('Codex')).events.click();
  assert.equal(ids.search.value, '', 'Chip selection clears the search filter');
  assert.equal(models().length, 1);
  assert.match(text(ids.zones), /Codex/);
  ids.search.value = 'nothing matches'; ids.search.events.input();
  assert.match(text(ids.zones), /No matching models/);
  ids.search.value = ''; ids.search.events.input();
  ids.expand.checked = true; ids.expand.events.change();
  assert.ok(models().every(d => d.open));
  ids.expand.checked = false; ids.expand.events.change();
  assert.ok(models().every(d => !d.open));
  click('theme'); assert.equal(document.documentElement.dataset.theme, 'dark');
  click('theme'); assert.equal(document.documentElement.dataset.theme, 'light');
}
checkInitial();
checkRankingMath();
checkChart();
checkPeriods();
checkSearchAndDetails();
ids.chart.clientWidth = 280;
context.getComputedStyle = () => ({paddingLeft: '12px', paddingRight: '12px'});
context.Pulse.renderChart(context.Pulse.chartModels);
assert.match(ids.chart.innerHTML, /viewBox="0 0 256 320"/, 'Phone chart uses content width');
assert.match(ids.chart.innerHTML, /width="24" height="24"/, 'Phone chart preserves logo dimensions');
const claudeLabels = harness([
  ...repeated('Claude Opus', 20, 'praise'), ...repeated('Claude Haiku', 20, 'praise'),
  ...repeated('Claude Code', 20, 'praise', '2026-09-27', 'tool')], meta);
claudeLabels.run(['pulse.js', 'pulse-rank.js', 'pulse-chart.js']);
const labels = claudeLabels.ids.chart.querySelectorAll('.point-label');
assert.deepEqual(labels.map(n => text(n).trim()), ['Opus', 'Haiku', 'Code'], 'Shared Claude logos have distinct short labels');
assert.equal(new Set(labels.map(n => `${n.x}/${n.y}/${n['text-anchor']}`)).size, 3,
  'Coincident points use different label positions');
const empty = harness([], {});
empty.run(['pulse.js', 'pulse-rank.js', 'pulse-chart.js']);
assert.match(text(empty.ids['use-today']), /Not enough talk yet/);
assert.equal(empty.ids['date-prev'].disabled, true);
assert.equal(empty.ids['date-next'].disabled, true);
assert.ok(!/NaN|Infinity/.test(empty.ids.chart.innerHTML));
console.log('Pulse UI offline interaction checks passed.');
