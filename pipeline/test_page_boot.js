// Execute the shipped artifact's embedded scripts, not just source modules.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {harness, text} = require('./ui_harness');
const page = fs.readFileSync(__dirname + '/../pulse.html', 'utf8');
assert.doesNotMatch(page, /id="timeline"|pulse-timeline(?:-core)?\.js/,
  'The shipped page has no Timeline section or scripts');
function payload(id) {
  const encoded = page.split(`id="${id}" type="application/json">`)[1]?.split('</script>')[0];
  assert.ok(encoded, `Shipped page contains ${id}`);
  return JSON.parse(encoded);
}
const {ids, context} = harness(payload('pulse-data'), payload('pulse-meta'), payload('pulse-logos'));
const scripts = [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
scripts.forEach((script, index) => vm.runInContext(script, context, {filename: `embedded-${index}.js`}));
const P = context.Pulse;
assert.ok(text(ids['update-info']).includes('(Thai time)'));
assert.ok(ids['covered-period'].textContent.startsWith('Comments from '), 'Date summary still renders');
assert.ok(ids['trend-alerts'].children.length, 'Trend alerts still render');
assert.ok(ids['use-today'].children.length, 'Use today recommendations still render');
assert.ok(ids.chart.innerHTML.includes('<svg'), 'The score chart still renders');
assert.ok(ids.zones.children.length, 'Model ranking still renders');
assert.equal(P.availableDates.length, P.meta.days.length, 'Date handling still reads shipped history');
console.log('Shipped offline page boot, dates, trends, ranking, and chart checks passed.');
