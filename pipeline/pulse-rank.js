'use strict';
const R = globalThis.Pulse;
R.modelsFor = function(rows) {
  return R.familiesFor(rows).map(subject => {
    const items = R.rowsFor(rows, subject);
    return {subject, items, zone: R.zoneFor(subject, items), stats: R.stats(items)};
  });
};
R.compareModels = (a, b) => b.stats.net - a.stats.net ||
  b.stats.opinions - a.stats.opinions || a.subject.localeCompare(b.subject);
R.diverging = function(stats) {
  const bar = R.el('span', undefined, 'diverging');
  bar.setAttribute('role', 'img');
  bar.setAttribute('aria-label', `Praise ${Math.round(100 * stats.praise / (stats.opinions || 1))}%, complaint ${Math.round(100 * stats.complaint / (stats.opinions || 1))}%`);
  const negative = R.el('span', undefined, 'diverging-negative');
  const positive = R.el('span', undefined, 'diverging-positive');
  negative.style.width = `${50 * stats.complaint / (stats.opinions || 1)}%`;
  positive.style.width = `${50 * stats.praise / (stats.opinions || 1)}%`;
  bar.append(negative, positive);
  return bar;
};
R.quote = function(items, label) {
  const best = items.filter(row => row.kind === 'comment' && row.label === label)
    .sort((a, b) => (b.score || 0) - (a.score || 0))[0];
  const quote = R.el('blockquote', undefined, `quote-line ${label}`);
  if (!best) { quote.textContent = `No ${label} comment available.`; return quote; }
  const anchor = R.el('a', `“${best.text || ''}”`);
  if (/^https?:\/\//i.test(best.link || '')) anchor.href = best.link;
  anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
  quote.append(anchor, R.el('span', ` ▲${best.score || 0}`, 'muted'));
  return quote;
};
R.versionRows = function(items) {
  const versions = R.versionsFor(items).sort((a, b) => b.mentions - a.mentions || a.name.localeCompare(b.name));
  const shown = versions.filter(version => version.name !== 'Version unknown' && version.mentions >= 3);
  const folded = versions.filter(version => !shown.includes(version)).flatMap(version => version.items);
  if (folded.length) shown.push({name: 'Other', items: folded, mentions: folded.length});
  return shown;
};
R.versionDetail = function(version) {
  const stat = R.stats(version.items);
  const row = R.el('div', undefined, 'version-row');
  const meta = R.el('span', `${version.name} · ${version.mentions} mentions`, 'version-name');
  row.append(meta, R.diverging(stat), R.el('span', `${R.netText(stat.net)} Net`, 'muted'));
  return row;
};
R.threadList = function(items) {
  const threads = new Map();
  items.filter(row => row.thread_url).forEach(row => {
    const old = threads.get(row.thread_url);
    if (!old || (row.thread_score || 0) > (old.thread_score || 0)) threads.set(row.thread_url, row);
  });
  const list = R.el('ul', undefined, 'threads');
  [...threads.values()].sort((a, b) => (b.thread_score || 0) - (a.thread_score || 0)).slice(0, 5).forEach(row => {
    const item = R.el('li');
    item.append(R.el('span', `▲${row.thread_score || 0} · r/${row.sub || ''} `, 'muted'));
    const anchor = R.el('a', row.thread || row.thread_url);
    if (/^https?:\/\//i.test(row.thread_url)) anchor.href = row.thread_url;
    anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
    item.append(anchor); list.append(item);
  });
  return list;
};
R.detail = function(model) {
  const body = R.el('div', undefined, 'model-detail');
  const versions = R.el('div', undefined, 'version-list');
  versions.append(R.el('h3', 'Versions'));
  R.versionRows(model.items).forEach(version => versions.append(R.versionDetail(version)));
  body.append(versions, R.el('h3', 'Best-voted praise'), R.quote(model.items, 'praise'),
    R.el('h3', 'Best-voted complaint'), R.quote(model.items, 'complaint'),
    R.el('h3', 'Top threads'), R.threadList(model.items));
  return body;
};
R.rankRow = function(model, open) {
  const row = R.el('details', undefined, 'rank-model');
  row.open = Boolean(open || R.$('expand').checked || R.selected === model.subject);
  const summary = R.el('summary');
  const identity = R.el('span', undefined, 'rank-identity');
  identity.append(R.logo(model.subject), R.el('span', model.subject, 'model-name'));
  const net = R.el('span', undefined, `net ${model.stats.net < 0 ? 'negative' : 'positive'}`);
  net.append(R.el('span', 'Net ', 'net-label'), R.el('strong', R.netText(model.stats.net)));
  summary.append(identity, net, R.diverging(model.stats),
    R.el('span', `${model.stats.opinions} opinions`, 'opinion-count'));
  row.append(summary, R.detail(model));
  return row;
};
R.matches = function(model) {
  if (R.selected && R.selected !== model.subject) return false;
  if (!R.query) return true;
  const q = R.query.toLowerCase();
  return model.subject.toLowerCase().includes(q) || model.items.some(item => (item.version || '').toLowerCase().includes(q));
};
R.matchVersion = model => R.query && model.items.some(item => (item.version || '').toLowerCase().includes(R.query.toLowerCase()));
R.renderUseToday = function(models) {
  const target = R.$('use-today');
  target.replaceChildren(R.el('h2', 'Use today', 'strip-title'));
  Object.entries(R.zones).forEach(([zone, title]) => {
    const ranked = models.filter(model => model.zone === zone && model.stats.opinions >= 20).sort(R.compareModels);
    const card = R.el('article', undefined, 'use-card');
    card.append(R.el('h2', title));
    if (!ranked.length) card.append(R.el('p', 'Not enough talk yet', 'empty-pick'));
    else {
      const best = ranked[0];
      const version = R.versionsFor(best.items).filter(item => item.name !== 'Version unknown')
        .sort((a, b) => b.mentions - a.mentions)[0];
      const titleLine = R.el('div', undefined, 'use-winner');
      titleLine.append(R.logo(best.subject), R.el('strong', best.subject));
      card.append(titleLine);
      card.append(R.el('p', version ? `mostly ${version.name}` : 'version not specified', 'mostly-version'));
      card.append(R.el('strong', R.netText(best.stats.net), `use-net ${best.stats.net < 0 ? 'negative' : 'positive'}`),
        R.el('p', `${best.stats.opinions} opinions`, 'use-opinions'), R.quote(best.items, 'praise'));
    }
    const runner = ranked[1];
    card.append(R.el('p', runner ? `runner-up: ${runner.subject} ${R.netText(runner.stats.net)}` : 'runner-up: none yet', 'runner-up'));
    target.append(card);
  });
};
R.renderChips = function(models) {
  const target = R.$('chips');
  const top = models.slice().sort((a, b) => b.stats.mentions - a.stats.mentions || a.subject.localeCompare(b.subject)).slice(0, 10);
  target.replaceChildren();
  top.forEach(model => {
    const button = R.el('button', undefined, 'model-chip');
    button.type = 'button';
    button.setAttribute('aria-pressed', String(R.selected === model.subject));
    button.append(R.logo(model.subject), R.el('span', model.subject));
    button.addEventListener('click', () => {
      R.selected = R.selected === model.subject ? null : model.subject;
      R.query = ''; R.$('search').value = '';
      R.render();
    });
    target.append(button);
  });
};
R.renderZones = function(models) {
  const target = R.$('zones');
  target.replaceChildren();
  Object.entries(R.zones).forEach(([zone, title]) => {
    const section = R.el('section', undefined, 'zone-section');
    section.append(R.el('h2', title));
    const current = models.filter(model => model.zone === zone);
    const visible = current.filter(R.matches);
    const ranked = visible.filter(model => model.stats.opinions >= 20).sort(R.compareModels);
    const low = visible.filter(model => model.stats.opinions < 20).sort((a, b) => b.stats.mentions - a.stats.mentions);
    if (ranked.length) ranked.forEach(model => section.append(R.rankRow(model, R.matchVersion(model))));
    if (low.length) {
      const group = R.el('details', undefined, 'low-data');
      group.open = R.$('expand').checked || Boolean(R.query && low.some(R.matchVersion)) || Boolean(R.selected);
      group.append(R.el('summary', `Not enough data (${low.length})`));
      low.forEach(model => group.append(R.rankRow(model, R.matchVersion(model))));
      section.append(group);
    }
    if (!visible.length) section.append(R.el('p', 'No matching models in this zone.', 'muted'));
    target.append(section);
  });
};
R.renderRanking = function() {
  const rows = R.rowsForRange();
  const models = R.modelsFor(rows);
  R.renderUseToday(models);
  R.renderChips(models);
  R.renderZones(models);
  R.$('selection').textContent = R.selected ? `Showing ${R.selected}` : R.query ? `${models.filter(R.matches).length} matching families or versions` : '';
  return models;
};
R.bindSelection = function() {
  R.$('search').addEventListener('input', () => {
    R.query = R.$('search').value.trim(); R.selected = null; R.render();
  });
  R.$('expand').addEventListener('change', () => {
    document.querySelectorAll('.rank-model,.low-data').forEach(node => { node.open = R.$('expand').checked; });
  });
};
