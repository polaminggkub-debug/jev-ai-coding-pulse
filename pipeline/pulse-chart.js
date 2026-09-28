'use strict';
const C = globalThis.Pulse;
C.svgLogo = function(name, x, y) {
  const key = C.logoKey(name);
  const source = key && C.logos[key];
  const match = source && source.match(/<svg\b([^>]*)>([\s\S]*)<\/svg>/i);
  if (!match) {
    const letter = C.escape([...String(name || '?')][0].toUpperCase());
    return `<circle cx="${x + 12}" cy="${y + 12}" r="11" fill="var(--card)" stroke="var(--line)"/><text x="${x + 12}" y="${y + 16}" text-anchor="middle" class="fallback-letter">${letter}</text>`;
  }
  const view = match[1].match(/\bviewBox=["']([^"']+)["']/i);
  const body = match[2].replace(/<title[^>]*>[\s\S]*?<\/title>/ig, '');
  return `<svg x="${x}" y="${y}" width="24" height="24" viewBox="${view ? view[1] : '0 0 24 24'}" color="var(--fg)" aria-hidden="true">${body}</svg>`;
};
C.shortLabel = function(subject) {
  const names = {'GPT / ChatGPT': 'GPT', 'Xiaomi MiMo': 'MiMo'};
  return names[subject] || subject.replace(/^Claude\s+/, '');
};
C.overlaps = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
C.labelCandidate = function(point, dx, dy) {
  const label = C.shortLabel(point.model.subject);
  const width = label.length * 6.5;
  const anchor = dx < 0 ? 'end' : 'start';
  const x = point.x + dx, y = point.y + dy;
  return {label, x, y, anchor, left: anchor === 'end' ? x - width : x,
    right: anchor === 'end' ? x : x + width, top: y - 11, bottom: y + 3};
};
C.placeLabels = function(points, width, top, bottom) {
  const occupied = points.map(point => ({left: point.x - 13, right: point.x + 13,
    top: point.y - 13, bottom: point.y + 13}));
  return points.map(point => {
    const candidates = [[17, 4], [-17, 4], [17, -14], [-17, -14], [17, 22], [-17, 22],
      [0, -19], [0, 29], [17, -30], [-17, 38]].map(([dx, dy]) => C.labelCandidate(point, dx, dy));
    const cost = box => occupied.filter(other => C.overlaps(box, other)).length * 100 +
      (box.left < 4 || box.right > width - 4 || box.top < top - 20 || box.bottom > bottom + 15 ? 10000 : 0);
    candidates.sort((a, b) => cost(a) - cost(b));
    const chosen = candidates[0];
    occupied.push(chosen);
    return chosen;
  });
};
C.pointLabel = function(label, x, y) {
  if (!label) return '';
  const dx = label.x - x + 12, dy = label.y - y + 12;
  const connector = Math.abs(label.y - y) > 10 ?
    `<line x1="12" y1="12" x2="${dx}" y2="${dy - 4}" class="label-connector"/>` : '';
  return `${connector}<text class="point-label" x="${dx}" y="${dy}" text-anchor="${label.anchor}">${C.escape(label.label)}</text>`;
};
C.chartShares = function(model) {
  const total = model.stats.opinions || 1;
  return {liked: Math.round(100 * model.stats.praise / total),
    disliked: Math.round(100 * model.stats.complaint / total)};
};
C.chartZoneClass = function(model) {
  return ({us: 'zone-us', tool: 'zone-tool', open: 'zone-open'})[model.zone] || 'zone-open';
};
C.chartPoint = function(model, x, y, label) {
  const shares = C.chartShares(model);
  const tip = `${model.subject} · 👍 ${shares.liked}% · 👎 ${shares.disliked}% · Score ${C.netText(model.stats.net)} · ${model.stats.opinions} opinions`;
  const safe = C.escape(tip);
  return `<g class="point ${C.chartZoneClass(model)}" transform="translate(${x - 12} ${y - 12})" tabindex="0" role="button" aria-label="${safe}" data-tip="${safe}"><title>${safe}</title><circle class="zone-ring" cx="12" cy="12" r="13.5"/>${C.svgLogo(model.subject, 0, 0)}${C.pointLabel(label, x, y)}</g>`;
};
C.chartLegend = function() {
  const keys = [['us', 'zone-us'], ['tool', 'zone-tool'], ['open', 'zone-open']];
  const items = keys.map(([zone, color]) => `<li><span class="zone-swatch ${color}" aria-hidden="true"></span>${C.escape(C.zones[zone])}</li>`).join('');
  return `<ul class="chart-zone-legend" aria-label="Model zones">${items}</ul>`;
};
C.chartTicks = function(max, left, width, top, bottom, height) {
  const minimum = C.rankingMinimum();
  const ticks = [8, 20, 50, 100, 250, 500, 1000].filter(n => n >= minimum && n < max);
  ticks.push(max);
  return ticks.map((value, index) => {
    const x = max === minimum ? left + width / 2 : left + Math.log(value / minimum) / Math.log(max / minimum) * width;
    const label = index === ticks.length - 1 && max > 1000 ? `${Math.round(max / 1000)}k` : value;
    return `<line x1="${x}" y1="${top}" x2="${x}" y2="${bottom}" class="gridline"/><text x="${x}" y="${bottom + 18 * height / 430}" text-anchor="middle" class="tick">${label}</text>`;
  }).join('');
};
C.renderChart = function(models) {
  const target = C.$('chart');
  const rankable = models.filter(model => C.rankable(model) && C.matches(model));
  const styles = globalThis.getComputedStyle?.(target);
  const padding = styles ? parseFloat(styles.paddingLeft) + parseFloat(styles.paddingRight) : 0;
  const width = Math.max(1, Math.round((target.clientWidth || 760) - padding));
  const height = Math.max(320, Math.min(430, 430 * width / 760));
  const scale = height / 430;
  const left = width < 500 ? 42 : 64, right = width < 500 ? 14 : 28;
  const top = 52 * scale, bottom = 356 * scale, plotWidth = width - left - right;
  const midX = left + plotWidth / 2, midY = (top + bottom) / 2;
  const minimum = C.rankingMinimum();
  const max = Math.max(minimum, ...rankable.map(model => model.stats.opinions));
  const positions = rankable.map(model => {
    const ratio = max === minimum ? 0.5 : Math.log(model.stats.opinions / minimum) / Math.log(max / minimum);
    const x = left + ratio * plotWidth;
    const bound = C.scoreMode === 'fair' ? 200 : 100;
    const y = top + (bound - model.stats.net) / (2 * bound) * (bottom - top);
    return {model, x, y};
  });
  const labels = C.placeLabels(positions, width, top, bottom);
  const points = positions.map((point, index) => C.chartPoint(point.model, point.x, point.y, labels[index])).join('');
  const rightEdge = width - right;
  const svg = `<svg class="buzz-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Buzz versus love scatter chart">
    <text x="${left}" y="${28 * scale}" class="quadrant">Loved, quiet</text><text x="${rightEdge}" text-anchor="end" y="${28 * scale}" class="quadrant">Loved &amp; hot</text>
    <text x="${left}" y="${394 * scale}" class="quadrant">Ignore</text><text x="${rightEdge}" text-anchor="end" y="${394 * scale}" class="quadrant">Hot but hated</text>
    <rect x="${left}" y="${top}" width="${plotWidth}" height="${midY - top}" class="score-positive-zone"/><rect x="${left}" y="${midY}" width="${plotWidth}" height="${bottom - midY}" class="score-negative-zone"/>
    <line x1="${left}" y1="${top}" x2="${left}" y2="${bottom}" class="axis"/><line x1="${left}" y1="${bottom}" x2="${rightEdge}" y2="${bottom}" class="axis"/>
    <line x1="${left}" y1="${midY}" x2="${rightEdge}" y2="${midY}" class="zero-line"/><line x1="${midX}" y1="${top}" x2="${midX}" y2="${bottom}" class="gridline"/>
    <text x="${left + 6}" y="${top + 18 * scale}" class="score-half-label score-half-positive">${C.scoreMode === 'fair' ? 'Above community average' : '👍 more liked'}</text><text x="${left + 6}" y="${bottom - 8 * scale}" class="score-half-label score-half-negative">${C.scoreMode === 'fair' ? 'Below community average' : '👎 more disliked'}</text>
    <text x="${left - 6}" y="${top + 4}" text-anchor="end" class="tick">+${C.scoreMode === 'fair' ? 200 : 100}</text><text x="${left - 6}" y="${midY + 4}" text-anchor="end" class="tick">0</text><text x="${left - 6}" y="${bottom + 4}" text-anchor="end" class="tick">−${C.scoreMode === 'fair' ? 200 : 100}</text>
    ${C.chartTicks(max, left, plotWidth, top, bottom, height)}<text x="${width / 2}" y="${418 * scale}" text-anchor="middle" class="axis-label">Opinions (log scale)</text>
    <text x="14" y="${height / 2}" text-anchor="middle" class="axis-label" transform="rotate(-90 14 ${height / 2})">${C.scoreMode === 'fair' ? 'Fair score (vs community average)' : 'Score (liked − disliked)'}</text>${points}</svg>`;
  const hint = rankable.length ? 'Hover, focus, or tap a point to inspect it.' : 'No rankable models in this period.';
  target.innerHTML = `<p id="chart-tip" class="chart-tip" role="status">${hint}</p>${svg}${C.chartLegend()}`;
  C.bindChartPoints(target);
};
C.bindChartPoints = function(target) {
  const points = target.querySelectorAll ? target.querySelectorAll('.point') : [];
  points.forEach(point => {
    const show = () => { C.$('chart-tip').textContent = point.getAttribute('data-tip'); };
    ['mouseenter', 'focus', 'click'].forEach(event => point.addEventListener(event, show));
  });
};
C.render = function() {
  C.renderTime();
  if (C.page === 'sources') {
    C.renderSourceOverview(C.rowsForRange());
    C.renderCommunityHeatmap(C.rowsForRange());
    return;
  }
  C.renderTrends();
  C.chartModels = C.renderRanking();
  C.renderChart(C.chartModels);
};
C.bindResize = function() {
  if (!globalThis.addEventListener || !globalThis.setTimeout) return;
  globalThis.addEventListener('resize', () => {
    globalThis.clearTimeout(C.resizeTimer);
    C.resizeTimer = globalThis.setTimeout(() => C.renderChart(C.chartModels || []), 120);
  });
};
C.init = function() {
  C.bindTime();
  if (C.page !== 'sources') { C.bindSelection(); C.bindResize(); }
  if (C.bindSourceControls) C.bindSourceControls();
  C.$('theme').addEventListener('click', () => {
    const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' :
      matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.dataset.theme = dark ? 'light' : 'dark';
  });
  C.render();
};
C.init();
