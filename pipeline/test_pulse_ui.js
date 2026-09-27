// Dependency-free DOM harness: exercises the shipped UI logic offline.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.dataset = {}; this.events = {}; this.value = ''; this.checked = false; this.textContent = ''; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, action) { this.events[name] = action; }
}
function walk(node) { return [node, ...node.children.flatMap(walk)]; }
function text(node) { return walk(node).map(n => n.textContent).join(' '); }
const ids = Object.fromEntries(['pulse-data', 'expand', 'chips', 'selection', 'zones', 'buzz', 'search', 'clear', 'theme'].map(id => [id, new Element(id)]));
const fixture = (subject, label, version, score) => ({subject, label, version, score,
  kind: 'comment', zone: 'us', text: `Quote ${score}`, link: 'https://reddit.com/comment',
  thread_url: 'https://reddit.com/thread', thread_score: 10, sub: 'Coding', thread: 'Thread'});
const data = [fixture('Rare', 'praise', 'Rare 1', 100),
  ...Array.from({length: 20}, (_, i) => fixture('Popular', i < 12 ? 'praise' : i < 16 ? 'mixed' : 'complaint', i < 10 ? 'Popular 2' : null, i))];
ids['pulse-data'].textContent = JSON.stringify(data);
const document = {getElementById: id => ids[id], createElement: tag => new Element(tag), documentElement: new Element('html'),
  querySelectorAll: () => walk(ids.zones).filter(n => n.tag === 'details')};
vm.runInNewContext(fs.readFileSync(__dirname + '/pulse.js', 'utf8'), {document, URL, matchMedia: () => ({matches: false})});
assert.equal(document.querySelectorAll().length, 2);
assert.ok(document.querySelectorAll().every(d => !d.open), 'Quick view starts collapsed');
assert.ok(text(ids.zones).includes('Best right now: Popular'), 'Rare perfect sentiment cannot win pick');
assert.ok(text(ids.zones).includes('Praise 60% · Mixed 20% · Complaint 20% · 20 opinions'));
assert.ok(text(ids.zones).includes('Version unknown'));
assert.ok(text(ids.zones).includes('“Quote 11”'), 'Best-voted praise');
assert.ok(text(ids.zones).includes('“Quote 19”'), 'Best-voted complaint');
assert.equal(ids.chips.children.length, 4, 'Every family and version gets a chip');
ids.chips.children.find(c => c.textContent === 'Rare · Rare 1').events.click();
assert.equal(document.querySelectorAll().length, 1, 'Rare version is selectable');
assert.ok(document.querySelectorAll()[0].open);
assert.ok(text(ids.zones).includes('1 opinions'));
ids.clear.events.click();
ids.expand.checked = true; ids.expand.events.change();
assert.ok(document.querySelectorAll().every(d => d.open));
ids.expand.checked = false; ids.expand.events.change();
assert.ok(document.querySelectorAll().every(d => !d.open));
ids.search.value = 'popular 2'; ids.search.events.input();
assert.equal(ids.chips.children.length, 1);
ids.chips.children[0].events.click();
assert.ok(text(ids.zones).includes('10 opinions'));
ids.clear.events.click();
ids.search.value = 'nothing matches'; ids.search.events.input();
assert.ok(text(ids.zones).includes('No matching models'));
ids.theme.events.click(); assert.equal(document.documentElement.dataset.theme, 'dark');
ids.theme.events.click(); assert.equal(document.documentElement.dataset.theme, 'light');
console.log('Pulse UI offline interaction checks passed.');
