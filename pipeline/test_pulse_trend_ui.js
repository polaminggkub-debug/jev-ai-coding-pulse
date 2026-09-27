// Exercise shipped trend rendering, ranking arrows, and date/range controls offline.
const assert = require('node:assert/strict');
const {harness, text} = require('./ui_harness');
const scripts = ['pulse.js', 'pulse-trends.js', 'pulse-trend-ui.js', 'pulse-rank.js', 'pulse-chart.js'];
function comments(subject, count, label, day, extra = {}) {
  return Array.from({length: count}, (_, i) => ({subject, kind: 'comment', label, zone: 'us',
    created_utc: `${day}T12:00:00Z`, score: i, link: `https://reddit.com/${subject}/${day}/${i}`,
    text: `${subject} comment ${i}`, ...extra}));
}
const rows = [
  ...comments('Sour', 20, 'praise', '2026-09-20', {version: 'v1'}),
  ...comments('Sour', 20, 'complaint', '2026-09-27', {version: 'v1'}),
  ...comments('Warm', 20, 'mixed', '2026-09-20'),
  ...comments('Warm', 20, 'praise', '2026-09-27'),
  ...comments('New', 15, 'mixed', '2026-09-27')];
const meta = {days: ['2026-09-20', '2026-09-27'], startDate: '2026-09-20', endDate: '2026-09-27'};
const h = harness(rows, meta);
h.run(scripts);
function click(id) { h.ids[id].events.click({preventDefault() {}}); }
function familyRow(name) {
  return h.ids.zones.querySelectorAll('.rank-model').find(row =>
    row.children[0].querySelector('.model-name').textContent === name);
}
function checkAlerts() {
  assert.equal(h.context.Pulse.rangeDays, 7, 'Ranking still defaults to seven days');
  assert.equal(h.ids['range-7'].getAttribute('aria-pressed'), 'true');
  const alerts = h.ids['trend-alerts'].querySelectorAll('.trend-alert');
  assert.equal(alerts.length, 4);
  assert.equal(alerts[0].querySelector('.trend-message').textContent,
    '⚠️ Going sour: Sour — score +100 → −100 in the last 2 days (20 opinions)');
  assert.ok(alerts[0].className.includes('trend-drop'));
  assert.equal(alerts[0].querySelector('.trend-quote').href, 'https://reddit.com/Sour/2026-09-27/19');
  assert.equal(alerts[2].querySelector('.trend-message').textContent,
    '📈 Heating up: Warm — +0 → +100 in the last 2 days (20 opinions)');
  assert.ok(alerts[2].className.includes('trend-rise'));
  assert.equal(alerts[2].querySelector('.trend-quote').href, 'https://reddit.com/Warm/2026-09-27/19');
  assert.equal(alerts[3].querySelector('.trend-message').textContent, '🆕 Suddenly talked about: New');
  assert.equal(familyRow('Sour').children[0].querySelector('.trend-arrow').textContent, '▼200');
  assert.equal(familyRow('Warm').children[0].querySelector('.trend-arrow').textContent, '▲100');
  assert.equal(familyRow('Sour').querySelector('.version-row').querySelector('.trend-arrow').textContent, '▼200');
  assert.equal(familyRow('New').querySelector('.trend-arrow'), null, 'New names do not imply a score trend');
}
function checkDateAndRange() {
  const original = text(h.ids['trend-alerts']);
  click('range-today');
  assert.equal(text(h.ids['trend-alerts']), original, 'Trend windows do not follow ranking range');
  click('range-30');
  assert.equal(text(h.ids['trend-alerts']), original);
  click('date-prev');
  assert.ok(!text(h.ids['trend-alerts']).includes('Going sour'), 'End-date change recomputes alerts');
  assert.equal(h.ids.zones.querySelectorAll('.trend-arrow').length, 0, 'No stale arrows');
  click('back-latest'); click('range-7');
  assert.equal(text(h.ids['trend-alerts']), original);
}
function checkCapAndEmpty() {
  const many = Array.from({length: 6}, (_, i) => [
    ...comments(`Model ${i}`, 20, 'praise', '2026-09-20'),
    ...comments(`Model ${i}`, 20, 'complaint', '2026-09-27')]).flat();
  const capped = harness(many, meta); capped.run(scripts);
  assert.equal(capped.ids['trend-alerts'].querySelectorAll('.trend-alert').length, 5);
  assert.equal(capped.ids.zones.querySelectorAll('.trend-arrow').length, 6,
    'Ranking arrows include qualifying changes beyond the five visible alerts');
  const empty = harness([], {}); empty.run(scripts);
  assert.equal(empty.ids['trend-alerts'].querySelector('.trend-empty').textContent,
    'No big mood swings in the last 2 days.');
}
checkAlerts(); checkDateAndRange(); checkCapAndEmpty();
console.log('Pulse trend UI interaction checks passed.');
