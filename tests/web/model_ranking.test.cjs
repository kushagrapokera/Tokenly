const assert = require('node:assert/strict');
const test = require('node:test');
const {rankModels, createRenderer} = require('../../web/model-ranking.js');

function model(platform, modelId, tokens, requests) {
  return {platform, model_id: modelId, totals: {total_tokens: tokens}, request_count: requests};
}

test('ranks only the selected platform models by token usage', () => {
  const rows = rankModels([
    model('cline', 'small', 100, 2), model('cline', 'large', 900, 3),
    model('opencode', 'other', 9000, 90)
  ], 'cline');
  assert.deepEqual(rows, [
    {model_id: 'large', total_tokens: 900, request_count: 3},
    {model_id: 'small', total_tokens: 100, request_count: 2}
  ]);
});

test('combines a model used through multiple providers', () => {
  assert.deepEqual(rankModels([
    model('cline', 'shared', 100, 2), model('cline', 'shared', 300, 4)
  ], 'cline'), [{model_id: 'shared', total_tokens: 400, request_count: 6}]);
});

test('equal token totals have a stable alphabetical order', () => {
  assert.deepEqual(rankModels([model('cline', 'z', 0, 1), model('cline', 'a', 0, 1)], 'cline')
    .map(row => row.model_id), ['a', 'z']);
});

test('a provider without usage has no invented models', () => {
  assert.deepEqual(rankModels([], 'codex'), []);
});

test('read-only rows scale bars to the busiest model and show request counts', () => {
  const renderer = createRenderer({formatCompact: String, formatInteger: String, escapeHtml: String});
  const html = renderer.render({platform: {id: 'cline', label: 'Cline', color: '#06b6d4'},
    models: [model('cline', 'a', 400, 4), model('cline', 'b', 100, 2)], rangeLabel: 'the last 30 days'});
  assert.ok(html.includes('width:100%'));
  assert.ok(html.includes('width:25%'));
  assert.ok(html.includes('4 requests'));
  assert.ok(html.includes('2 requests'));
  assert.ok(!html.includes('<button'));
});

test('zero tokens do not produce invalid bar widths', () => {
  const renderer = createRenderer({formatCompact: String, formatInteger: String, escapeHtml: String});
  const html = renderer.render({platform: {id: 'cline', label: 'Cline', color: '#06b6d4'},
    models: [model('cline', 'quiet', 0, 2)], rangeLabel: 'the last 7 days'});
  assert.ok(html.includes('width:0%'));
  assert.ok(!html.includes('NaN') && !html.includes('Infinity'));
});
