// Minimal offline DOM surface: state and events stay observable to assertions.
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.style = {}; this.dataset = {};
    this.events = {}; this.value = ''; this.checked = false;
    this.textContent = ''; this.attributes = {}; this.hidden = false;
    this.classList = {add: cls => { this.className = `${this.className || ''} ${cls}`.trim(); }};
  }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.append(child); return child; }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) {
    this.attributes[name] = String(value); this[name] = String(value);
    if (name === 'class') this.className = String(value);
  }
  set innerHTML(html) { this._html = html; this.children = parseHTML(html); }
  get innerHTML() { return this._html || ''; }
  getAttribute(name) { return this.attributes[name]; }
  addEventListener(name, action) { this.events[name] = action; }
  querySelectorAll(selector) { return walk(this).filter(n => matches(n, selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
function decode(value) {
  return value.replace(/&(amp|lt|gt|quot|#39);/g,
    (_, key) => ({amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'"})[key]);
}
function parseHTML(html) {
  const root = new Element('fragment');
  const stack = [root];
  for (const token of html.match(/<[^>]+>|[^<]+/g) || []) {
    if (token.startsWith('</')) { if (stack.length > 1) stack.pop(); continue; }
    if (token.startsWith('<')) {
      const tag = token.match(/^<([\w-]+)/)?.[1];
      if (!tag) continue;
      const node = new Element(tag);
      for (const match of token.matchAll(/([\w:-]+)="([^"]*)"/g)) node.setAttribute(match[1], decode(match[2]));
      stack[stack.length - 1].append(node);
      if (!token.endsWith('/>') && !['input', 'br', 'img', 'meta'].includes(tag)) stack.push(node);
    } else {
      const node = new Element('#text'); node.textContent = decode(token);
      stack[stack.length - 1].append(node);
    }
  }
  return root.children;
}
function walk(node) { return [node, ...node.children.flatMap(walk)]; }
function text(node) { return walk(node).map(n => n.textContent).join(' '); }
function matches(node, selector) {
  if (selector.includes(',')) return selector.split(',').some(part => matches(node, part));
  if (selector.startsWith('.')) return (node.className || '').split(' ').includes(selector.slice(1));
  return node.tag === selector;
}
class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [Date.UTC(2026, 8, 27, 12)])); }
  static now() { return Date.UTC(2026, 8, 27, 12); }
}
function harness(rows, meta, logos = {}) {
  const names = ['pulse-data', 'pulse-meta', 'pulse-logos', 'expand', 'chips', 'selection', 'zones',
    'use-today', 'chart', 'search', 'theme', 'range-status', 'range-today', 'range-7', 'range-30',
    'covered-period', 'date-prev', 'date-next', 'date-end', 'back-latest'];
  const ids = Object.fromEntries(names.map(id => [id, new Element(id)]));
  ids['pulse-data'].textContent = JSON.stringify(rows);
  ids['pulse-meta'].textContent = JSON.stringify(meta);
  ids['pulse-logos'].textContent = JSON.stringify(logos);
  const document = {getElementById: id => ids[id] || Object.values(ids).flatMap(walk).find(n => n.id === id), createElement: tag => new Element(tag),
    createElementNS: (_, tag) => new Element(tag), documentElement: new Element('html'),
    querySelectorAll: selector => Object.values(ids).flatMap(n => n.querySelectorAll(selector))};
  const context = vm.createContext({document, URL, Date: FixedDate, matchMedia: () => ({matches: false})});
  return {ids, document, context, run: names => names.forEach(name =>
    vm.runInContext(fs.readFileSync(__dirname + '/' + name, 'utf8'), context, {filename: name}))};
}
module.exports = {Element, walk, text, harness};
