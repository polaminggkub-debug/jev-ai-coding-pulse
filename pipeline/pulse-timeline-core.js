'use strict';
const L = globalThis.Pulse;
if (L) {
  L.timelineDayMs = 86400000;
  L.timelineMinWindow = 5;
  L.timelineMinMover = 15;
  L.timelineDayOf = function(value) {
    if (value === null || value === undefined || value === '') return null;
    const raw = String(value).trim();
    const numeric = /^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(raw);
    const number = numeric ? Number(raw) : null;
    const date = new Date(numeric ? number * (Math.abs(number) > 1e11 ? 1 : 1000) : raw);
    return Number.isFinite(date.getTime()) ? date.toISOString().slice(0, 10) : null;
  };
  L.timelineDateOf = function(row) {
    for (const key of ['created_utc', 'parent_created_utc', 'post_created_utc', 'judged_at', 'date']) {
      const day = L.timelineDayOf(row && row[key]);
      if (day) return day;
    }
    return null;
  };
  L.timelineRows = function(rows) {
    return (Array.isArray(rows) ? rows : []).map(row => ({row, day: L.timelineDateOf(row)}))
      .filter(item => item.day && item.row && item.row.subject &&
        ['praise', 'mixed', 'complaint', 'no_opinion'].includes(item.row.label));
  };
  L.timelineStats = function(rows) {
    const praise = rows.filter(row => row.label === 'praise').length;
    const mixed = rows.filter(row => row.label === 'mixed').length;
    const complaint = rows.filter(row => row.label === 'complaint').length;
    const opinions = praise + mixed + complaint;
    return {praise, mixed, complaint, opinions, net: opinions ? (praise - complaint) * 100 / opinions : 0};
  };
  L.timelineAddDays = (day, count) => new Date(Date.parse(`${day}T00:00:00Z`) + count * L.timelineDayMs).toISOString().slice(0, 10);
  L.timelineMonthBounds = function(month) {
    const [year, number] = month.split('-').map(Number);
    const end = new Date(Date.UTC(year, number, 0)).toISOString().slice(0, 10);
    return {start: `${month}-01`, end};
  };
  L.timelineMonths = items => [...new Set(items.map(item => item.day.slice(0, 7)))].sort();
  L.timelineRange = function(latest, mode, month) {
    if (mode === 'month' && month) return {...L.timelineMonthBounds(month), month, mode};
    return {start: L.timelineAddDays(latest, -29), end: latest, month, mode: '30'};
  };
  L.timelineDates = function(start, end) {
    const dates = [];
    for (let day = start; day <= end; day = L.timelineAddDays(day, 1)) dates.push(day);
    return dates;
  };
  L.timelineWindow = function(items, subject, end) {
    const start = L.timelineAddDays(end, -6);
    return L.timelineStats(items.filter(item => item.row.subject === subject && item.day >= start && item.day <= end)
      .map(item => item.row));
  };
  L.timelineAllModels = function(items, range) {
    const within = items.filter(item => item.day >= range.start && item.day <= range.end);
    const subjects = [...new Set(within.map(item => item.row.subject))];
    return subjects.map(subject => {
      const rows = within.filter(item => item.row.subject === subject).map(item => item.row);
      return {subject, zone: L.zoneFor(subject, rows), stats: L.timelineStats(rows)};
    }).filter(model => model.stats.opinions > 0)
      .sort((a, b) => b.stats.opinions - a.stats.opinions || a.subject.localeCompare(b.subject));
  };
  L.timelineModels = (items, range) => L.timelineAllModels(items, range).slice(0, 12);
  L.timelineCaption = function(items, models, day) {
    const oldDay = L.timelineAddDays(day, -3), changes = [];
    models.forEach(model => {
      const now = L.timelineWindow(items, model.subject, day), before = L.timelineWindow(items, model.subject, oldDay);
      const delta = now.net - before.net;
      if (now.opinions >= L.timelineMinMover && before.opinions >= L.timelineMinMover && Math.abs(delta) >= 15) {
        changes.push({subject: model.subject, delta});
      }
    });
    changes.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta) || a.subject.localeCompare(b.subject));
    const mover = changes[0];
    if (!mover) return 'No family moved 15+ points over the last 3 days.';
    const delta = Math.round(mover.delta), points = `${delta > 0 ? '+' : '−'}${Math.abs(delta)}`;
    return delta > 0 ? `📈 ${mover.subject} heating up (${points} in 3 days)` :
      `⚠️ ${mover.subject} going sour (${points} in 3 days)`;
  };
  L.timelineSvgZone = zone => `zone-${({us: 'us', tool: 'tool', open: 'open'})[zone] || 'open'}`;
  L.timelineRaceValues = function(items, models, day) {
    return models.map(model => ({...model, stats: L.timelineWindow(items, model.subject, day)})).sort((a, b) =>
      Number(b.stats.opinions > 0) - Number(a.stats.opinions > 0) || b.stats.net - a.stats.net ||
      b.stats.opinions - a.stats.opinions || a.subject.localeCompare(b.subject));
  };
  L.timelineSeries = (items, models, dates) => models.map(model => ({...model,
    points: dates.map(day => ({day, ...L.timelineWindow(items, model.subject, day)}))}));
  L.timelinePath = function(series, dates, width, height) {
    const left = 42, right = width - 48, top = 18, bottom = height - 52;
    const x = index => dates.length < 2 ? (left + right) / 2 : left + index * (right - left) / (dates.length - 1);
    const y = score => top + (100 - score) * (bottom - top) / 200;
    const points = series.points.map((point, index) => ({point, index}));
    const solid = [], dashed = [], observed = points.filter(item => item.point.opinions > 0);
    for (let index = 0; index < points.length - 1; index++) {
      const first = points[index], next = points[index + 1];
      if (!first.point.opinions || !next.point.opinions) continue;
      const path = `M${x(index).toFixed(1)} ${y(first.point.net).toFixed(1)} L${x(index + 1).toFixed(1)} ${y(next.point.net).toFixed(1)}`;
      (first.point.opinions >= L.timelineMinWindow && next.point.opinions >= L.timelineMinWindow ? solid : dashed).push(path);
    }
    const last = observed[observed.length - 1];
    const lone = observed.length === 1 ? {x: x(last.index), y: y(last.point.net), low: last.point.opinions < L.timelineMinWindow} : null;
    return {solid: solid.join(' '), dashed: dashed.join(' '), lone,
      last: last ? {x: x(last.index), y: y(last.point.net)} : null};
  };
  L.timelineThreads = function(rows) {
    const threads = new Map(), comments = new Set();
    rows.forEach(row => {
      if (!row.thread_url || (row.kind && row.kind !== 'comment')) return;
      const id = row.id || row.link || `${row.thread_url}:${row.subject}`;
      const thread = threads.get(row.thread_url) || {...row, count: 0};
      if (!comments.has(id)) { thread.count++; comments.add(id); }
      threads.set(row.thread_url, thread);
    });
    return [...threads.values()].sort((a, b) => b.count - a.count || (b.thread_score || 0) - (a.thread_score || 0) || a.thread_url.localeCompare(b.thread_url)).slice(0, 5);
  };
  L.timelineInsights = function(items, month) {
    const bounds = L.timelineMonthBounds(month), monthItems = items.filter(item => item.day >= bounds.start && item.day <= bounds.end);
    const models = L.timelineAllModels(monthItems, bounds), firstEnd = L.timelineAddDays(bounds.start, 6);
    const observedEnd = monthItems.map(item => item.day).sort().slice(-1)[0] || bounds.end;
    const lastStart = L.timelineAddDays(observedEnd, -6);
    const movers = models.map(model => {
      const first = L.timelineStats(monthItems.filter(item => item.row.subject === model.subject && item.day <= firstEnd).map(item => item.row));
      const last = L.timelineStats(monthItems.filter(item => item.row.subject === model.subject && item.day >= lastStart).map(item => item.row));
      return {...model, first, last, delta: last.net - first.net};
    }).filter(model => model.first.opinions >= L.timelineMinWindow && model.last.opinions >= L.timelineMinWindow);
    const zoneBest = Object.keys(L.zones).map(zone => ({zone, model: models.filter(item => item.zone === zone && item.stats.opinions >= 20)
      .sort((a, b) => b.stats.net - a.stats.net || b.stats.opinions - a.stats.opinions)[0] || null}));
    const eligible = models.filter(model => model.stats.opinions >= 20);
    return {month, bounds, zoneBest,
      mostDisliked: eligible.sort((a, b) => a.stats.net - b.stats.net || b.stats.opinions - a.stats.opinions)[0] || null,
      riser: movers.filter(item => item.delta > 0).sort((a, b) => b.delta - a.delta || a.subject.localeCompare(b.subject))[0] || null,
      faller: movers.filter(item => item.delta < 0).sort((a, b) => a.delta - b.delta || a.subject.localeCompare(b.subject))[0] || null,
      threads: L.timelineThreads(monthItems.map(item => item.row))};
  };
}
