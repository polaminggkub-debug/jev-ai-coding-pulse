'use strict';
const Community = globalThis.Pulse;
if (Community) {
  Community.communityKey = row => `${Community.sourceOf(row)}\u0000${Community.communityLabel(row)}`;
  Community.communityGroups = function(rows) {
    const groups = new Map();
    rows.forEach(row => {
      const key = Community.communityKey(row), group = groups.get(key) || {key, label: Community.communityLabel(row), items: []};
      group.items.push(row); groups.set(key, group);
    });
    return [...groups.values()].map(group => ({...group, stats: Community.stats(group.items)}));
  };
  Community.fairScore = function(items, baseline) {
    const stats = Community.stats(items);
    return stats.opinions >= 10 ? {count: stats.opinions, delta: stats.net - baseline, net: stats.net} : null;
  };
  Community.applyFairScores = function(models, rows) {
    const communities = Community.communityGroups(rows), cells = new Map();
    communities.forEach(group => cells.set(group.key, new Map()));
    rows.forEach(row => {
      const group = communities.find(item => item.key === Community.communityKey(row));
      if (!group) return;
      const family = cells.get(group.key), items = family.get(row.subject) || [];
      items.push(row); family.set(row.subject, items);
    });
    models.forEach(model => {
      let weighted = 0, weight = 0;
      communities.forEach(group => {
        const items = cells.get(group.key).get(model.subject) || [], cell = Community.fairScore(items, group.stats.net);
        if (cell) { weighted += cell.delta * cell.count; weight += cell.count; }
      });
      model.rawNet = model.stats.net;
      model.fairNet = weight ? weighted / weight : null;
      model.stats.net = Community.scoreMode === 'fair' ? model.fairNet : model.rawNet;
    });
    return models;
  };
  Community.communityCell = function(group, subject) {
    const items = group.items.filter(row => row.subject === subject), stats = Community.stats(items);
    return {items, stats, delta: stats.net - group.stats.net};
  };
  Community.heatColor = value => {
    const strength = Math.min(100, Math.abs(value)) / 100;
    return value >= 0 ? `rgba(36,115,68,${0.06 + strength * 0.28})` : `rgba(181,51,46,${0.06 + strength * 0.28})`;
  };
  Community.heatCell = function(cell, baseline) {
    const node = Community.el('td', undefined, 'heat-cell');
    if (!cell.stats.opinions) { node.textContent = '—'; return node; }
    const value = Community.el('strong', Community.netText(cell.stats.net), 'heat-score');
    const delta = Community.el('span', `vs avg ${Community.netText(cell.delta)}`, 'heat-delta');
    node.append(value, delta); node.style.backgroundColor = Community.heatColor(cell.stats.net);
    node.setAttribute('title', `${cell.stats.opinions} opinions · community average ${Community.netText(baseline)}`);
    node.setAttribute('aria-label', `Score ${Community.netText(cell.stats.net)}, vs community average ${Community.netText(cell.delta)}, ${cell.stats.opinions} opinions`);
    return node;
  };
  Community.communityTastes = function(group, families) {
    const scored = families.map(subject => ({subject, ...Community.communityCell(group, subject)}))
      .filter(cell => cell.stats.opinions >= 10).sort((a, b) => b.stats.net - a.stats.net || a.subject.localeCompare(b.subject));
    return {
      loves: scored[0] || null,
      hates: scored[scored.length - 1] || null
    };
  };
  Community.renderCommunityHeatmap = function(rows) {
    const target = Community.$('community-heatmap');
    if (!target) return;
    const communities = Community.communityGroups(rows).filter(group => group.stats.opinions >= 30)
      .sort((a, b) => b.stats.opinions - a.stats.opinions || a.label.localeCompare(b.label));
    const families = Community.familiesFor(rows).map(subject => ({subject, count: Community.stats(Community.rowsFor(rows, subject)).opinions}))
      .filter(item => item.count >= 20).sort((a, b) => a.subject.localeCompare(b.subject));
    target.replaceChildren();
    if (!communities.length || !families.length) {
      target.append(Community.el('p', 'Need a community with 30 opinions and a family with 20 in this range.', 'muted'));
      return;
    }
    const table = Community.el('table', undefined, 'community-table'), head = Community.el('thead'), heading = Community.el('tr');
    heading.append(Community.el('th', 'Community'), Community.el('th', 'Opinions'), Community.el('th', 'Loves most / hates most'));
    families.forEach(item => heading.append(Community.el('th', item.subject, 'family-head')));
    head.append(heading); table.append(head);
    const body = Community.el('tbody');
    communities.forEach(group => body.append(Community.communityHeatRow(group, families)));
    table.append(body);
    const wrap = Community.el('div', undefined, 'community-table-wrap'); wrap.append(table); target.append(wrap);
  };
  Community.communityHeatRow = function(group, families) {
    const row = Community.el('tr'), first = Community.el('th', undefined, 'community-name');
    first.setAttribute('scope', 'row'); first.append(Community.sourceBadge(group.items[0]), Community.el('span', group.label));
    const tastes = Community.communityTastes(group, families.map(item => item.subject));
    const tasteText = taste => taste ? `${taste.subject} ${Community.netText(taste.stats.net)}` : '—';
    row.append(first, Community.el('td', String(group.stats.opinions), 'community-count'),
      Community.el('td', `loves ${tasteText(tastes.loves)} · hates ${tasteText(tastes.hates)}`, 'community-tastes'));
    families.forEach(item => row.append(Community.heatCell(Community.communityCell(group, item.subject), group.stats.net)));
    return row;
  };
}
