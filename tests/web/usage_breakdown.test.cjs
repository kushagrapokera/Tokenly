const assert = require('node:assert/strict');
const test = require('node:test');
const {
  aggregateByPlatform,
  createDayBarRenderer,
  modelsForPlatform,
  requestHitRate,
  shortModel,
  tokenHitRate
} = require('../../web/usage-breakdown.js');

/* One model row as /api/usage/models returns it: platform, identifiers, and a totals
   block whose cache figures are the additive counters the backend computed. */
function row(platform, modelId, overrides = {}) {
  const cache = Object.assign({
    cache_read_tokens: 0, cache_write_tokens: 0, cache_hit_requests: 0,
    cache_miss_requests: 0, cache_unknown_requests: 0, cache_prompt_tokens: 0
  }, overrides.cache || {});
  const totals = Object.assign(
    {input_tokens: 0, output_tokens: 0, total_tokens: 0, consumption_tokens: 0},
    overrides.totals || {}
  );
  return Object.assign(
    {platform, provider_id: 'p', model_id: modelId, request_count: 0,
     unknown_total_events: 0, totals: Object.assign({}, totals, {cache})},
    overrides.extra || {}
  );
}

/* One timeline bucket as /api/usage/timeline returns it. */
function bucket(label, overrides = {}) {
  const cache = Object.assign({
    cache_read_tokens: 0, cache_write_tokens: 0, cache_hit_requests: 0,
    cache_miss_requests: 0, cache_unknown_requests: 0, cache_prompt_tokens: 0
  }, overrides.cache || {});
  const totals = Object.assign(
    {input_tokens: 0, output_tokens: 0, total_tokens: 0, consumption_tokens: 0},
    overrides.totals || {}
  );
  return Object.assign(
    {label, request_count: 0, totals: Object.assign({}, totals, {cache})},
    overrides.extra || {}
  );
}

test('rows reduce onto the platform that produced them', () => {
  const rows = aggregateByPlatform([
    row('opencode', 'a', {extra: {request_count: 3}, totals: {total_tokens: 300}}),
    row('opencode', 'b', {extra: {request_count: 1}, totals: {total_tokens: 100}}),
    row('cline', 'a', {extra: {request_count: 2}, totals: {total_tokens: 50}})
  ]);
  assert.equal(rows.opencode.request_count, 4);
  assert.equal(rows.opencode.total_tokens, 400);
  assert.equal(rows.cline.total_tokens, 50);
});

test('cache counters are summed rather than averaged', () => {
  const rows = aggregateByPlatform([
    row('opencode', 'a', {cache: {cache_read_tokens: 500, cache_hit_requests: 2,
      cache_miss_requests: 1, cache_prompt_tokens: 1500}}),
    row('opencode', 'b', {cache: {cache_read_tokens: 100, cache_hit_requests: 1,
      cache_miss_requests: 0, cache_prompt_tokens: 400}})
  ]);
  assert.deepEqual(rows.opencode.cache, {
    cache_read_tokens: 600, cache_write_tokens: 0, cache_hit_requests: 3,
    cache_miss_requests: 1, cache_unknown_requests: 0, cache_prompt_tokens: 1900
  });
});

test('an unreported cache row counts as unknown, never as a miss', () => {
  const rows = aggregateByPlatform([
    row('opencode', 'a', {cache: {cache_read_tokens: 500, cache_hit_requests: 1,
      cache_prompt_tokens: 1500}}),
    row('opencode', 'b', {cache: {cache_unknown_requests: 1}})
  ]);
  assert.equal(rows.opencode.cache.cache_miss_requests, 0);
  assert.equal(rows.opencode.cache.cache_unknown_requests, 1);
  assert.equal(requestHitRate(rows.opencode.cache), 1);
});

test('a row with no cache block contributes nothing and rates stay absent', () => {
  const rows = aggregateByPlatform([
    {platform: 'cline', model_id: 'a', request_count: 1,
     totals: {input_tokens: 10, output_tokens: 1, total_tokens: 11}}
  ]);
  assert.equal(rows.cline.cache.cache_read_tokens, 0);
  assert.equal(requestHitRate(rows.cline.cache), null);
  assert.equal(tokenHitRate(rows.cline.cache), null);
});

test('the hit rate divides by requests the source spoke about', () => {
  assert.equal(requestHitRate({cache_hit_requests: 2, cache_miss_requests: 1,
    cache_unknown_requests: 35}), 2 / 3);
});

test('the token rate divides by the overlap-aware prompt denominator', () => {
  assert.equal(tokenHitRate({cache_read_tokens: 1000, cache_prompt_tokens: 1000}), 1);
  assert.equal(tokenHitRate({cache_read_tokens: 1000, cache_prompt_tokens: 2000}), 0.5);
});

test('each card offers only the models its own platform has used', () => {
  const models = [
    row('cline', 'zeta'), row('cline', 'alpha'), row('cline', 'alpha'),
    row('opencode', 'mu')
  ];
  assert.deepEqual(modelsForPlatform(models, 'cline'), ['alpha', 'zeta']);
  assert.deepEqual(modelsForPlatform(models, 'opencode'), ['mu']);
  assert.deepEqual(modelsForPlatform(models, 'codex'), []);
});

test('long model names are shortened without overflowing', () => {
  assert.equal(shortModel('cline-free/step-5-preview'), 'step-5-preview');
  assert.equal(shortModel('a'.repeat(40)).length, 28);
});

/* --- per-day bars --- */

function stubElement() {
  const nodes = {};
  return {nodes, lookup: id => nodes[id] || (nodes[id] = {innerHTML: '', textContent: ''})};
}

function barsFor(lookup) {
  return createDayBarRenderer({
    element: lookup,
    formatCompact: n => String(n),
    formatInteger: n => String(n),
    formatPercent: f => (f * 100).toFixed(1) + '%',
    escapeHtml: String
  });
}

test('day bars scale against the busiest day', () => {
  const {lookup} = stubElement();
  const html = barsFor(lookup).render([
    bucket('2026-10-11', {totals: {total_tokens: 400}}),
    bucket('2026-10-12', {totals: {total_tokens: 100}})
  ], null);
  assert.deepEqual([...html.matchAll(/width:([0-9.]+)%/g)].map(m => Number(m[1])), [100, 25]);
});

test('an all-empty range states it instead of rendering silent zeroes', () => {
  const {lookup} = stubElement();
  const html = barsFor(lookup).render([
    bucket('2026-10-11'), bucket('2026-10-12')
  ], null);
  assert.ok(html.includes('No usage on any day in this range.'));
  assert.ok(!html.includes('width:100'));
});

test('a day tooltip reports cache hits, misses, input, output and totals', () => {
  const {lookup} = stubElement();
  const html = barsFor(lookup).render([bucket('2026-10-11', {
    extra: {request_count: 4},
    totals: {input_tokens: 10, output_tokens: 5, total_tokens: 15},
    cache: {cache_read_tokens: 400, cache_write_tokens: 9, cache_hit_requests: 3,
      cache_miss_requests: 1, cache_prompt_tokens: 500}
  })], null);
  for (const label of ['Requests', 'Input tokens', 'Output tokens', 'Total tokens',
    'Cache read', 'Cache hits', 'Cache misses', 'Request hit rate', 'Token hit rate']) {
    assert.ok(html.includes(label), 'day tooltip is missing ' + label);
  }
  assert.ok(html.includes('75.0%'), 'hit rate 3 of 4 known requests');
});

test('a day with no reported requests says so rather than implying zero', () => {
  const {lookup} = stubElement();
  const html = barsFor(lookup).render([bucket('2026-10-11', {totals: {total_tokens: 5}})], null);
  assert.ok(html.includes('&mdash;'));
  assert.ok(!html.includes('0.0%'));
});

test('a day tooltip follows its bar so keyboard focus can reach it', () => {
  /* Focus reveals the tooltip through a sibling selector, so the tooltip must come
     after the bar. Emitting it earlier leaves the bar focusable but the tooltip
     invisible to anyone not using a mouse. */
  const {lookup} = stubElement();
  const html = barsFor(lookup).render([bucket('2026-10-11', {totals: {total_tokens: 5}})], null);
  assert.ok(html.indexOf('usage-bar-track') < html.indexOf('usage-bar-tooltip'));
});

test('a model selected whose usage fell outside the range shows an empty day list', () => {
  const {lookup} = stubElement();
  const html = barsFor(lookup).render([], null);
  assert.ok(html.includes('No usage on any day in this range.'));
});