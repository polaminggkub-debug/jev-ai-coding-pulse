'use strict';
const P = globalThis.Pulse = globalThis.Pulse || {};
P.$ = id => document.getElementById(id);
P.el = (tag, value, cls) => {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = value;
  if (cls) node.className = cls;
  return node;
};
P.rows = JSON.parse(P.$('pulse-data').textContent || '[]');
P.meta = JSON.parse(P.$('pulse-meta')?.textContent || '{}');
P.logos = JSON.parse(P.$('pulse-logos')?.textContent || '{}');
P.zones = {us: '🇺🇸 US frontier', tool: '🛠 Coding tools', open: '🇨🇳 China + open'};
P.rangeDays = 7;
P.selected = null;
P.query = '';
P.latestDate = P.meta.endDate || '';
P.dateOf = function(row) {
  for (const value of [row.created_utc, row.parent_created_utc, row.post_created_utc, row.judged_at, row.date]) {
    if (value === null || value === undefined || value === '') continue;
    const number = Number(value);
    const stamp = Number.isFinite(number) ? number * (Math.abs(number) > 1e11 ? 1 : 1000) : Date.parse(value);
    if (Number.isFinite(stamp) && Math.abs(stamp) <= 8640000000000000) {
      return new Date(stamp).toISOString().slice(0, 10);
    }
  }
  return null;
};
P.availableDates = [...new Set((P.meta.days || []).filter(day => /^\d{4}-\d{2}-\d{2}$/.test(day)))].sort();
if (!P.availableDates.length) P.availableDates = [...new Set(P.rows.map(P.dateOf).filter(Boolean))].sort();
P.latestDate = P.latestDate || P.availableDates[P.availableDates.length - 1] || new Date().toISOString().slice(0, 10);
P.endDate = P.latestDate;
P.startDate = P.meta.startDate || P.availableDates[0] || P.latestDate;
P.addDays = function(day, amount) {
  return new Date(Date.parse(`${day}T00:00:00Z`) + amount * 86400000).toISOString().slice(0, 10);
};
P.shortDate = function(day) {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const [year, month, date] = day.split('-').map(Number);
  return `${date} ${months[month - 1]} ${year}`;
};
P.updatedLabel = function(value, timeOnly = false) {
  const stamp = Date.parse(value);
  if (!Number.isFinite(stamp)) return 'time not recorded';
  const thai = new Date(stamp + 7 * 3600000).toISOString();
  const clock = thai.slice(11, 16);
  return timeOnly ? clock : `${Number(thai.slice(8, 10))} ${P.shortDate(thai.slice(0, 10)).split(' ')[1]} ${clock}`;
};
P.renderUpdate = function() {
  const target = P.$('update-info');
  if (!target) return;
  const count = P.meta.runStats?.newOpinions;
  const opinions = Number.isFinite(count) ? count.toLocaleString('en-US') : 'unknown';
  const next = P.meta.nextUpdateAt ? P.updatedLabel(P.meta.nextUpdateAt, true) : 'unknown';
  const start = P.meta.startDate ? P.shortDate(P.meta.startDate).replace(/ \d{4}$/, '') : 'unknown';
  target.textContent = `Updated ${P.updatedLabel(P.meta.updatedAt)} (Thai time) · next update ~${next} · this run read ${opinions} new opinions · history since ${start}`;
};
P.windowStart = function() {
  const start = P.addDays(P.endDate, -(P.rangeDays - 1));
  return start < P.startDate ? P.startDate : start;
};
P.rowsForRange = function() {
  const start = P.windowStart();
  return P.rows.filter(row => {
    const day = P.dateOf(row);
    return day && day >= start && day <= P.endDate;
  });
};
P.stats = function(rows) {
  const praise = rows.filter(row => row.label === 'praise').length;
  const mixed = rows.filter(row => row.label === 'mixed').length;
  const complaint = rows.filter(row => row.label === 'complaint').length;
  const opinions = praise + mixed + complaint;
  return {praise, mixed, complaint, opinions, mentions: rows.length,
    net: opinions ? (praise - complaint) * 100 / opinions : 0};
};
P.familiesFor = rows => [...new Set(rows.map(row => row.subject).filter(Boolean))];
P.rowsFor = (rows, subject) => rows.filter(row => row.subject === subject);
P.versionsFor = function(rows) {
  const versions = new Map();
  rows.forEach(row => {
    const name = row.version || 'Version unknown';
    if (!versions.has(name)) versions.set(name, []);
    versions.get(name).push(row);
  });
  return [...versions].map(([name, items]) => ({name, items, mentions: items.length}));
};
P.zoneFor = function(subject, rows) {
  const found = rows.find(row => row.subject === subject && P.zones[row.zone]);
  return found ? found.zone : 'open';
};
P.logoKey = function(name) {
  const value = name.toLowerCase();
  if (/claude|opus|sonnet|haiku|fable/.test(value)) return 'claude';
  if (/codex/.test(value)) return 'codex';
  if (/gpt|chatgpt|openai/.test(value)) return 'openai';
  if (/gemma/.test(value)) return 'gemma';
  if (/gemini/.test(value)) return 'gemini';
  if (/grok/.test(value)) return 'grok';
  if (/deepseek/.test(value)) return 'deepseek';
  if (/qwen/.test(value)) return 'qwen';
  if (/kimi/.test(value)) return 'kimi';
  if (/glm/.test(value)) return 'glm';
  if (/minimax/.test(value)) return 'minimax';
  if (/mistral/.test(value)) return 'mistral';
  if (/llama/.test(value)) return 'llama';
  if (/mimo|xiaomi/.test(value)) return 'mimo';
  if (/cursor/.test(value)) return 'cursor';
  if (/copilot/.test(value)) return 'copilot';
  if (/opencode/.test(value)) return 'opencode';
  return null;
};
P.logo = function(name, cls) {
  const node = P.el('span', undefined, `logo ${cls || ''}`.trim());
  node.setAttribute('aria-hidden', 'true');
  const key = P.logoKey(name);
  if (key && P.logos[key]) node.innerHTML = P.logos[key];
  else {
    node.classList?.add('fallback');
    node.textContent = [...String(name || '?')][0].toUpperCase();
  }
  return node;
};
P.netText = value => {
  const rounded = Math.round(value);
  return rounded < 0 ? `−${Math.abs(rounded)}` : `+${rounded}`;
};
P.escape = value => String(value ?? '').replace(/[&<>"']/g, char =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
P.renderHistoryNote = function() {
  const note = P.$('history-note');
  const first = P.availableDates[0];
  const requestedStart = P.addDays(P.endDate, -(P.rangeDays - 1));
  note.hidden = !first || requestedStart >= first;
  note.textContent = note.hidden ? '' :
    `History starts ${P.shortDate(first)} — longer ranges fill in as daily runs accumulate.`;
};
P.renderTime = function() {
  P.renderHistoryNote();
  const start = P.windowStart();
  P.renderUpdate();
  P.$('covered-period').textContent = `Comments from ${P.shortDate(start)} – ${P.shortDate(P.endDate)}`;
  P.$('range-status').textContent = `${P.rangeDays === 1 ? '1 day' : `${P.rangeDays} days`} ending ${P.shortDate(P.endDate)} (UTC)`;
  [[1, 'range-today'], [7, 'range-7'], [30, 'range-30']].forEach(([days, id]) =>
    P.$(id).setAttribute('aria-pressed', String(days === P.rangeDays)));
  const select = P.$('date-end');
  if (select) {
    const options = [];
    for (let day = P.startDate; day <= P.latestDate; day = P.addDays(day, 1)) {
      const option = P.el('option', P.shortDate(day));
      option.value = day;
      option.disabled = !P.availableDates.includes(day);
      option.selected = day === P.endDate;
      options.push(option);
    }
    select.replaceChildren(...options);
    select.value = P.endDate;
  }
  const index = P.availableDates.indexOf(P.endDate);
  P.$('date-prev').disabled = index <= 0;
  P.$('date-next').disabled = index < 0 || index >= P.availableDates.length - 1;
  P.$('back-latest').hidden = P.endDate === P.latestDate;
};
P.clearFilters = function() {
  P.selected = null;
  P.query = '';
  if (P.$('search')) P.$('search').value = '';
};
P.setRange = function(days) {
  P.rangeDays = days;
  P.clearFilters();
  P.render();
};
P.setEndDate = function(day) {
  if (!P.availableDates.includes(day)) return;
  P.endDate = day;
  P.clearFilters();
  P.render();
};
P.moveDate = function(offset) {
  const index = P.availableDates.indexOf(P.endDate);
  const next = P.availableDates[index + offset];
  if (next) P.setEndDate(next);
};
P.bindTime = function() {
  [[1, 'range-today'], [7, 'range-7'], [30, 'range-30']].forEach(([days, id]) =>
    P.$(id).addEventListener('click', () => P.setRange(days)));
  P.$('date-prev').addEventListener('click', () => P.moveDate(-1));
  P.$('date-next').addEventListener('click', () => P.moveDate(1));
  P.$('date-end').addEventListener('change', () => P.setEndDate(P.$('date-end').value));
  P.$('back-latest').addEventListener('click', event => {
    event.preventDefault(); P.setEndDate(P.latestDate);
  });
};
