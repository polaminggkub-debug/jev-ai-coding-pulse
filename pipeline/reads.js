'use strict';
const root = globalThis;
const Reads = {};
  const icons = {reddit: '🔴', hn: '🟧', github: '🐙', bluesky: '🦋', devto: '✍️', lobsters: '🦞'};
  const names = {reddit: 'Reddit', hn: 'Hacker News', github: 'GitHub',
    bluesky: 'Bluesky', devto: 'Dev.to', lobsters: 'Lobsters'};
  const byId = id => root.document?.getElementById(id);
  const el = (tag, text, cls) => {
    const node = root.document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const validDay = day => /^\d{4}-\d{2}-\d{2}$/.test(String(day || ''));
  const addDays = (day, amount) => new Date(Date.parse(`${day}T00:00:00Z`) + amount * 86400000)
    .toISOString().slice(0, 10);
  const prettyDate = day => validDay(day) ? new Date(`${day}T00:00:00Z`).toLocaleDateString('en-GB',
    {day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC'}) : String(day || '');

  Reads.logoKey = function(name) {
    const value = String(name || '').toLowerCase();
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

  Reads.selectStories = function(data, day, view) {
    const daily = data.daily || {};
    if (view !== 'week') return daily[day] || [];
    const start = addDays(day, -6);
    return Object.entries(daily).filter(([date]) => date >= start && date <= day)
      .flatMap(([, stories]) => stories)
      .sort((a, b) => b.rank_score - a.rank_score || b.date.localeCompare(a.date))
      .slice(0, 10);
  };

  function safeUrl(value) {
    try {
      if (!/^https?:\/\//i.test(String(value || ''))) return '#';
      const url = new URL(value);
      return ['https:', 'http:'].includes(url.protocol) ? url.href : '#';
    } catch (_error) { return '#'; }
  }

  function logo(name, logos) {
    const node = el('span', undefined, 'logo read-logo');
    node.setAttribute('aria-hidden', 'true');
    const key = Reads.logoKey(name), svg = key && logos[key];
    if (svg && /<svg\b/.test(svg)) node.innerHTML = svg;
    else {
      node.classList.add('fallback');
      node.textContent = [...String(name || '?')][0].toUpperCase();
    }
    return node;
  }

  function labelClass(value) {
    if (String(value).startsWith('🔥')) return 'debate';
    if (String(value).startsWith('👍')) return 'love';
    if (String(value).startsWith('👎')) return 'angry';
    return '';
  }

  function addModels(target, models, logos) {
    target.className = 'read-models';
    (models || []).forEach(name => {
      const item = el('span', undefined, 'read-model');
      item.append(logo(name, logos), el('span', name));
      target.append(item);
    });
  }

  function addComment(card, comment) {
    if (!comment?.text) return;
    const quote = el('p', undefined, 'read-comment');
    const votes = comment.score === null || comment.score === undefined ? '' : ` · ▲${comment.score}`;
    quote.append(el('strong', `Top comment${votes}: `), root.document.createTextNode(comment.text));
    card.append(quote);
  }

  function makeCard(story, logos) {
    const card = el('article', undefined, 'read-card');
    const heading = el('h2', undefined, 'read-card-title'), link = el('a', story.title);
    link.href = safeUrl(story.url);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    heading.append(link);
    const meta = el('p', undefined, 'read-meta');
    const source = story.source || 'reddit';
    const badge = el('span', story.source_icon || icons[source] || '💬', 'read-source');
    badge.setAttribute('aria-label', names[source] || source);
    badge.setAttribute('role', 'img');
    const community = source === 'reddit' ? `r/${String(story.community || '').replace(/^r\//i, '')}` : story.community;
    const date = el('time', prettyDate(story.date), 'read-date');
    date.dateTime = story.date;
    meta.append(badge, el('span', community || names[source], 'read-community'), date,
      el('span', `▲${story.score ?? '—'} · 💬${story.comments ?? '—'}`, 'read-stats'));
    const models = el('div');
    addModels(models, story.models, logos);
    const label = el('span', story.label, `read-label ${labelClass(story.label)}`.trim());
    card.append(heading, meta, models, label);
    addComment(card, story.popular_comment);
    return card;
  }

  function render(data, logos, day, view) {
    const cards = byId('reads-cards'), status = byId('reads-status');
    if (!cards || !status) return;
    cards.replaceChildren();
    const stories = Reads.selectStories(data, day, view);
    const start = addDays(day, -6);
    status.textContent = view === 'week' ?
      `Top ${stories.length} threads for ${prettyDate(start)} – ${prettyDate(day)} (UTC).` :
      `Top ${stories.length} threads from ${prettyDate(day)} (UTC).`;
    if (!stories.length) {
      cards.append(el('p', 'No high-confidence reading picks for this date yet.', 'read-empty'));
    } else stories.forEach(story => cards.append(makeCard(story, logos)));
    byId('day-prev').disabled = data.days.indexOf(day) <= 0;
    byId('day-next').disabled = data.days.indexOf(day) < 0 || data.days.indexOf(day) >= data.days.length - 1;
  }

  function bindTheme() {
    const button = byId('theme');
    if (!button) return;
    button.addEventListener('click', () => {
      const dark = root.document.documentElement.dataset.theme ?
        root.document.documentElement.dataset.theme === 'dark' :
        (root.matchMedia?.('(prefers-color-scheme: dark)').matches || false);
      root.document.documentElement.dataset.theme = dark ? 'light' : 'dark';
    });
  }

  function init() {
    const dataNode = byId('reads-data'), select = byId('read-day');
    if (!dataNode || !select) return;
    const data = JSON.parse(dataNode.textContent || '{}');
    const logos = JSON.parse(byId('reads-logos')?.textContent || '{}');
    const days = (data.days || []).filter(validDay).sort();
    let selected = days.includes(data.today) ? data.today : (data.default_day || days.at(-1) || data.today);
    let view = 'day';
    days.forEach(day => {
      const option = el('option', prettyDate(day));
      option.value = day;
      select.append(option);
    });
    if (!days.length) {
      const option = el('option', `No curated days yet · ${prettyDate(data.today)}`);
      option.value = data.today || '';
      select.append(option);
    }
    if (selected && !days.includes(selected) && days.length) selected = days.at(-1);
    select.value = selected || '';
    const update = () => {
      selected = select.value || data.today;
      byId('view-day').setAttribute('aria-pressed', String(view === 'day'));
      byId('view-week').setAttribute('aria-pressed', String(view === 'week'));
      render(data, logos, selected, view);
    };
    select.addEventListener('change', update);
    byId('day-prev').addEventListener('click', () => {
      const index = days.indexOf(selected);
      if (index > 0) { select.value = days[index - 1]; update(); }
    });
    byId('day-next').addEventListener('click', () => {
      const index = days.indexOf(selected);
      if (index >= 0 && index < days.length - 1) { select.value = days[index + 1]; update(); }
    });
    byId('view-day').addEventListener('click', () => { view = 'day'; update(); });
    byId('view-week').addEventListener('click', () => { view = 'week'; update(); });
    bindTheme();
    update();
  }

  Reads.prettyDate = prettyDate;
  Reads.addDays = addDays;
  Reads.init = init;
  root.ReadsUI = Reads;
  if (typeof module !== 'undefined' && module.exports) module.exports = Reads;
  if (root.document) init();
