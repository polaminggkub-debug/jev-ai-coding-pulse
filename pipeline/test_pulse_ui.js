// Behavioral acceptance for TASK3, using the shipped scripts and no network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
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
run(['pulse.js', 'pulse-trends.js', 'pulse-trend-ui.js', 'pulse-rank.js', 'pulse-chart.js']);
function click(id) { ids[id].events.click({preventDefault() {}}); }
function models() { return document.querySelectorAll('.rank-model'); }
function assertBar(bar, counts, total) {
  assert.equal(bar.getAttribute('role'), 'img');
  assert.deepEqual(bar.children.map(node => node.className),
    ['opinion-liked', 'opinion-mixed', 'opinion-disliked']);
  const widths = bar.children.map(node => Number.parseFloat(node.style.width));
  counts.forEach((count, index) => assert.ok(Math.abs(widths[index] - count * 100 / total) < 1e-8));
  assert.ok(Math.abs(widths.reduce((sum, width) => sum + width, 0) - 100) < 1e-8);
}
function checkInitial() {
  assert.equal(ids['range-7']['aria-pressed'], 'true');
  assert.match(text(ids['covered-period']), /27 Sep 2026/);
  assert.match(text(ids['update-info']), /Updated 27 Sep 19:00 \(Thai time\)/);
  assert.match(text(ids['use-today']), /Claude Opus/);
  assert.match(text(ids['use-today']), /mostly Opus 5.5/);
  assert.match(text(ids['use-today']), /runner-up: Gemini Score \+0/);
  assert.match(text(ids['use-today']), /Not enough talk yet/);
  assert.match(text(ids['use-today']), /Quote 11/);
  assert.equal(ids.chips.children.length, 10, 'Only ten family chips');
  assert.ok(!text(ids.chips).includes('Opus 5.5'), 'Versions are not chips');
  assert.ok(models().every(d => !d.open), 'Models start collapsed');
  assert.equal(ids['history-note'].hidden, true, 'Seven-day range starts after the first available day');
  assert.ok(ids.zones.children[0].className.split(' ').includes('ranking-legend'), 'Legend leads the ranking area');
  assert.equal(text(ids.zones.children[0]), '👍 liked · mixed · 👎 disliked — share of opinions about each model for coding. Score = liked − disliked.');
  assert.match(text(ids.zones), /Not enough data/);
  assert.match(text(ids.zones), /other/i, 'Rare versions folded into other');
  assert.ok(!text(ids.zones).includes('Old champion'), 'Seven-day cutoff');
  for (const label of ['Loved & hot', 'Loved, quiet', 'Hot but hated', 'Ignore']) {
    assert.ok(text(ids.chart).includes(label), label);
  }
}
function checkZeroOpinionAndEdges(us, usRanked) {
  const gemini = usRanked[1].children[0];
  assert.equal(gemini.querySelector('.liked-label').textContent, '👍 0% liked');
  assert.equal(gemini.querySelector('.disliked-label').textContent, '👎 0% disliked');
  assertBar(gemini.querySelector('.opinion-bar'), [0, 20, 0], 20);
  const grokScore = usRanked[2].querySelector('.score-pill');
  assert.ok(grokScore.className.split(' ').includes('negative'));
  assert.equal(text(grokScore), 'Score −100');
  assert.equal(grokScore.getAttribute('title'), 'Score = liked % − disliked %');
  const low = us.children.find(n => n.className === 'low-data');
  const zeroRow = low.children.find(n => n.className === 'rank-model' && text(n).includes('Small 0'));
  const zeroSummary = zeroRow.children[0];
  assert.equal(zeroSummary.querySelector('.liked-label').textContent, '👍 0% liked');
  assert.equal(zeroSummary.querySelector('.disliked-label').textContent, '👎 0% disliked');
  assert.deepEqual(zeroSummary.querySelector('.opinion-bar').children.map(node => node.style.width), ['0%', '0%', '0%']);
  assert.equal(zeroSummary.querySelector('.score-pill').getAttribute('title'), 'Score = liked % − disliked %');
  assert.ok(!/NaN|Infinity/.test(text(zeroSummary)), 'Zero-opinion row has finite values');
  return low;
}
function checkRankingMath() {
  const us = ids.zones.children.find(n => n.className === 'zone-section');
  const usRanked = us.children.filter(n => n.className === 'rank-model');
  assert.match(text(usRanked[0]), /Claude Opus/);
  assert.match(text(usRanked[1]), /Gemini/);
  assert.match(text(usRanked[2]), /Grok/);
  assert.ok(!usRanked.some(n => text(n).includes('Rare')), 'Neutral mentions do not satisfy threshold');
  const summary = usRanked[0].children[0];
  const display = summary.querySelector('.opinion-display');
  assert.deepEqual(display.children.map(node => node.className), ['liked-label', 'opinion-bar', 'disliked-label'],
    'Liked label and green share precede mixed and disliked shares');
  assert.equal(display.children[0].textContent, '👍 57% liked');
  assert.equal(display.children[2].textContent, '👎 24% disliked');
  assertBar(display.children[1], [12, 4, 5], 21);
  const score = summary.querySelector('.score-pill');
  assert.equal(text(score), 'Score +33');
  assert.equal(score.getAttribute('title'), 'Score = liked % − disliked %');
  assert.equal(text(summary.querySelector('.opinion-count')), "21 people's opinions");
  const other = walk(usRanked[0]).find(n => n.className === 'version-row' && text(n).includes('Other'));
  assert.ok(other, 'Folded versions remain visible as Other');
  const otherDisplay = other.querySelector('.opinion-display');
  assert.equal(otherDisplay.children[0].textContent, '👍 18% liked');
  assert.equal(otherDisplay.children[2].textContent, '👎 45% disliked');
  assertBar(otherDisplay.children[1], [2, 4, 5], 11);
  assert.equal(text(other.querySelector('.opinion-count')), "11 people's opinions");
  const useCard = ids['use-today'].querySelectorAll('.use-card').find(n => text(n).includes('Claude Opus'));
  assert.equal(text(useCard.querySelector('.use-score-label')), 'Score (liked − disliked)');
  assert.equal(text(useCard.querySelector('.use-distribution')), '👍 57% · 👎 24%');
  assert.equal(text(useCard.querySelector('.use-opinions')), "21 people's opinions");
  const low = checkZeroOpinionAndEdges(us, usRanked);
  const versions = context.Pulse.versionRows(rows.filter(r => r.subject === 'Claude Opus'));
  assert.ok(!versions.some(v => v.name === 'Opus 4'), 'Two mentions must fold into Other');
  assert.equal(versions.find(v => v.name === 'Other').mentions, 11);
  assert.equal(context.Pulse.stats(rows.filter(r => r.subject === 'Rare')).opinions, 19);
  assert.equal(low.open, false, 'Low-data group starts collapsed');
}
function checkChart() {
  const points = ids.chart.querySelectorAll('.point');
  assert.equal(points.length, 4, 'Only rankable models are plotted');
  assert.deepEqual(ids.chart.querySelectorAll('.point-label').map(n => text(n).trim()), ['Opus', 'Gemini', 'Grok', 'Codex']);
  assert.ok(!/NaN|Infinity/.test(ids.chart.innerHTML));
  const svg = ids.chart.querySelector('.buzz-chart');
  const positive = svg.querySelector('.score-positive-zone');
  const negative = svg.querySelector('.score-negative-zone');
  const zero = svg.querySelector('.zero-line');
  assert.equal(positive.tag, 'rect'); assert.equal(negative.tag, 'rect');
  assert.equal(Number(positive.y) + Number(positive.height), Number(zero.y1), 'Green tint ends at zero');
  assert.equal(Number(negative.y), Number(zero.y1), 'Red tint starts at zero');
  assert.ok(Number(negative.y) + Number(negative.height) > Number(zero.y1), 'Red tint fills the lower half');
  assert.equal(text(svg.querySelector('.score-half-positive')).trim(), '👍 more liked');
  assert.equal(text(svg.querySelector('.score-half-negative')).trim(), '👎 more disliked');
  assert.ok(svg.querySelectorAll('.axis-label').some(n => text(n).trim() === 'Score (liked − disliked)'));
  const zoneClasses = points.map(point => point.className.split(' ').find(name => name.startsWith('zone-')));
  assert.deepEqual(zoneClasses, ['zone-us', 'zone-us', 'zone-us', 'zone-tool']);
  assert.ok(points.every(point => point.querySelector('.zone-ring')), 'Every point has a zone-colored ring');
  const legend = ids.chart.querySelector('.chart-zone-legend');
  assert.equal(legend.querySelectorAll('.zone-swatch').length, 3);
  for (const [zone, label] of [['zone-us', 'US frontier'], ['zone-tool', 'Coding tools'], ['zone-open', 'China + open']]) {
    const entry = legend.querySelectorAll('li').find(item => item.querySelector(`.${zone}`));
    assert.ok(entry && text(entry).includes(label), `${zone} is identified in the legend`);
  }
  const point = points.find(n => n['aria-label'].startsWith('Claude Opus'));
  assert.ok(point.className.split(' ').includes('zone-us'));
  const [x, y] = point.transform.match(/[-\d.]+/g).map(Number);
  assert.ok(Math.abs(x - (64 + Math.log(21 / 20) / Math.log(2) * 668 - 12)) < 1e-8);
  assert.ok(Math.abs(y - (52 + (100 - 100 / 3) / 200 * 304 - 12)) < 1e-8);
  point.events.click();
  const expectedTip = 'Claude Opus · 👍 57% · 👎 24% · Score +33 · 21 opinions';
  assert.equal(document.getElementById('chart-tip').textContent.trim(), expectedTip);
  assert.equal(point.getAttribute('data-tip'), expectedTip);
  assert.equal(text(point.querySelector('title')).trim(), expectedTip);
  assert.ok(points.every(n => n.tabindex === '0'), 'Keyboard-focusable points');
  const logo = point.querySelector('svg');
  assert.equal(logo.width, '24'); assert.equal(logo.height, '24');

}
function checkChartTokens() {
  const css = fs.readFileSync(__dirname + '/pulse.css', 'utf8');
  const light = css.match(/:root\s*\{([^}]*)\}/)?.[1];
  const dark = css.match(/:root\[data-theme=dark\]\s*\{([^}]*)\}/)?.[1];
  assert.ok(light && dark, 'Light and dark token groups are present');
  const token = (block, name) => block.match(new RegExp(`${name}:\\s*([^;]+)`))?.[1].trim();
  for (const name of ['--zone-us', '--zone-tool', '--zone-open', '--score-positive-tint', '--score-negative-tint']) {
    assert.ok(token(light, name), `${name} has a light-theme value`);
    assert.ok(token(dark, name), `${name} has a dark-theme value`);
    assert.notEqual(token(light, name), token(dark, name), `${name} adapts for dark theme`);
  }
  assert.equal(new Set(['--zone-us', '--zone-tool', '--zone-open'].map(name => token(light, name))).size, 3,
    'Zone hues are distinct in light theme');
  assert.equal(new Set(['--zone-us', '--zone-tool', '--zone-open'].map(name => token(dark, name))).size, 3,
    'Zone hues are distinct in dark theme');
  assert.match(css, /\.buzz-chart \.score-positive-zone\s*\{[^}]*fill:\s*var\(--score-positive-tint\)/);
  assert.match(css, /\.buzz-chart \.score-negative-zone\s*\{[^}]*fill:\s*var\(--score-negative-tint\)/);
  for (const zone of ['us', 'tool', 'open']) {
    assert.ok(css.includes(`.point.zone-${zone} .zone-ring`), `${zone} ring uses its zone selector`);
    assert.ok(css.includes(`.point.zone-${zone} .point-label`), `${zone} label uses its zone selector`);
  }
}
function checkHistoryNote() {
  const note = ids['history-note'];
  click('range-30');
  assert.equal(note.hidden, false, 'Thirty-day range begins before available history');
  assert.equal(text(note), 'History starts 20 Sep 2026 — longer ranges fill in as daily runs accumulate.');
  click('range-7');
  assert.equal(note.hidden, true, 'Seven-day requested start is after available history');
  ids['date-end'].value = '2026-09-20'; ids['date-end'].events.change();
  assert.equal(ids['date-end'].value, '2026-09-20');
  assert.equal(note.hidden, false, 'Range beginning before first available day stays visible after clamping');
  click('range-today');
  assert.equal(note.hidden, true, 'A range starting on the first available day hides the note');
  click('range-7'); click('back-latest');
  assert.equal(ids['date-end'].value, '2026-09-27');
  assert.equal(note.hidden, true, 'Latest seven-day view is restored');
}
function checkPeriods() {
  click('range-today');
  assert.match(text(ids['use-today']), /\+40/);
  assert.match(text(ids['use-today']), /20 people's opinions/);
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
checkHistoryNote();
checkRankingMath();
checkChart();
checkChartTokens();
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
claudeLabels.run(['pulse.js', 'pulse-trends.js', 'pulse-trend-ui.js', 'pulse-rank.js', 'pulse-chart.js']);
const labels = claudeLabels.ids.chart.querySelectorAll('.point-label');
assert.deepEqual(labels.map(n => text(n).trim()), ['Opus', 'Haiku', 'Code'], 'Shared Claude logos have distinct short labels');
assert.equal(new Set(labels.map(n => `${n.x}/${n.y}/${n['text-anchor']}`)).size, 3,
  'Coincident points use different label positions');
const empty = harness([], {});
empty.run(['pulse.js', 'pulse-trends.js', 'pulse-trend-ui.js', 'pulse-rank.js', 'pulse-chart.js']);
assert.match(text(empty.ids['use-today']), /Not enough talk yet/);
assert.equal(empty.ids['date-prev'].disabled, true);
assert.equal(empty.ids['date-next'].disabled, true);
assert.equal(empty.ids['history-note'].hidden, true, 'No available data hides the history note');
assert.ok(!/NaN|Infinity/.test(empty.ids.chart.innerHTML));
console.log('Pulse UI offline interaction checks passed.');

{
  const {ids, context, run} = harness([], {updatedAt: '2026-09-28T00:04:00Z',
    nextUpdateAt: '2026-09-28T06:00:00Z', startDate: '2026-08-29', runStats: {newOpinions: 1811}});
  run(['pulse.js']);
  context.Pulse.renderUpdate();
  assert.equal(ids['update-info'].textContent,
    'Updated 28 Sep 07:04 (Thai time) · next update ~13:00 · this run read 1,811 new opinions · history since 29 Aug');
  context.Pulse.meta.runStats.newOpinions = 0;
  context.Pulse.renderUpdate();
  assert.match(ids['update-info'].textContent, /read 0 new opinions/);
  assert.equal(context.Pulse.updatedLabel('2026-09-28T18:04:00Z'), '29 Sep 01:04');
}

{
  const {context, run} = harness([], {});
  run(['pulse.js']);
  assert.equal(context.Pulse.dateOf({created_utc: '2026-09-08T12:00:00Z',
    judged_at: '2026-09-28T12:00:00Z', date: '2026-09-28'}), '2026-09-08');
  assert.equal(context.Pulse.dateOf({parent_created_utc: '2026-09-07T12:00:00Z',
    judged_at: '2026-09-28T12:00:00Z'}), '2026-09-07');
}
