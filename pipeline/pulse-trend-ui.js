'use strict';
const U = globalThis.Pulse;

U.trendName = function(alert) {
  return alert.name || (alert.version ? `${alert.subject} · ${alert.version}` : alert.subject);
};
U.trendArrow = function(subject, version) {
  const alert = (U.trendAlerts || []).find(item => item.subject === subject && item.version === version &&
    (item.kind === 'drop' || item.kind === 'rise'));
  if (!alert) return null;
  const delta = Number(alert.delta);
  const points = Number.isFinite(delta) ? Math.abs(Math.round(delta)) : 0;
  const rising = alert.kind === 'rise';
  const arrow = U.el('span', `${rising ? '▲' : '▼'}${points}`, `trend-arrow trend-${alert.kind}`);
  const direction = rising ? 'up' : 'down';
  arrow.setAttribute('title', `Score ${direction} ${points} points in the last 2 days`);
  arrow.setAttribute('aria-label', `Score ${direction} ${points} points`);
  return arrow;
};
U.trendMessage = function(alert) {
  const name = U.trendName(alert);
  if (alert.kind === 'new') return `🆕 Suddenly talked about: ${name}`;
  const before = U.netText(alert.before.net), now = U.netText(alert.now.net);
  if (alert.kind === 'drop') {
    return `⚠️ Going sour: ${name} — score ${before} → ${now} in the last 2 days (${alert.now.opinions} opinions)`;
  }
  return `📈 Heating up: ${name} — ${before} → ${now} in the last 2 days (${alert.now.opinions} opinions)`;
};
U.trendQuoteNode = function(alert) {
  const row = alert.quote;
  if (!row || !/^https?:\/\//i.test(row.link || '')) return null;
  const label = alert.kind === 'drop' ? 'Top complaint: ' : 'Top praise: ';
  const line = U.el('p', undefined, 'trend-quote-line');
  line.append(U.el('span', label, 'trend-quote-label'));
  const link = U.el('a', `“${row.text || 'View comment'}”`, 'trend-quote');
  link.setAttribute('href', row.link);
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  if (U.sourceBadge) line.append(U.sourceBadge(row));
  line.append(link, U.el('span', `▲${row.score || 0}`, 'trend-comment-score muted'));
  return line;
};
U.renderTrends = function() {
  const rows = U.rowsForMain ? U.rowsForMain(U.rows) :
    U.filterSources ? U.filterSources(U.rows) : U.rows;
  U.trendAlerts = U.trendsFor(rows, U.endDate);
  const target = U.$('trend-alerts');
  if (!target) return U.trendAlerts;
  target.replaceChildren(U.el('h2', 'Trend alerts'));
  const visible = U.trendAlerts.slice(0, 5);
  if (!visible.length) {
    target.append(U.el('p', 'No big mood swings in the last 2 days.', 'trend-empty'));
    return U.trendAlerts;
  }
  visible.forEach(alert => {
    const item = U.el('article', undefined, `trend-alert trend-${alert.kind}`);
    item.append(U.el('p', U.trendMessage(alert), 'trend-message'));
    const quote = U.trendQuoteNode(alert);
    if (quote) item.append(quote);
    target.append(item);
  });
  return U.trendAlerts;
};
