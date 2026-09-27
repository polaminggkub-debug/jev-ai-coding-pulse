// Pure, offline trend-window checks with independently chosen opinion counts.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(__dirname + '/pulse-trends.js', 'utf8'), context);
const trends = rows => context.Pulse.trendsFor(rows, '2026-09-27');
function opinions(count, label, created_utc, extra = {}) {
  return Array.from({length: count}, (_, i) => ({subject: 'Model', kind: 'comment',
    label, created_utc, score: i, text: `Comment ${i}`, link: `https://reddit.com/${i}`, ...extra}));
}
const now = '2026-09-27T12:00:00Z', before = '2026-09-23T12:00:00Z';
function checkDirection() {
  const baseline = [...opinions(10, 'praise', before), ...opinions(10, 'complaint', before)];
  const rise = trends([...baseline, ...opinions(9, 'praise', now), ...opinions(6, 'complaint', now)])[0];
  assert.equal(rise.kind, 'rise'); assert.equal(rise.delta, 20);
  assert.equal(rise.now.opinions, 15); assert.equal(rise.before.opinions, 20);
  assert.equal(rise.quote.label, 'praise'); assert.equal(rise.quote.score, 8);
  const drop = trends([...baseline, ...opinions(6, 'praise', now), ...opinions(9, 'complaint', now),
    ...opinions(1, 'complaint', before, {score: 999, kind: 'post'})])[0];
  assert.equal(drop.kind, 'drop'); assert.equal(drop.delta, -20);
  assert.equal(drop.quote.label, 'complaint'); assert.equal(drop.quote.score, 8);
}
function checkThresholds() {
  assert.equal(trends([...opinions(20, 'praise', before), ...opinions(14, 'complaint', now),
    ...opinions(100, 'no_opinion', now)]).length, 0, 'Neutral mentions cannot reach 15 opinions');
  assert.equal(trends([...opinions(19, 'praise', before), ...opinions(15, 'complaint', now)]).length, 0);
  const exact = trends([...opinions(10, 'praise', before), ...opinions(10, 'mixed', before),
    ...opinions(7, 'praise', now), ...opinions(13, 'mixed', now)])[0];
  assert.equal(exact.delta, -15, 'Exactly 15 points fires');
  assert.equal(trends([...opinions(10, 'praise', before), ...opinions(10, 'mixed', before),
    ...opinions(8, 'praise', now), ...opinions(12, 'mixed', now)]).length, 0);
  const fresh = trends([...opinions(4, 'praise', before), ...opinions(15, 'mixed', now)])[0];
  assert.equal(fresh.kind, 'new'); assert.equal(fresh.delta, null);
  assert.equal(trends([...opinions(5, 'praise', before), ...opinions(15, 'mixed', now)]).length, 0);
}
function checkWindows() {
  const rows = [...opinions(20, 'praise', '2026-09-19T00:00:00Z'),
    ...opinions(15, 'complaint', '2026-09-26T00:00:00Z'),
    ...opinions(1, 'praise', '2026-09-25T23:59:59.999Z'),
    ...opinions(50, 'mixed', '2026-09-18T23:59:59.999Z'),
    ...opinions(50, 'mixed', '2026-09-28T00:00:00Z'),
    ...opinions(50, 'mixed', 'invalid', {date: '2026-09-27'})];
  const alert = trends(rows)[0];
  assert.equal(alert.now.opinions, 15); assert.equal(alert.before.opinions, 21);
  assert.equal(alert.delta, -200);
  const stamp = Date.parse('2026-09-26T00:00:00Z');
  for (const value of [stamp, stamp / 1000, String(stamp / 1000), '2026-09-26T07:00:00+07:00']) {
    assert.equal(context.Pulse.trendTimestamp(value), stamp);
  }
  assert.equal(context.Pulse.trendTimestamp('2026-02-30T00:00:00Z'), null);
  assert.equal(context.Pulse.trendsFor(rows, 'invalid').length, 0);
}
function checkVersionsAndPurity() {
  const rows = [...opinions(20, 'praise', before, {version: 'v1'}),
    ...opinions(15, 'complaint', now, {version: 'v1'}),
    ...opinions(20, 'mixed', before, {subject: 'Gentler'}),
    ...opinions(15, 'praise', now, {subject: 'Gentler'}),
    ...opinions(15, 'praise', now, {subject: 'New model'})];
  const original = JSON.stringify(rows);
  rows.forEach(Object.freeze); Object.freeze(rows);
  const alerts = trends(rows);
  assert.equal(alerts.length, 4);
  assert.equal(alerts[0].delta, -200); assert.equal(alerts[1].delta, -200);
  assert.ok(alerts.some(item => item.subject === 'Model' && item.version === 'v1'));
  assert.ok(alerts.some(item => item.subject === 'Model' && item.version === null));
  assert.equal(alerts[2].subject, 'Gentler'); assert.equal(alerts[3].kind, 'new');
  assert.equal(JSON.stringify(rows), original, 'Calculation does not mutate its inputs');
}
checkDirection(); checkThresholds(); checkWindows(); checkVersionsAndPurity();
console.log('Pulse trend window checks passed.');
