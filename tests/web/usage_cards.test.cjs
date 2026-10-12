const assert = require('node:assert/strict');
const test = require('node:test');
const breakdown = require('../../web/usage-breakdown.js');
const ranking = require('../../web/model-ranking.js');
const {createRenderer} = require('../../web/usage-cards.js');

const PLATFORMS = [
  {id: 'opencode', label: 'OpenCode', color: '#8b5cf6'},
  {id: 'cline', label: 'Cline', color: '#06b6d4'},
  {id: 'claude_code', label: 'Claude Code', color: '#10b981'},
  {id: 'codex', label: 'Codex', color: '#f59e0b'}
];

function row(platform, modelId, totals = {}, requestCount = 0) {
  return {
    platform, provider_id: 'p', model_id: modelId, request_count: requestCount,
    unknown_total_events: 0,
    totals: Object.assign({input_tokens: 0, output_tokens: 0, total_tokens: 0,
      consumption_tokens: 0, cache: null}, totals)
  };
}

function cache(over = {}) {
  return Object.assign({cache_read_tokens: 0, cache_write_tokens: 0,
    cache_hit_requests: 0, cache_miss_requests: 0, cache_unknown_requests: 0,
    cache_prompt_tokens: 0}, over);
}

function bucket(label, total, requestCount = 0) {
  return {label, request_count: requestCount,
    totals: {input_tokens: total, output_tokens: 0, total_tokens: total,
      consumption_tokens: total, cache: cache()}};
}

const MODELS = [
  row('cline', 'cline-a', {total_tokens: 400, cache: cache({cache_hit_requests: 3,
    cache_miss_requests: 1, cache_read_tokens: 300, cache_prompt_tokens: 700})}, 4),
  row('cline', 'cline-b', {total_tokens: 100}, 1),
  row('opencode', 'opencode-a', {total_tokens: 900}, 8)
];

function harness() {
  const nodes = {};
  const lookup = id => nodes[id] || (nodes[id] = {innerHTML: '', textContent: '', setAttribute() {}});
  const dayBars = breakdown.createDayBarRenderer({
    element: lookup, formatCompact: String, formatInteger: String,
    formatPercent: f => (f * 100).toFixed(1) + '%', escapeHtml: String
  });
  const renderer = createRenderer({
    element: lookup, dayBars, formatCompact: String, formatInteger: String,
    formatPercent: f => (f * 100).toFixed(1) + '%', escapeHtml: String,
    rates: breakdown,
    modelRanking: ranking.createRenderer({formatCompact: String, formatInteger: String, escapeHtml: String})
  });
  const series = {};
  function render(over = {}) {
    renderer.render(Object.assign({
      models: MODELS,
      rows: breakdown.aggregateByPlatform(MODELS, ''),
      platforms: PLATFORMS,
      platformFilter: '',
      rangeLabel: 'the last 7 days',
      statusFor: () => ({available: true}),
      modelByPlatform: {},
      modelsFor: id => breakdown.modelsForPlatform(MODELS, id),
      daySeriesFor: (platformId, modelId) =>
        series[platformId] || {modelId, buckets: []}
    }, over));
    return nodes['usage-card-grid'].innerHTML;
  }
  return {render, series, nodes};
}

function cardFor(html, platformId) {
  const start = html.indexOf(`data-platform="${platformId}"`);
  assert.ok(start > -1, 'no card for ' + platformId);
  const end = html.indexOf('</article>', start);
  return html.slice(start, end);
}

test('all four platforms get a card, quiet ones included', () => {
  const html = harness().render();
  for (const platform of PLATFORMS) {
    assert.ok(html.includes(`data-platform="${platform.id}"`), 'missing ' + platform.id);
  }
});

test('a platform with no stored usage explains itself instead of vanishing', () => {
  const html = harness().render();
  assert.ok(cardFor(html, 'codex').includes('No stored usage in this range.'));
});

test('the platform dropdown narrows the grid to the chosen card', () => {
  const html = harness().render({platformFilter: 'cline'});
  assert.ok(html.includes('data-platform="cline"'));
  assert.ok(!html.includes('data-platform="opencode"'));
  assert.equal((html.match(/<article/g) || []).length, 1);
});

test('each card shows the hits, misses and token figures it was asked for', () => {
  const card = cardFor(harness().render(), 'cline');
  for (const label of ['Total tokens', 'Requests', 'Cache read', 'Cache hits',
    'Cache misses', 'Input', 'Output', 'Hit rate']) {
    assert.ok(card.includes(label), 'card is missing ' + label);
  }
  assert.ok(card.includes('75.0%'), 'hit rate 3 of 4 known requests');
});

test('a card dropdown lists only its own platform models', () => {
  const card = cardFor(harness().render(), 'cline');
  const options = [...card.matchAll(/<option value="([^"]*)"/g)].map(m => m[1]);
  assert.deepEqual(options, ['', 'cline-a', 'cline-b']);
});

test('choosing a model swaps that card to day bars and leaves the others alone', () => {
  const {render, series} = harness();
  series.cline = {modelId: 'cline-a', buckets: [bucket('2026-10-11', 200, 3),
    bucket('2026-10-12', 400, 6)]};
  const html = render({modelByPlatform: {cline: 'cline-a'}});

  const cline = cardFor(html, 'cline');
  assert.ok(cline.includes('usage-day-row'), 'drilled card should show day bars');
  assert.equal((cline.match(/usage-day-row/g) || []).length, 2);
  assert.ok(!cline.includes('Cache misses</dt>'), 'summary metrics should give way to bars');

  assert.ok(cardFor(html, 'opencode').includes('Cache hits'),
    'neighbouring cards keep their summaries');
});

test('the drilled card offers a way back to its summary', () => {
  const {render, series} = harness();
  series.cline = {modelId: 'cline-a', buckets: [bucket('2026-10-11', 200, 3)]};
  const card = cardFor(render({modelByPlatform: {cline: 'cline-a'}}), 'cline');
  assert.ok(card.includes('Change model'), 'a drilled card must be escapable');
  assert.ok(card.includes('<option value=""'), 'back option must clear the selection');
});

test('a model whose usage fell outside the range yields an empty day list', () => {
  const {render} = harness();
  const card = cardFor(render({modelByPlatform: {cline: 'cline-b'}}), 'cline');
  assert.ok(card.includes('No usage on any day in this range.'));
});

test('the caption counts used platforms and drilled cards without stuttering', () => {
  const {render, nodes, series} = harness();
  render();
  assert.equal(nodes['usage-card-caption'].textContent,
    'Usage across 4 platforms in the last 7 days.');

  series.cline = {modelId: 'cline-a', buckets: [bucket('2026-10-11', 200, 3)]};
  render({modelByPlatform: {cline: 'cline-a'}});
  assert.equal(nodes['usage-card-caption'].textContent,
    'Usage across 4 platforms in the last 7 days. 1 card is showing one model by day.');
});

test('a single-platform filter says so instead of repeating the platform count', () => {
  const {render, nodes} = harness();
  render({platformFilter: 'cline'});
  assert.equal(nodes['usage-card-caption'].textContent,
    'Usage for one platform in the last 7 days.');
});

test('a load failure states the problem and the recovery', () => {
  const nodes = {};
  const lookup = id => nodes[id] || (nodes[id] = {innerHTML: '', textContent: '', setAttribute() {}});
  const renderer = createRenderer({
    element: lookup, dayBars: breakdown.createDayBarRenderer({
      element: lookup, formatCompact: String, formatInteger: String,
      formatPercent: String, escapeHtml: String
    }),
    formatCompact: String, formatInteger: String, formatPercent: String,
    escapeHtml: String, rates: breakdown
  });
  renderer.clear('Could not reach the Tokenly API. Start the backend (python main.py), then refresh.');
  assert.ok(nodes['usage-card-grid'].innerHTML.includes('Could not reach the Tokenly API'));
  assert.equal(nodes['usage-card-caption'].textContent, '');
});

test('every card dropdown is labelled for screen readers', () => {
  const html = harness().render();
  assert.ok(html.includes('for="usage-model-cline"'));
  assert.ok(html.includes('Model for Cline'));
});
test('a focused provider uses the spare columns for read-only model comparison', () => {
  const html = harness().render({platformFilter: 'cline'});
  assert.ok(html.includes('usage-model-ranking'));
  assert.ok(html.includes('400 tokens'));
  assert.ok(html.includes('4 requests'));
  assert.ok(!html.includes('data-model="opencode-a"'));
});

test('all-platform view keeps the four-card layout without a ranking panel', () => {
  assert.ok(!harness().render().includes('usage-model-ranking'));
});

test('model drill-down keeps the provider ranking visible and unfiltered', () => {
  const {render, series} = harness();
  series.cline = {modelId: 'cline-a', buckets: [bucket('2026-10-11', 400, 4)]};
  const html = render({platformFilter: 'cline', modelByPlatform: {cline: 'cline-a'}});
  assert.ok(html.includes('usage-day-row'));
  assert.ok(html.includes('data-model="cline-a"'));
  assert.ok(html.includes('data-model="cline-b"'));
});
