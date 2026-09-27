'use strict';
const TLUI = globalThis.Pulse;
if (TLUI) {
  TLUI.timelineRaceSvg = function(models) {
    const rows = models.map((model, index) => `<g class="timeline-row ${TLUI.timelineSvgZone(model.zone)}" data-subject="${TLUI.escape(model.subject)}" transform="translate(0 ${38 + index * 36})"><title>${TLUI.escape(model.subject)}</title>${TLUI.svgLogo(model.subject, 6, -5)}<text x="39" y="12" class="timeline-family">${TLUI.escape(TLUI.shortLabel(model.subject))}</text><rect class="timeline-bar ${TLUI.timelineSvgZone(model.zone)}" x="450" y="-8" width="0" height="20" rx="6"/><text class="timeline-score" x="458" y="7">—</text></g>`).join('');
    const height = Math.max(90, 54 + models.length * 36);
    return `<svg class="timeline-race" viewBox="0 0 760 ${height}" role="img" aria-label="Rolling seven-day score race"><text x="450" y="17" text-anchor="middle" class="timeline-axis-label">−100 ← Score → +100</text><line x1="450" y1="27" x2="450" y2="${height}" class="timeline-zero"/>${rows}</svg>`;
  };
  TLUI.updateTimelineRace = function(state) {
    const day = state.dates[state.index], values = TLUI.timelineRaceValues(state.items, state.models, day);
    const ordered = new Map(values.map((value, index) => [value.subject, index]));
    state.target.querySelectorAll('.timeline-row').forEach(node => {
      const subject = node.getAttribute('data-subject'), value = values.find(item => item.subject === subject);
      const rank = ordered.get(subject), hasData = value.stats.opinions > 0;
      const width = hasData ? Math.abs(value.stats.net) * 2.25 : 0;
      const x = value.stats.net >= 0 ? 450 : 450 - width;
      node.setAttribute('transform', `translate(0 ${38 + rank * 36})`);
      node.setAttribute('class', `timeline-row ${TLUI.timelineSvgZone(value.zone)}${hasData ? '' : ' timeline-empty'}`);
      const bar = node.querySelector('.timeline-bar');
      bar.setAttribute('x', String(x)); bar.setAttribute('width', String(width));
      const label = node.querySelector('.timeline-score');
      label.textContent = hasData ? TLUI.netText(value.stats.net) : '—';
      label.setAttribute('x', String(hasData ? (value.stats.net >= 0 ? x + width + 7 : x - 7) : 458));
      label.setAttribute('text-anchor', !hasData || value.stats.net >= 0 ? 'start' : 'end');
      node.querySelector('title').textContent = hasData ?
        `${subject} · ${TLUI.netText(value.stats.net)} · ${value.stats.opinions} opinions` : `${subject} · no opinions in this window`;
    });
    state.refs.date.textContent = TLUI.shortDate(day);
    state.refs.scrubber.value = String(state.index);
    state.refs.caption.textContent = TLUI.timelineCaption(state.items, state.allModels, day);
  };
  TLUI.timelineLineSvg = function(state) {
    const width = 760, height = 330, dates = state.dates;
    const series = TLUI.timelineSeries(state.items, state.allModels, dates);
    const groups = series.map(model => ({model, path: TLUI.timelinePath(model, dates, width, height)}))
      .filter(item => item.path.solid || item.path.dashed || item.path.lone);
    const lines = groups.map(({model, path}) => {
      const solid = path.solid ? `<path class="timeline-line ${TLUI.timelineSvgZone(model.zone)}" d="${path.solid}"/>` : '';
      const dashed = path.dashed ? `<path class="timeline-line ${TLUI.timelineSvgZone(model.zone)} timeline-low-data" d="${path.dashed}"/>` : '';
      const lone = path.lone ? `<circle class="timeline-line-point ${TLUI.timelineSvgZone(model.zone)}${path.lone.low ? ' timeline-low-data' : ''}" cx="${path.lone.x}" cy="${path.lone.y}" r="3"/>` : '';
      return `<g class="timeline-series${state.isolated && state.isolated !== model.subject ? ' timeline-muted' : ''}" data-subject="${TLUI.escape(model.subject)}">${solid}${dashed}${lone}${path.last ? TLUI.svgLogo(model.subject, path.last.x - 11, path.last.y - 11) : ''}</g>`;
    }).join('');
    const grids = [-100, 0, 100].map(score => {
      const y = 18 + (100 - score) * 260 / 200;
      return `<line x1="42" x2="712" y1="${y}" y2="${y}" class="timeline-grid"/><text x="36" y="${y + 4}" text-anchor="end" class="timeline-tick">${score > 0 ? '+' : ''}${score}</text>`;
    }).join('');
    const labels = [0, Math.floor((dates.length - 1) / 2), dates.length - 1].filter((index, pos, all) => all.indexOf(index) === pos)
      .map(index => `<text x="${dates.length < 2 ? 377 : 42 + index * 670 / (dates.length - 1)}" y="302" text-anchor="middle" class="timeline-tick">${dates[index].slice(5)}</text>`).join('');
    return `<svg class="timeline-lines" viewBox="0 0 ${width} ${height}" role="img" aria-label="Seven-day rolling score over time">${grids}${labels}${lines}</svg>`;
  };
  TLUI.renderTimelineLines = function(state) {
    const note = `<p class="timeline-note">Rolling seven-day score; windows below ${TLUI.timelineMinWindow} opinions are dashed. Click a family to isolate it.</p>`;
    state.refs.lines.innerHTML = `${note}${TLUI.timelineLineSvg(state)}`;
    const legend = document.createElement('div'); legend.className = 'timeline-legend';
    state.allModels.forEach(model => {
      const button = TLUI.el('button', undefined, `timeline-legend-item ${TLUI.timelineSvgZone(model.zone)}`);
      button.type = 'button'; button.setAttribute('aria-pressed', String(!state.isolated || state.isolated === model.subject));
      button.append(TLUI.logo(model.subject), TLUI.el('span', model.subject));
      button.addEventListener('click', () => {
        state.isolated = state.isolated === model.subject ? null : model.subject;
        TLUI.renderTimelineLines(state);
      });
      legend.append(button);
    });
    state.refs.lines.append(legend);
  };
  TLUI.timelineInsightLine = function(title, model, detail) {
    const line = TLUI.el('p', undefined, 'timeline-insight');
    line.append(TLUI.el('strong', `${title}: `));
    if (!model) line.append(TLUI.el('span', 'Not enough data yet.'));
    else line.append(TLUI.logo(model.subject), TLUI.el('span', `${model.subject} · ${detail(model)}`));
    return line;
  };
  TLUI.renderTimelineInsights = function(state) {
    const result = TLUI.timelineInsights(state.items, state.month);
    const target = state.refs.insights, fmt = model => `Score ${TLUI.netText(model.stats.net)} · ${model.stats.opinions} opinions`;
    const lines = [
      ['Best in US frontier', result.zoneBest.find(item => item.zone === 'us').model, fmt],
      ['Best in coding tools', result.zoneBest.find(item => item.zone === 'tool').model, fmt],
      ['Best in China + open', result.zoneBest.find(item => item.zone === 'open').model, fmt],
      ['Most disliked', result.mostDisliked, fmt],
      ['Biggest riser', result.riser, model => `${TLUI.netText(model.first.net)} → ${TLUI.netText(model.last.net)} (${TLUI.netText(model.delta)})`],
      ['Biggest faller', result.faller, model => `${TLUI.netText(model.first.net)} → ${TLUI.netText(model.last.net)} (${TLUI.netText(model.delta)})`]
    ].map(([title, model, detail]) => TLUI.timelineInsightLine(title, model, detail));
    const list = TLUI.el('ul', undefined, 'timeline-threads');
    result.threads.forEach(row => {
      const item = TLUI.el('li'); item.append(TLUI.el('span', `${row.count} comments · r/${row.sub || '?'} `, 'muted'));
      const link = TLUI.el('a', row.thread || row.thread_url);
      if (/^https?:\/\//i.test(row.thread_url)) link.href = row.thread_url;
      link.target = '_blank'; link.rel = 'noopener noreferrer'; item.append(link); list.append(item);
    });
    target.replaceChildren(...lines, TLUI.el('h3', 'Busiest threads'), list);
    if (!result.threads.length) target.append(TLUI.el('p', 'No thread activity recorded for this month.', 'muted'));
    return result;
  };
  TLUI.stopTimeline = function(state) {
    if (state.timer && globalThis.clearInterval) globalThis.clearInterval(state.timer);
    state.timer = null; state.refs.play.textContent = '▶ Play'; state.refs.play.setAttribute('aria-pressed', 'false');
  };
  TLUI.playTimeline = function(state) {
    TLUI.stopTimeline(state);
    if (state.index >= state.dates.length - 1) { state.index = 0; TLUI.updateTimelineRace(state); }
    state.refs.play.textContent = '⏸ Pause'; state.refs.play.setAttribute('aria-pressed', 'true');
    if (!globalThis.setInterval) { TLUI.updateTimelineRace(state); TLUI.stopTimeline(state); return; }
    state.timer = globalThis.setInterval(() => {
      if (state.index >= state.dates.length - 1) return TLUI.stopTimeline(state);
      state.index++; TLUI.updateTimelineRace(state);
    }, 800 / state.speed);
  };
  TLUI.timelinePeriodChanged = function(state) {
    TLUI.stopTimeline(state);
    state.isolated = null;
    state.range = TLUI.timelineRange(state.latest, state.mode, state.month);
    state.dates = TLUI.timelineDates(state.range.start, state.range.end);
    state.allModels = TLUI.timelineAllModels(state.items, state.range);
    state.models = state.allModels.slice(0, 12); state.index = Math.max(0, state.dates.length - 1);
    state.refs.scrubber.min = '0'; state.refs.scrubber.max = String(Math.max(0, state.dates.length - 1));
    state.refs.scrubber.value = String(state.index);
    state.refs.race.innerHTML = state.models.length ? TLUI.timelineRaceSvg(state.models) : '<p class="muted">No opinions in this period.</p>';
    TLUI.updateTimelineRace(state); TLUI.renderTimelineLines(state); TLUI.renderTimelineInsights(state);
    state.refs.period.textContent = state.mode === 'month' ? `${state.month} · selected month` : 'Last 30 days';
  };
  TLUI.timelineControls = function(months, initial) {
    const controls = TLUI.el('div', undefined, 'timeline-controls');
    const mode = document.createElement('select'); mode.id = 'timeline-range'; mode.setAttribute('aria-label', 'Timeline range');
    [['30', 'Last 30 days'], ['month', 'Selected month']].forEach(([value, label]) => {
      const option = TLUI.el('option', label); option.value = value; mode.append(option);
    }); mode.value = '30';
    const modeLabel = TLUI.el('label', 'Range'); modeLabel.htmlFor = mode.id; controls.append(modeLabel, mode);
    const monthSelect = document.createElement('select'); monthSelect.id = 'timeline-month'; monthSelect.setAttribute('aria-label', 'Selected month');
    months.forEach(value => {
      const [year, number] = value.split('-').map(Number);
      const label = new Date(Date.UTC(year, number - 1, 1)).toLocaleString('en', {month: 'short', year: 'numeric', timeZone: 'UTC'});
      const option = TLUI.el('option', label); option.value = value; monthSelect.append(option);
    }); monthSelect.value = initial;
    const monthLabel = TLUI.el('label', 'Month'); monthLabel.htmlFor = monthSelect.id; controls.append(monthLabel, monthSelect);
    const play = TLUI.el('button', '▶ Play'); play.type = 'button'; play.setAttribute('aria-pressed', 'false');
    const speed = TLUI.el('div', undefined, 'timeline-speed');
    const speed1 = TLUI.el('button', '1×'); speed1.type = 'button'; speed1.setAttribute('aria-pressed', 'true');
    const speed2 = TLUI.el('button', '2×'); speed2.type = 'button'; speed2.setAttribute('aria-pressed', 'false');
    speed.append(speed1, speed2); controls.append(play, speed);
    return {controls, mode, monthSelect, play, speed1, speed2};
  };
  TLUI.bindTimeline = function(state) {
    const {mode, month, play, speed1, speed2, scrubber} = state.refs;
    mode.addEventListener('change', () => { state.mode = mode.value; TLUI.timelinePeriodChanged(state); });
    month.addEventListener('change', () => {
      state.month = month.value; state.mode = 'month'; mode.value = 'month'; TLUI.timelinePeriodChanged(state);
    });
    scrubber.addEventListener('input', () => { TLUI.stopTimeline(state); state.index = Number(scrubber.value) || 0; TLUI.updateTimelineRace(state); });
    play.addEventListener('click', () => state.timer ? TLUI.stopTimeline(state) : TLUI.playTimeline(state));
    [[speed1, 1], [speed2, 2]].forEach(([button, factor]) => button.addEventListener('click', () => {
      state.speed = factor; speed1.setAttribute('aria-pressed', String(factor === 1)); speed2.setAttribute('aria-pressed', String(factor === 2));
      if (state.timer) TLUI.playTimeline(state);
    }));
  };
  TLUI.initTimeline = function() {
    const target = TLUI.$('timeline');
    if (!target || !Array.isArray(TLUI.rows)) return;
    const items = TLUI.timelineRows(TLUI.rows), months = TLUI.timelineMonths(items);
    const latest = items.map(item => item.day).sort().slice(-1)[0] || TLUI.latestDate;
    const month = months[months.length - 1] || String(latest).slice(0, 7), built = TLUI.timelineControls(months, month);
    const period = TLUI.el('p', '', 'timeline-period'), date = TLUI.el('h3', '', 'timeline-date');
    date.setAttribute('aria-live', 'polite');
    const scrubber = document.createElement('input'); scrubber.type = 'range'; scrubber.id = 'timeline-scrubber';
    scrubber.setAttribute('aria-label', 'Scrub timeline date');
    const caption = TLUI.el('p', '', 'timeline-caption'); caption.setAttribute('role', 'status');
    const race = TLUI.el('div', undefined, 'timeline-race-wrap'), lines = TLUI.el('div', undefined, 'timeline-line-wrap');
    const insights = TLUI.el('div', undefined, 'timeline-month-insights');
    target.replaceChildren(TLUI.el('h2', 'Timeline', 'strip-title'), built.controls, period, date, scrubber, caption,
      TLUI.el('h3', 'Rolling seven-day score race'), race, TLUI.el('h3', 'Score over time'), lines,
      TLUI.el('h3', 'Month insights'), insights);
    const state = {target, items, latest, month, months, mode: '30', range: null, dates: [], models: [], index: 0,
      speed: 1, timer: null, isolated: null, refs: {mode: built.mode, month: built.monthSelect,
        play: built.play, speed1: built.speed1, speed2: built.speed2, period, date, scrubber, caption, race, lines, insights}};
    TLUI.timelineState = state; TLUI.bindTimeline(state); TLUI.timelinePeriodChanged(state);
    if (globalThis.matchMedia && globalThis.matchMedia('(prefers-reduced-motion: reduce)').matches) target.classList.add('timeline-reduced-motion');
  };
  TLUI.initTimeline();
}
