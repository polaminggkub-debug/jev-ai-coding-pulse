// Exercise rolling-window arithmetic, month summaries, and controls without a browser or network.
const assert = require('node:assert/strict');
const {Element, harness, text} = require('./ui_harness');
let sequence = 0;
const scripts = ['pulse.js', 'pulse-trends.js', 'pulse-trend-ui.js', 'pulse-rank.js', 'pulse-chart.js',
  'pulse-timeline-core.js', 'pulse-timeline.js'];
function row(subject, label, day, extra = {}) {
  return {id: `${subject}-${label}-${day}-${sequence++}`, kind: 'comment', subject, label, zone: 'us',
    created_utc: `${day}T12:00:00Z`, judged_at: '2026-09-28T12:00:00Z', date: '2026-09-28', ...extra};
}
function repeated(subject, label, day, count, extra = {}) {
  return Array.from({length: count}, (_, index) => row(subject, label, day, {...extra, id: `${subject}-${day}-${label}-${index}`}));
}
function pureHarness(rows = []) {
  const h = harness(rows, {days: ['2026-08-10', '2026-09-28'], startDate: '2026-08-10', endDate: '2026-09-28'});
  h.run(scripts.slice(0, -1));
  return h.context.Pulse;
}
function checkCommentDateAndWindowMath() {
  const P = pureHarness();
  const old = {subject: 'Written earlier', label: 'praise', created_utc: '2026-09-08T12:00:00Z',
    judged_at: '2026-09-28T12:00:00Z', date: '2026-09-28'};
  assert.equal(P.timelineDateOf(old), '2026-09-08', 'Comment time wins over today’s judged date');
  assert.equal(P.timelineDateOf({parent_created_utc: '2026-08-09T12:00:00Z', judged_at: '2026-09-28'}), '2026-08-09');
  assert.equal(P.timelineDateOf({post_created_utc: '2026-08-10T12:00:00Z', judged_at: '2026-09-28'}), '2026-08-10');
  const qwen = [...repeated('Qwen', 'praise', '2026-09-20', 5),
    ...repeated('Qwen', 'praise', '2026-09-21', 2), ...repeated('Qwen', 'praise', '2026-09-23', 2),
    ...repeated('Qwen', 'mixed', '2026-09-25', 2), ...repeated('Qwen', 'complaint', '2026-09-27', 2),
    ...repeated('Qwen', 'complaint', '2026-09-28', 1)].map(item => ({row: item, day: P.timelineDateOf(item)}));
  const stat = P.timelineWindow(qwen, 'Qwen', '2026-09-27');
  assert.deepEqual({...stat}, {praise: 4, mixed: 2, complaint: 2, opinions: 8, net: 25},
    'The inclusive seven-day window excludes Sep 20 and Sep 28; mixed opinions remain in the denominator');
  assert.deepEqual({...P.timelineRange('2026-09-28', '30', '2026-09')},
    {start: '2026-08-30', end: '2026-09-28', month: '2026-09', mode: '30'});
  assert.deepEqual({...P.timelineMonthBounds('2026-12')}, {start: '2026-12-01', end: '2026-12-31'});
  assert.deepEqual({...P.timelineMonthBounds('2028-02')}, {start: '2028-02-01', end: '2028-02-29'});
  assert.equal(P.timelineDates('2026-08-30', '2026-09-28').length, 30);
}
function checkMoverThresholdAndDashes() {
  const P = pureHarness();
  const movers = [...repeated('Qwen', 'complaint', '2026-09-24', 15),
    ...repeated('Qwen', 'praise', '2026-09-27', 15)].map(item => ({row: item, day: P.timelineDateOf(item)}));
  const model = P.timelineAllModels(movers, {start: '2026-09-01', end: '2026-09-30'});
  assert.equal(P.timelineCaption(movers, model, '2026-09-27'), '📈 Qwen heating up (+100 in 3 days)');
  const tooFew = [...repeated('Qwen', 'complaint', '2026-09-24', 14),
    ...repeated('Qwen', 'praise', '2026-09-27', 15)].map(item => ({row: item, day: P.timelineDateOf(item)}));
  assert.equal(P.timelineCaption(tooFew, P.timelineAllModels(tooFew, {start: '2026-09-01', end: '2026-09-30'}), '2026-09-27'),
    'No family moved 15+ points over the last 3 days.', 'The prior window needs at least 15 opinions');
  const series = {points: [{opinions: 10, net: 50}, {opinions: 10, net: 25}, {opinions: 2, net: -50}]};
  const paths = P.timelinePath(series, ['2026-09-01', '2026-09-02', '2026-09-03'], 760, 330);
  assert.ok(paths.solid.startsWith('M42.0') && paths.solid.includes('L377.0'));
  assert.ok(paths.dashed.includes('M377.0') && paths.dashed.includes('L712.0'), 'Only the low-data edge is dashed');
  const isolated = P.timelinePath({points: [{opinions: 1, net: 20}, {opinions: 0, net: 0}]},
    ['2026-09-01', '2026-09-02'], 760, 330);
  assert.equal(isolated.lone.low, true);
}
function checkMonthSummariesAndAllFamilies() {
  const rows = [
    ...repeated('US good', 'praise', '2026-09-12', 20, {zone: 'us'}),
    ...repeated('US bad', 'complaint', '2026-09-12', 20, {zone: 'us'}),
    ...repeated('Tool', 'praise', '2026-09-12', 20, {zone: 'tool'}),
    ...repeated('Open', 'praise', '2026-09-12', 20, {zone: 'open'}),
    ...repeated('Riser', 'complaint', '2026-09-03', 8, {zone: 'tool'}),
    ...repeated('Riser', 'praise', '2026-09-28', 8, {zone: 'tool'}),
    ...repeated('Faller', 'praise', '2026-09-03', 8, {zone: 'open'}),
    ...repeated('Faller', 'complaint', '2026-09-28', 8, {zone: 'open'})];
  for (let index = 0; index < 3; index++) rows.push(row(`Discussed ${index}`, 'no_opinion', '2026-09-15', {
    id: `busy-${index}`, thread_url: 'https://reddit.test/busy', thread: 'Busy thread', sub: 'models'}));
  for (let index = 0; index < 2; index++) rows.push(row(`Discussed other ${index}`, 'no_opinion', '2026-09-15', {
    id: `quiet-${index}`, thread_url: 'https://reddit.test/quiet', thread: 'Quiet thread', sub: 'models'}));
  const P = pureHarness(rows), items = P.timelineRows(rows);
  const insight = P.timelineInsights(items, '2026-09');
  assert.equal(insight.zoneBest.find(item => item.zone === 'us').model.subject, 'US good');
  assert.equal(insight.zoneBest.find(item => item.zone === 'tool').model.subject, 'Tool');
  assert.equal(insight.zoneBest.find(item => item.zone === 'open').model.subject, 'Open');
  assert.equal(insight.mostDisliked.subject, 'US bad');
  assert.equal(insight.riser.subject, 'Riser'); assert.equal(insight.riser.delta, 200);
  assert.equal(insight.faller.subject, 'Faller'); assert.equal(insight.faller.delta, -200);
  assert.equal(insight.threads[0].thread, 'Busy thread'); assert.equal(insight.threads[0].count, 3);
  const many = Array.from({length: 13}, (_, index) => repeated(`Family ${index}`, 'praise', '2026-09-20', 20)).flat();
  const manyItems = P.timelineRows(many), range = {start: '2026-09-01', end: '2026-09-30'};
  assert.equal(P.timelineAllModels(manyItems, range).length, 13);
  assert.equal(P.timelineModels(manyItems, range).length, 12, 'Only race bars use the top-12 cap');
}
function uiRows() {
  const families = Array.from({length: 13}, (_, index) => repeated(`Family ${index}`, 'praise', '2026-09-27', 20));
  return [...families.flat(), row('Neutral archive', 'no_opinion', '2026-08-10', {
    id: 'aug-neutral', thread_url: 'https://reddit.test/archive', thread: 'August discussion', sub: 'models'}),
  row('Neutral current', 'no_opinion', '2026-09-28', {id: 'sep-neutral'})];
}
function checkActualControlsAndEmptyState() {
  const h = harness(uiRows(), {days: ['2026-08-10', '2026-09-28'], startDate: '2026-08-10', endDate: '2026-09-28'});
  h.ids.timeline = new Element('section');
  const timers = new Map(); let serial = 0;
  h.context.setInterval = (fn, delay) => { const id = ++serial; timers.set(id, {fn, delay}); return id; };
  h.context.clearInterval = id => timers.delete(id);
  h.context.matchMedia = () => ({matches: true}); h.run(scripts);
  const P = h.context.Pulse, state = P.timelineState;
  assert.equal(state.latest, '2026-09-28', 'Neutral-only latest days remain in the date range');
  assert.deepEqual([...state.months], ['2026-08', '2026-09'], 'Neutral-only months appear in the selector');
  assert.equal(state.dates.length, 30); assert.equal(state.models.length, 12); assert.equal(state.allModels.length, 13);
  assert.ok(h.ids.timeline.className.includes('timeline-reduced-motion'));
  assert.equal(h.ids.timeline.querySelectorAll('.timeline-row').length, 12);
  const scrubber = h.document.getElementById('timeline-scrubber');
  scrubber.value = '0'; scrubber.events.input();
  assert.equal(state.refs.date.textContent, '30 Aug 2026');
  assert.equal(h.ids.timeline.querySelectorAll('.timeline-empty').length, 12, 'No-opinion windows show dashes, not zero bars');
  const mode = h.document.getElementById('timeline-range'), month = h.document.getElementById('timeline-month');
  month.value = '2026-08'; month.events.change();
  assert.equal(state.mode, 'month', 'Choosing a month switches the timeline to that whole month');
  assert.equal(mode.value, 'month'); assert.equal(state.dates.length, 31);
  assert.equal(state.range.start, '2026-08-01'); assert.equal(state.range.end, '2026-08-31');
  assert.match(text(state.refs.insights), /August discussion/);
  month.value = '2026-09'; month.events.change();
  assert.equal(state.dates.length, 30); assert.equal(state.range.end, '2026-09-30');
  const series = h.ids.timeline.querySelectorAll('.timeline-series');
  assert.equal(series.length, 13, 'The score chart and legend include every family');
  const legend = state.refs.lines.querySelectorAll('.timeline-legend-item');
  assert.equal(legend.length, 13);
  legend[0].events.click();
  assert.equal(state.isolated, 'Family 0');
  assert.ok(state.refs.lines.querySelectorAll('.timeline-series').some(node => node.className.includes('timeline-muted')));
  mode.value = '30'; mode.events.change(); assert.equal(state.dates.length, 30);
  state.refs.play.events.click();
  assert.equal(state.index, 0); assert.equal(state.refs.date.textContent, '30 Aug 2026');
  assert.equal([...timers.values()][0].delay, 800);
  [...timers.values()][0].fn(); assert.equal(state.index, 1);
  state.refs.speed2.events.click(); assert.equal([...timers.values()][0].delay, 400);
  state.refs.play.events.click(); assert.equal(timers.size, 0); assert.equal(state.refs.play.textContent, '▶ Play');
  const empty = harness([], {}); empty.ids.timeline = new Element('section'); empty.run(scripts);
  assert.equal(empty.context.Pulse.timelineState.models.length, 0);
  assert.match(text(empty.ids.timeline), /No opinions in this period/);
}
checkCommentDateAndWindowMath();
checkMoverThresholdAndDashes();
checkMonthSummariesAndAllFamilies();
checkActualControlsAndEmptyState();
console.log('Pulse timeline interaction and window checks passed.');
