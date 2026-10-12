const assert = require('node:assert/strict');
const test = require('node:test');
const { summarizeSeries, columnScale, createRenderer } = require('../../web/usage-chart.js');
const { dayLabel } = require('../../web/usage-breakdown.js');

function series(platform, entries) {
  return { p: { id: platform }, buckets: entries.map(([label, total]) => ({label, totals: {total_tokens: total}})) };
}

/* Minimal element stub: the renderer only writes innerHTML/textContent and reads
 * a handful of child spans off the Y axis. */
function stubElement() {
  const nodes = {};
  return {
    nodes,
    get(id) {
      return nodes[id] || (nodes[id] = {innerHTML: '', textContent: '', querySelectorAll: () => []});
    }
  };
}

function renderChart(platforms, entries, mode = 'stacked') {
  const dom = stubElement();
  const renderer = createRenderer({
    element: dom.get,
    formatCompact: (n) => String(n),
    escapeHtml: (s) => String(s),
    dayLabel
  });
  renderer.render({data: summarizeSeries(entries), platforms, mode, days: 7, platform: null});
  return dom.nodes;
}

const PLATFORMS = [
  {id: 'claude_code', label: 'Claude Code', color: '#10b981'},
  {id: 'codex', label: 'Codex', color: '#f59e0b'}
];

test('a 90-day series preserves every historical bucket', () => {
  const entries = Array.from({length: 90}, (_, day) => [new Date(Date.UTC(2026, 6, day + 1)).toISOString().slice(0, 10), day + 1]);
  const data = summarizeSeries([series('opencode', entries)]);
  assert.equal(data.labels.length, 90);
  assert.equal(data.labels[0], '2026-07-01');
  assert.equal(data.totals.opencode, 4095);
});

test('platforms have separate daily values and chronological labels', () => {
  const data = summarizeSeries([
    series('opencode', [['2026-10-13', 10], ['2026-10-12', 20]]),
    series('cline', [['2026-10-12', 90]])
  ]);
  assert.deepEqual(data.labels, ['2026-10-12', '2026-10-13']);
  assert.deepEqual(data.byLabel['2026-10-12'], {opencode: 20, cline: 90});
  assert.deepEqual(data.totals, {opencode: 30, cline: 90});
  assert.equal(data.maxStacked, 110);
  assert.equal(data.maxGrouped, 90);
});

test('stacked segments share their column height', () => {
  assert.deepEqual(columnScale([20, 80], 200, 'stacked'), {height: 50, segments: [20, 80]});
});

test('grouped segments use the chart axis directly', () => {
  assert.deepEqual(columnScale([20, 80], 100, 'grouped'), {height: 100, segments: [20, 80]});
});

test('empty usage never produces invalid heights', () => {
  assert.deepEqual(columnScale([0, 0], 0, 'stacked'), {height: 0, segments: [0, 0]});
});

test('the legend shows each platform total and its share of the window', () => {
  const nodes = renderChart(PLATFORMS, [
    series('claude_code', [['2026-10-11', 500], ['2026-10-12', 700]]),
    series('codex', [['2026-10-11', 200], ['2026-10-12', 100]])
  ]);
  const legend = nodes['platform-legend'].innerHTML;
  assert.match(legend, /Claude Code/);
  assert.match(legend, /1200 \(80\.0%\)/);
  assert.match(legend, /300 \(20\.0%\)/);
});

test('every legend entry highlights by the platform id the API uses', () => {
  const nodes = renderChart(PLATFORMS, [series('claude_code', [['2026-10-11', 5]])]);
  assert.match(nodes['platform-legend'].innerHTML, /togglePlatformHighlight\('claude_code'\)/);
});

test('day labels come from the injected formatter, not a private copy', () => {
  const nodes = renderChart(PLATFORMS, [series('codex', [['2026-10-11', 5]])]);
  assert.match(nodes['bar-chart-columns'].innerHTML, /Oct 11/);
  assert.match(nodes['chart-caption'].innerHTML, /Oct 11/);
});
