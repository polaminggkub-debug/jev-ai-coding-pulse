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
  if (/^\d{4}-\d{2}-\d{2}$/.test(row.date || '')) return row.date;
  const value = row.created_utc;
  if (typeof value === 'number' && Number.isFinite(value)) {
    return new Date(value > 1e12 ? value : value * 1000).toISOString().slice(0, 10);
  }
  if (typeof value === 'string' && value.trim()) {
    const n = Number(value);
    const stamp = Number.isFinite(n) ? (n > 1e12 ? n : n * 1000) : Date.parse(value);
    return Number.isFinite(stamp) ? new Date(stamp).toISOString().slice(0, 10) : null;
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
P.updatedLabel = function(value) {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  return match ? `${Number(match[3])} ${P.shortDate(value.slice(0, 10)).split(' ')[1]} ${match[1]} ${match[4]}:${match[5]} UTC` : 'time not recorded';
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
P.renderTime = function() {
  const start = P.windowStart();
  const updated = P.updatedLabel(P.meta.updatedAt);
  P.$('covered-period').textContent = `Comments from ${P.shortDate(start)} – ${P.shortDate(P.endDate)} · updated ${updated}`;
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
