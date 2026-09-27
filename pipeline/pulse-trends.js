'use strict';
const T = globalThis.Pulse = globalThis.Pulse || {};
T.trendDay = 86400000;
T.trendTimestamp = function(value) {
  if (typeof value === 'number') return Number.isFinite(value) ? value * (Math.abs(value) > 1e11 ? 1 : 1000) : null;
  const raw = String(value ?? '').trim();
  if (!raw) return null;
  if (/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(raw)) {
    const number = Number(raw);
    return Number.isFinite(number) ? number * (Math.abs(number) > 1e11 ? 1 : 1000) : null;
  }
  const parts = raw.match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?(Z|[+-]\d{2}:?\d{2})?)?$/i);
  if (!parts) return null;
  const [, ys, mos, ds, hs = '0', mis = '0', ss = '0', fraction = '', zone = 'Z'] = parts;
  const [year, month, day, hour, minute, second] = [ys, mos, ds, hs, mis, ss].map(Number);
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  date.setUTCHours(hour, minute, second, Number((fraction + '000').slice(0, 3)));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day ||
      date.getUTCHours() !== hour || date.getUTCMinutes() !== minute || date.getUTCSeconds() !== second) return null;
  const offset = zone.match(/^([+-])(\d{2}):?(\d{2})$/);
  if (!offset) return date.getTime();
  const hours = Number(offset[2]), minutes = Number(offset[3]);
  if (hours > 23 || minutes > 59) return null;
  return date.getTime() - (offset[1] === '+' ? 1 : -1) * (hours * 60 + minutes) * 60000;
};
T.trendGroup = function(groups, subject, version) {
  const key = JSON.stringify([subject, version]);
  if (!groups.has(key)) groups.set(key, {subject, version,
    name: version === null ? subject : `${subject} · ${version}`, now: [], before: []});
  return groups.get(key);
};
T.trendGroups = function(rows, endExclusive) {
  const groups = new Map(), nowStart = endExclusive - 2 * T.trendDay;
  const beforeStart = endExclusive - 9 * T.trendDay;
  (Array.isArray(rows) ? rows : []).forEach(row => {
    if (!row || (row.kind && row.kind !== 'comment')) return;
    const subject = typeof row.subject === 'string' ? row.subject.trim() : '';
    const stamp = T.trendTimestamp(row.created_utc);
    if (!subject || stamp === null || stamp < beforeStart || stamp >= endExclusive) return;
    const window = stamp >= nowStart ? 'now' : 'before';
    T.trendGroup(groups, subject, null)[window].push(row);
    const version = typeof row.version === 'string' ? row.version.trim() : '';
    if (version && version.toLowerCase() !== 'version unknown') {
      T.trendGroup(groups, subject, version)[window].push(row);
    }
  });
  return [...groups.values()];
};
T.trendStats = function(rows) {
  const praise = rows.filter(row => row.label === 'praise').length;
  const mixed = rows.filter(row => row.label === 'mixed').length;
  const complaint = rows.filter(row => row.label === 'complaint').length;
  const opinions = praise + mixed + complaint;
  return {opinions, net: opinions ? (praise - complaint) * 100 / opinions : 0};
};
T.trendScore = row => Number.isFinite(Number(row.score)) ? Number(row.score) : 0;
T.trendCompareText = (a, b) => a < b ? -1 : a > b ? 1 : 0;
T.trendQuote = function(rows, label) {
  return rows.filter(row => row.label === label).sort((a, b) =>
    T.trendScore(b) - T.trendScore(a) || T.trendCompareText(String(a.link || ''), String(b.link || '')) ||
    T.trendCompareText(String(a.text || ''), String(b.text || '')) ||
    T.trendCompareText(String(a.id || ''), String(b.id || '')))[0] || null;
};
T.trendNameOrder = (a, b) => b.now.opinions - a.now.opinions || T.trendCompareText(a.name, b.name);
T.trendsFor = function(rows, endDate) {
  if (typeof endDate !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(endDate)) return [];
  const midnight = T.trendTimestamp(endDate);
  if (midnight === null) return [];
  const groups = T.trendGroups(rows, midnight + T.trendDay), swings = [], newNames = [];
  groups.forEach(group => {
    const now = T.trendStats(group.now), before = T.trendStats(group.before);
    const delta = now.net - before.net;
    if (now.opinions >= 15 && before.opinions >= 20 && Math.abs(delta) >= 15) {
      const kind = delta < 0 ? 'drop' : 'rise';
      swings.push({...group, kind, now, before, delta,
        quote: T.trendQuote(group.now, kind === 'drop' ? 'complaint' : 'praise')});
    } else if (now.opinions >= 15 && before.opinions < 5) {
      newNames.push({...group, kind: 'new', now, before, delta: null, quote: null});
    }
  });
  swings.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta) || T.trendNameOrder(a, b));
  newNames.sort(T.trendNameOrder);
  return [...swings, ...newNames];
};
