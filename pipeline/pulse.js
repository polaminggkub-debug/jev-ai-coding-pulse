'use strict';
const rows = JSON.parse(document.getElementById('pulse-data').textContent);
const zones = {us: '🇺🇸 US frontier', tool: '🛠 Coding tools', open: '🇨🇳 China + open models'};
const families = [...new Set(rows.map(r => r.subject))].sort();
const choices = families.flatMap(subject => [{subject, version: null},
  ...[...new Set(rows.filter(r => r.subject === subject && r.version).map(r => r.version))]
    .sort().map(version => ({subject, version}))]);
let selected = null;
const $ = id => document.getElementById(id);
function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
function stats(items) {
  const counts = ['praise', 'mixed', 'complaint'].map(label => items.filter(r => r.label === label).length);
  const total = counts.reduce((a, b) => a + b, 0);
  return {counts, total, net: total ? (counts[0] - counts[2]) / total : 0};
}
function bar(items) {
  const {counts, total} = stats(items);
  const node = el('div');
  const graphic = el('div', undefined, 'b');
  graphic.setAttribute('aria-hidden', 'true');
  counts.forEach((n, i) => {
    const segment = el('span', undefined, ['p', 'x', 'c'][i]);
    segment.style.width = `${total ? n / total * 100 : 0}%`;
    graphic.append(segment);
  });
  node.append(graphic, el('div', counts.map((n, i) =>
    `${['Praise', 'Mixed', 'Complaint'][i]} ${total ? Math.round(n / total * 100) : 0}%`
  ).join(' · ') + ` · ${total} opinions`, 'stats'));
  return node;
}
function link(text, url) {
  const a = el('a', text);
  try { if (['https:', 'http:'].includes(new URL(url).protocol)) a.href = url; } catch (_) { /* Invalid source URL. */ }
  a.target = '_blank'; a.rel = 'noopener noreferrer';
  return a;
}
function quote(items, label) {
  const best = items.filter(r => r.kind === 'comment' && r.label === label)
    .sort((a, b) => b.score - a.score)[0];
  const node = el('blockquote', undefined, label);
  if (best) node.append(link(`“${best.text}”`, best.link), el('span', ` ▲${best.score}`, 'm'));
  else node.textContent = `No ${label} comment available.`;
  return node;
}
function card(subject, items) {
  const details = el('details', undefined, 'model');
  details.open = $('expand').checked || Boolean(selected);
  const summary = el('summary');
  const content = el('span', undefined, 'summary');
  content.append(el('span', selected?.version || subject, 'name'), bar(items));
  summary.append(content);
  const body = el('div', undefined, 'detail');
  body.append(el('h3', 'Versions'));
  const versions = [...new Set(items.map(r => r.version).filter(Boolean))].sort();
  [...versions, null].forEach(version => {
    const row = el('div', undefined, 'version');
    row.append(el('span', version || 'Version unknown'), bar(items.filter(r => r.version === version)));
    body.append(row);
  });
  body.append(el('h3', 'Best-voted praise'), quote(items, 'praise'),
    el('h3', 'Best-voted complaint'), quote(items, 'complaint'), el('h3', 'Top threads'));
  const threads = new Map();
  items.forEach(r => {
    const previous = threads.get(r.thread_url);
    if (!previous || r.thread_score > previous.thread_score) threads.set(r.thread_url, r);
  });
  const list = el('ul');
  [...threads.values()].sort((a, b) => b.thread_score - a.thread_score).slice(0, 5).forEach(r => {
    const li = el('li');
    li.append(el('span', `▲${r.thread_score} · r/${r.sub} `, 'm'), link(r.thread, r.thread_url));
    list.append(li);
  });
  body.append(list); details.append(summary, body);
  return details;
}
function choose(choice) { selected = choice; $('search').value = ''; render(); }
function render() {
  const query = $('search').value.trim().toLowerCase();
  const matches = choices.filter(c => `${c.subject} ${c.version || ''}`.toLowerCase().includes(query));
  $('chips').replaceChildren();
  matches.forEach(c => {
    const button = el('button', c.version ? `${c.subject} · ${c.version}` : c.subject);
    button.type = 'button';
    button.setAttribute('aria-pressed', String(selected?.subject === c.subject && selected?.version === c.version));
    button.addEventListener('click', () => choose(c)); $('chips').append(button);
  });
  $('selection').textContent = selected ? `Showing ${selected.version || selected.subject}` :
    (query ? `${matches.length} matching model choices` : '');
  $('zones').replaceChildren();
  Object.entries(zones).forEach(([zone, title]) => {
    const all = families.filter(subject => rows.some(r => r.subject === subject && r.zone === zone));
    const visible = all.filter(subject => selected ? subject === selected.subject : matches.some(c => c.subject === subject));
    if (!visible.length) return;
    const section = el('section');
    const heading = el('h2', title);
    const ranked = all.map(subject => ({subject, ...stats(rows.filter(r => r.subject === subject))}))
      .filter(s => s.total >= 20).sort((a, b) => b.net - a.net || b.total - a.total || a.subject.localeCompare(b.subject));
    heading.append(el('span', `Best right now: ${ranked[0]?.subject || 'No family has 20 opinions yet'}`, 'pick'));
    section.append(heading);
    visible.sort((a, b) => stats(rows.filter(r => r.subject === b)).total - stats(rows.filter(r => r.subject === a)).total)
      .forEach(subject => section.append(card(subject, rows.filter(r => r.subject === subject &&
        (!selected?.version || r.version === selected.version)))));
    $('zones').append(section);
  });
  if (!$('zones').children.length) $('zones').append(el('p', 'No matching models. Try another search.'));
}
families.map(subject => ({subject, count: rows.filter(r => r.subject === subject).length}))
  .sort((a, b) => b.count - a.count).slice(0, 6).forEach(c => {
    const button = el('button', `${c.subject} ${c.count}`);
    button.addEventListener('click', () => choose({subject: c.subject, version: null})); $('buzz').append(button);
  });
$('search').addEventListener('input', () => { selected = null; render(); });
$('clear').addEventListener('click', () => { selected = null; $('search').value = ''; render(); });
$('expand').addEventListener('change', () => document.querySelectorAll('.model').forEach(d => { d.open = $('expand').checked; }));
$('theme').addEventListener('click', () => {
  const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' :
    matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = dark ? 'light' : 'dark';
});
render();
