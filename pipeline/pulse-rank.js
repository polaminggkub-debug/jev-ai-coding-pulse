'use strict';
const R = globalThis.Pulse;
R.modelsFor = function(rows) {
  return R.familiesFor(rows).map(subject => {
    const items = R.rowsFor(rows, subject);
    return {subject, items, zone: R.zoneFor(subject, items), stats: R.stats(items)};
  });
};
R.rankingMinimum = () => R.rangeDays === 1 ? 8 : 20;
R.rankable = (model, minimum = R.rankingMinimum()) =>
  model.stats.opinions >= minimum && (R.scoreMode !== 'fair' || model.fairNet !== null);
R.compareModels = (a, b) => b.stats.net - a.stats.net ||
  b.stats.opinions - a.stats.opinions || a.subject.localeCompare(b.subject);
R.shares = function(stats) {
  const total = stats.opinions || 0;
  return total ? {
    liked: 100 * stats.praise / total,
    mixed: 100 * stats.mixed / total,
    disliked: 100 * stats.complaint / total
  } : {liked: 0, mixed: 0, disliked: 0};
};
R.percentText = value => `${Math.round(value)}%`;
R.opinionBar = function(stats) {
  const shares = R.shares(stats);
  const bar = R.el('span', undefined, 'opinion-bar');
  bar.setAttribute('role', 'img');
  bar.setAttribute('aria-label', `${R.percentText(shares.liked)} liked, ${R.percentText(shares.mixed)} mixed, ${R.percentText(shares.disliked)} disliked`);
  const liked = R.el('span', undefined, 'opinion-liked');
  const mixed = R.el('span', undefined, 'opinion-mixed');
  const disliked = R.el('span', undefined, 'opinion-disliked');
  liked.style.width = `${shares.liked}%`;
  mixed.style.width = `${shares.mixed}%`;
  disliked.style.width = `${shares.disliked}%`;
  bar.append(liked, mixed, disliked);
  return bar;
};
R.opinionDisplay = function(stats) {
  const shares = R.shares(stats);
  const display = R.el('span', undefined, 'opinion-display');
  display.append(
    R.el('span', `👍 ${R.percentText(shares.liked)} liked`, 'liked-label'),
    R.opinionBar(stats),
    R.el('span', `👎 ${R.percentText(shares.disliked)} disliked`, 'disliked-label'));
  return display;
};
R.scorePill = function(net, mode = R.scoreMode) {
  const score = R.el('span', net === null ? 'Fair score unavailable' : `Score ${R.netText(net)}`, `score-pill ${net < 0 ? 'negative' : 'positive'}`);
  score.setAttribute('title', mode === 'fair' ? 'Fair score = weighted difference from community baselines' : 'Score = liked % − disliked %');
  return score;
};
R.todayScoreCell = function(model) {
  const cell = R.el('span', undefined, 'rank-24h');
  const today = model.todayStats || {opinions: 0, net: 0};
  cell.append(R.el('span', '24h', 'rank-24h-label'));
  if (today.opinions < 8) {
    const unavailable = R.el('span', '—', 'rank-24h-value muted');
    unavailable.setAttribute('title', 'fewer than 8 opinions in 24h');
    cell.append(unavailable);
    return cell;
  }
  if (today.net === null || model.stats.net === null) {
    const unavailable = R.el('span', 'Fair score unavailable', 'rank-24h-value muted');
    unavailable.setAttribute('title', 'Fair score unavailable for this comparison');
    cell.append(unavailable);
    return cell;
  }
  const value = R.el('span', `Score ${R.netText(today.net)}`, 'rank-24h-value');
  const difference = Math.round(today.net - model.stats.net);
  const change = difference > 0 ? `▲${difference}` : difference < 0 ? `▼${Math.abs(difference)}` : '=0';
  const delta = R.el('span', change, 'rank-24h-delta');
  delta.setAttribute('title', `24h score ${R.netText(today.net)} vs 7d ${R.netText(model.stats.net)}`);
  cell.setAttribute('aria-label', `24h Score ${R.netText(today.net)}, ${today.opinions} opinions, ${change} versus 7d`);
  cell.append(value, delta);
  return cell;
};
R.quote = function(items, label) {
  const best = items.filter(row => row.kind === 'comment' && row.label === label)
    .sort((a, b) => (b.score || 0) - (a.score || 0))[0];
  const quote = R.el('blockquote', undefined, `quote-line ${label}`);
  if (!best) { quote.textContent = `No ${label} comment available.`; return quote; }
  const anchor = R.el('a', `“${best.text || ''}”`);
  if (/^https?:\/\//i.test(best.link || '')) anchor.href = best.link;
  anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
  if (R.sourceBadge) quote.append(R.sourceBadge(best));
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
R.versionDetail = function(subject, version) {
  const stat = R.stats(version.items);
  const row = R.el('div', undefined, 'version-row');
  const meta = R.el('span', `${version.name} · ${version.mentions} mentions`, 'version-name');
  const trend = R.trendArrow(subject, version.name);
  if (trend) meta.append(trend);
  row.append(meta, R.opinionDisplay(stat), R.scorePill(stat.net, 'raw'),
    R.el('span', `${stat.opinions} people's opinions`, 'opinion-count'));
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
    item.append(R.el('span', `▲${row.thread_score || 0} · ${R.communityLabel ? R.communityLabel(row) : `r/${row.sub || ''}`} `, 'muted'));
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
  R.versionRows(model.items).forEach(version => versions.append(R.versionDetail(model.subject, version)));
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
  const trend = R.trendArrow(model.subject, null);
  if (trend) identity.append(trend);
  summary.append(identity, R.scorePill(model.stats.net));
  if (R.rangeDays === 1) summary.append(R.todayScoreCell(model));
  summary.append(R.el('span', `${model.stats.opinions} people's opinions`, 'opinion-count'),
    R.opinionDisplay(model.stats));
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
R.todayChoice = function(today, week) {
  const fairAvailable = model => model && (R.scoreMode !== 'fair' || model.fairNet !== null);
  if (today && today.stats.opinions >= 8 && fairAvailable(today)) return {...today, period: '24h'};
  if (week && week.stats.opinions >= 20 && fairAvailable(week)) return {...week, period: '7d'};
  return null;
};
R.compareTodayChoices = (a, b) => b.stats.net - a.stats.net ||
  b.stats.opinions - a.stats.opinions || a.subject.localeCompare(b.subject);
R.renderUseToday = function(weekModels, todayModels) {
  const target = R.$('use-today');
  target.replaceChildren(R.el('h2', 'Use today', 'strip-title'));
  const weeks = new Map(weekModels.map(model => [model.subject, model]));
  const todays = new Map(todayModels.map(model => [model.subject, model]));
  const subjects = new Set([...weeks.keys(), ...todays.keys()]);
  const picks = [...subjects].map(subject => R.todayChoice(todays.get(subject), weeks.get(subject))).filter(Boolean);
  Object.entries(R.zones).forEach(([zone, title]) => {
    const ranked = picks.filter(model => model.zone === zone).sort(R.compareTodayChoices);
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
      const shares = R.shares(best.stats);
      const score = R.el('div', undefined, 'use-score-block');
      const detail = R.el('div', undefined, 'use-score-detail');
      const scoreLabel = R.scoreMode === 'fair' ? 'Fair score (vs community average)' : 'Score (liked − disliked)';
      detail.append(R.el('span', `${scoreLabel}${best.period === '7d' ? ' (7d)' : ''}`, 'use-score-label'),
        R.el('span', `👍 ${R.percentText(shares.liked)} · 👎 ${R.percentText(shares.disliked)}`, 'use-distribution'));
      score.append(R.el('strong', R.netText(best.stats.net), `use-net ${best.stats.net < 0 ? 'negative' : 'positive'}`), detail);
      card.append(score, R.el('p', `${best.stats.opinions} people's opinions`, 'use-opinions'), R.quote(best.items, 'praise'));
    }
    const runner = ranked[1];
    const runnerPeriod = runner && runner.period === '7d' ? ' (7d)' : '';
    card.append(R.el('p', runner ? `runner-up: ${runner.subject} Score ${R.netText(runner.stats.net)}${runnerPeriod}` : 'runner-up: none yet', 'runner-up'));
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
R.renderZones = function(models, minimum = R.rankingMinimum()) {
  const target = R.$('zones');
  target.replaceChildren();
  target.append(R.el('p', '👍 liked · mixed · 👎 disliked — share of opinions about each model for coding. ' + (R.scoreMode === 'fair' ? 'Fair score = difference from community baselines.' : 'Score = liked − disliked.'), 'ranking-legend legend'));
  Object.entries(R.zones).forEach(([zone, title]) => {
    const section = R.el('section', undefined, 'zone-section');
    section.append(R.el('h2', title));
    const current = models.filter(model => model.zone === zone);
    const visible = current.filter(R.matches);
    const ranked = visible.filter(model => R.rankable(model, minimum)).sort(R.compareModels);
    const low = visible.filter(model => !R.rankable(model, minimum)).sort((a, b) => b.stats.mentions - a.stats.mentions);
    if (ranked.length) ranked.forEach(model => section.append(R.rankRow(model, R.matchVersion(model))));
    if (low.length) {
      const group = R.el('details', undefined, 'low-data');
      group.open = R.$('expand').checked || Boolean(R.query && low.some(R.matchVersion)) || Boolean(R.selected);
      group.append(R.el('summary', `Not enough data yet (${low.length})`));
      low.forEach(model => group.append(R.rankRow(model, R.matchVersion(model))));
      section.append(group);
    }
    if (!visible.length) section.append(R.el('p', 'No matching models in this zone.', 'muted'));
    target.append(section);
  });
};
R.renderRanking = function() {
  const rows = R.rowsForRange();
  const todayRows = R.rowsForRange(1);
  const weekRows = R.rowsForRange(7);
  const rankingRows = R.rangeDays === 1 ? weekRows : rows;
  const models = R.modelsFor(rankingRows);
  const weekModels = R.rangeDays === 7 ? models : R.modelsFor(weekRows);
  const todayModels = R.modelsFor(todayRows);
  if (R.applyFairScores) {
    R.applyFairScores(models, rankingRows);
    if (weekModels !== models) R.applyFairScores(weekModels, weekRows);
    R.applyFairScores(todayModels, todayRows);
  }
  if (R.rangeDays === 1) {
    const bySubject = new Map(todayModels.map(model => [model.subject, model.stats]));
    models.forEach(model => { model.todayStats = bySubject.get(model.subject) || {opinions: 0, net: 0}; });
  }
  R.chartModels = R.rangeDays === 1 ? todayModels : models;
  R.renderUseToday(weekModels, todayModels);
  R.renderChips(models);
  R.renderZones(models, R.rangeDays === 1 ? 20 : R.rankingMinimum());
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
