'use strict';
const assert = require('node:assert/strict');
const Reads = require('./reads.js');

const days = [];
const daily = {};
for (let index = 0; index < 7; index += 1) {
  const day = Reads.addDays('2026-09-22', index);
  days.push(day);
  daily[day] = Array.from({length: 10}, (_, rank) => ({
    id: `${day}-${rank}`, date: day, rank_score: index * 10 + rank,
  }));
}
const data = {days, daily};

assert.equal(Reads.selectStories(data, '2026-09-28', 'day').length, 10);
assert.equal(Reads.selectStories(data, '2026-09-28', 'week').length, 10);
assert.equal(Reads.selectStories(data, '2026-09-28', 'week')[0].id, '2026-09-28-9');
assert.equal(Reads.selectStories(data, '2026-09-24', 'week').length, 10);
assert.equal(Reads.logoKey('Claude Opus'), 'claude');
assert.equal(Reads.logoKey('GPT / ChatGPT'), 'openai');
assert.equal(Reads.logoKey('Unknown model'), null);

class FakeNode {
  constructor(tag, id) {
    this.tag = tag; this.id = id; this.children = []; this.handlers = {};
    this.attributes = {}; this.dataset = {}; this.classList = {add: () => {}};
    this.value = ''; this.textContent = ''; this.disabled = false;
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, handler) { this.handlers[name] = handler; }
  fire(name) { this.handlers[name]?.(); }
}

function makeSurface(payload) {
  const ids = ['reads-data', 'reads-logos', 'read-day', 'day-prev', 'day-next',
    'view-day', 'view-week', 'reads-status', 'reads-cards', 'theme'];
  const nodes = Object.fromEntries(ids.map(id => [id, new FakeNode('div', id)]));
  nodes['reads-data'].textContent = JSON.stringify(payload);
  nodes['reads-logos'].textContent = '{}';
  nodes['read-day'].tag = 'select';
  global.document = {
    getElementById: id => nodes[id],
    createElement: tag => new FakeNode(tag),
    createTextNode: text => Object.assign(new FakeNode('#text'), {textContent: text}),
    documentElement: {dataset: {}},
  };
  return nodes;
}

function loadUi(payload) {
  const nodes = makeSurface(payload);
  delete require.cache[require.resolve('./reads.js')];
  require('./reads.js');
  return nodes;
}

const emptyNodes = loadUi({days: [], daily: {}, today: '2026-09-28', default_day: '2026-09-28'});
assert.match(emptyNodes['read-day'].children[0].textContent, /No curated days yet/);
assert.equal(emptyNodes['read-day'].value, '2026-09-28');
assert.match(emptyNodes['reads-status'].textContent, /Top 0 threads/);

const story = {id: 'a', source: 'reddit', community: 'Example', title: 'A coding thread',
  url: 'https://example.test/thread', date: '2026-09-28', score: 12, comments: 4,
  models: ['Claude Opus'], label: '👍 People love it', rank_score: 0.8,
  popular_comment: {text: 'A useful comment', score: 3}};
const populatedNodes = loadUi({days: ['2026-09-27', '2026-09-28'],
  daily: {'2026-09-27': [{...story, id: 'older', title: 'Older thread'}],
    '2026-09-28': [story]}, today: '2026-09-28', default_day: '2026-09-28'});
assert.equal(populatedNodes['reads-cards'].children.length, 1);
let heading = populatedNodes['reads-cards'].children[0].children[0];
assert.equal(heading.children[0].textContent, 'A coding thread');
populatedNodes['day-prev'].fire('click');
heading = populatedNodes['reads-cards'].children[0].children[0];
assert.equal(heading.children[0].textContent, 'Older thread');
populatedNodes['read-day'].value = '2026-09-28';
populatedNodes['read-day'].fire('change');
populatedNodes['view-week'].fire('click');
assert.equal(populatedNodes['reads-cards'].children.length, 2);
assert.equal(populatedNodes['view-week'].attributes['aria-pressed'], 'true');
console.log('Reads day, week, empty state, and card render checks passed.');
