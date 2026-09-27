// Execute the shipped artifact's embedded scripts, not just source modules.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {harness, Element, text} = require('./ui_harness');
const page = fs.readFileSync(__dirname + '/../pulse.html', 'utf8');
function payload(id) {
  const encoded = page.split(`id="${id}" type="application/json">`)[1]?.split('</script>')[0];
  assert.ok(encoded, `Shipped page contains ${id}`);
  return JSON.parse(encoded);
}
const {ids, context} = harness(payload('pulse-data'), payload('pulse-meta'), payload('pulse-logos'));
ids.timeline = new Element('section');
const intervals = new Map();
let serial = 0;
context.setInterval = (callback, delay) => { intervals.set(++serial, {callback, delay}); return serial; };
context.clearInterval = id => intervals.delete(id);
const scripts = [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
assert.ok(scripts.length >= 7, 'Timeline calculation and UI scripts are embedded');
scripts.forEach((script, index) => vm.runInContext(script, context, {filename: `embedded-${index}.js`}));
const P = context.Pulse;
assert.ok(P.timelineState, 'Timeline initializes from shipped page data');
assert.equal(P.timelineState.dates.length, 30);
assert.ok(text(ids['update-info']).includes('(Thai time)'));
assert.ok(ids.timeline.querySelectorAll('svg').length >= 1, 'Timeline has inline SVG');
const state = P.timelineState;
state.refs.play.events.click();
assert.equal(intervals.size, 1, 'Play creates one timer');
const timer = [...intervals.values()][0];
assert.equal(timer.delay, 800);
const prior = state.index;
timer.callback();
assert.equal(state.index, prior + 1, 'Playback advances one day');
state.refs.play.events.click();
assert.equal(intervals.size, 0, 'Pause cancels playback');
console.log('Shipped offline page boot and playback checks passed.');
