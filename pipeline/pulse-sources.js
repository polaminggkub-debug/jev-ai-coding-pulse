'use strict';
const S = globalThis.Pulse;
if (S) {
  S.sourceNames = {reddit: 'Reddit', hn: 'Hacker News', github: 'GitHub',
    bluesky: 'Bluesky', devto: 'Dev.to', lobsters: 'Lobsters'};
  S.sourceIcons = {reddit: '🔴', hn: '🟧', github: '🐙', bluesky: '🦋', devto: '✍️', lobsters: '🦞'};
  S.sourceOf = row => S.sourceNames[row && row.source] ? row.source : 'reddit';
  S.filterSources = function(rows) {
    return rows.filter(row => S.sourceFilter === 'all' || S.sourceOf(row) === S.sourceFilter);
  };
  S.sourceBadge = function(row) {
    const source = S.sourceOf(row), badge = S.el('span', S.sourceIcons[source], 'source-icon');
    badge.setAttribute('aria-label', S.sourceNames[source]);
    badge.setAttribute('title', S.sourceNames[source]);
    return badge;
  };
  S.communityLabel = function(row) {
    const source = S.sourceOf(row), raw = String(row.community || row.sub || '').replace(/^r\//i, '');
    if (source === 'reddit') return `r/${raw || 'Reddit'}`;
    return raw || S.sourceNames[source];
  };
  S.opinionCount = rows => rows.filter(row => ['praise', 'mixed', 'complaint'].includes(row.label)).length;
  S.sourceCountRow = function(target, label, count, max, cls) {
    const row = S.el('div', undefined, `source-count-row ${cls || ''}`.trim());
    const name = S.el('span', label, 'source-count-name'), number = S.el('strong', String(count), 'source-count-value');
    const track = S.el('span', undefined, 'source-count-track'), fill = S.el('span', undefined, 'source-count-fill');
    fill.style.width = `${max ? count * 100 / max : 0}%`;
    track.append(fill); row.append(name, track, number); target.append(row);
  };
  S.renderSourceOverview = function(rows) {
    const target = S.$('source-chart'), communities = S.$('reddit-communities');
    if (!target || !communities) return;
    const groups = Object.fromEntries(Object.keys(S.sourceNames).map(source => [source, []]));
    rows.forEach(row => groups[S.sourceOf(row)].push(row));
    const totals = Object.fromEntries(Object.entries(groups).map(([source, items]) => [source, S.opinionCount(items)]));
    const max = Math.max(0, ...Object.values(totals));
    target.replaceChildren();
    Object.entries(S.sourceNames).forEach(([source, label]) =>
      S.sourceCountRow(target, `${S.sourceIcons[source]} ${label}`, totals[source], max, `source-${source}`));
    const byCommunity = new Map();
    groups.reddit.forEach(row => {
      const label = S.communityLabel(row), bucket = byCommunity.get(label) || [];
      bucket.push(row); byCommunity.set(label, bucket);
    });
    const ranked = [...byCommunity].map(([label, items]) => ({label, count: S.opinionCount(items)}))
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)).slice(0, 8);
    communities.replaceChildren();
    if (!ranked.length) communities.append(S.el('p', 'No Reddit opinions in this range and filter.', 'muted'));
    ranked.forEach(item => S.sourceCountRow(communities, item.label, item.count, ranked[0].count, 'reddit-community'));
  };
  S.bindSourceControls = function() {
    const source = S.$('source-filter'), mode = S.$('score-mode');
    if (source) source.addEventListener('change', () => {
      S.sourceFilter = S.sourceNames[source.value] ? source.value : 'all';
      S.clearFilters(); S.render();
    });
    if (mode) mode.addEventListener('change', () => {
      S.scoreMode = mode.value === 'fair' ? 'fair' : 'raw'; S.render();
    });
  };
}
