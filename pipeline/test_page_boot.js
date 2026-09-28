// Execute each generated dashboard artifact with only the controls present in its HTML.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {harness, text} = require('./ui_harness');

function verifySources(ids, P) {
  assert.equal(ids['trend-alerts'], undefined, 'Source artifact has no ranking-only alerts');
  assert.equal(ids['use-today'], undefined, 'Source artifact has no Use today section');
  assert.equal(ids.search, undefined, 'Source artifact has no ranking search control');
  assert.equal(ids['score-mode'], undefined, 'Source artifact has no ranking score control');
  assert.ok(ids['source-chart'].children.length, 'All source rows render');
  assert.ok(ids['community-heatmap'].children.length, 'Community heatmap renders');
  assert.equal(typeof ids['source-filter'].events.change, 'function',
    'The source filter binds without ranking controls');
  assert.ok(P.rowsForRange().some(row => P.sourceId(row) === 'github'),
    'GitHub source data remains available on Sources');
}

function verifyArtifact(filename, expectedPage) {
  let page = fs.readFileSync(__dirname + '/../' + filename, 'utf8');
  assert.doesNotMatch(page, /id="timeline"|pulse-timeline(?:-core)?\.js/,
    'The shipped page has no Timeline section or scripts');
  for (const [href, label] of [['index.html', 'Rankings'], ['reads.html', 'Worth reading'],
    ['sources.html', 'Sources &amp; communities']]) {
    assert.ok(page.includes(`href="${href}"`), `${filename} links to ${href}`);
    assert.ok(page.includes(label), `${filename} labels ${href}`);
  }
  const expectedActive = `href="${expectedPage === 'rankings' ? 'index.html' : 'sources.html'}" aria-current="page"`;
  assert.ok(page.includes(expectedActive), `${filename} highlights its current page`);

  function payload(id) {
    const encoded = page.split(`id="${id}" type="application/json">`)[1]?.split('</script>')[0];
    assert.ok(encoded, `Shipped ${filename} contains ${id}`);
    return JSON.parse(encoded);
  }
  let rows = payload('pulse-data');
  let meta = payload('pulse-meta');
  let logos = payload('pulse-logos');
  const pageIds = new Set([...page.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]));
  const fake = harness(rows, meta, logos);
  rows = null; meta = null; logos = null;
  Object.keys(fake.ids).forEach(id => { if (!pageIds.has(id)) delete fake.ids[id]; });
  const scripts = [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
  page = null;
  scripts.forEach((script, index) => vm.runInContext(script, fake.context,
    {filename: `${filename}-embedded-${index}.js`}));

  const {ids, context} = fake;
  const P = context.Pulse;
  assert.equal(P.page, expectedPage);
  assert.ok(text(ids['update-info']).includes('(Thai time)'));
  assert.ok(ids['covered-period'].textContent.startsWith('Comments from '), 'Date summary still renders');
  assert.equal(P.availableDates.length, P.meta.days.length, 'Date handling still reads shipped history');

  if (expectedPage === 'rankings') {
    assert.ok(ids['trend-alerts'].children.length, 'Trend alerts still render');
    assert.ok(ids['use-today'].children.length, 'Use today recommendations still render');
    assert.ok(ids.chart.innerHTML.includes('<svg'), 'The score chart still renders');
    assert.ok(ids.zones.children.length, 'Model ranking still renders');
    assert.equal(ids['source-chart'], undefined, 'Source chart is not part of the ranking DOM');
    assert.equal(ids['community-heatmap'], undefined, 'Heatmap is not part of the ranking DOM');
    assert.ok(P.rowsForRange().every(row => P.mainSourceIds.includes(P.sourceId(row))),
      'The default ranking artifact only scores its four allowed sources');
  } else verifySources(ids, P);
}

verifyArtifact('pulse.html', 'rankings');
verifyArtifact('sources.html', 'sources');
console.log('Shipped rankings and sources artifacts boot with their actual DOM controls.');
