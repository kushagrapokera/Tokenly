const assert = require('node:assert/strict');
const test = require('node:test');
const { sparklinePaths, summarizeModels } = require('../../web/platform-cards.js');

test('sparkline traces the actual daily values across the whole card', () => {
  assert.deepEqual(sparklinePaths([0, 100, 50]), {
    line: 'M2,34 L100,2 L198,18', area: 'M2,34 L100,2 L198,18 L198,36 L2,36 Z'
  });
});

test('all 90 days are represented in the trend', () => {
  const path = sparklinePaths(Array.from({length: 90}, (_, index) => index)).line;
  assert.equal(path.split(' ').length, 90);
  assert.ok(path.startsWith('M2,34 '));
  assert.ok(path.endsWith('L198,2'));
});

test('zero usage has a finite flat line', () => {
  assert.deepEqual(sparklinePaths([0, 0]), {
    line: 'M2,34 L198,34', area: 'M2,34 L198,34 L198,36 L2,36 Z'
  });
});

test('an absent timeline does not invent a graph', () => {
  assert.deepEqual(sparklinePaths([]), {line: '', area: ''});
});

test('a single day remains visible as a full width line', () => {
  assert.equal(sparklinePaths([100]).line, 'M2,2 L198,2');
});

test('card metrics include every model and distinguish input from output', () => {
  const models = [
    {model_id: 'first', request_count: 2, totals: {total_tokens: 100, input_tokens: 80, output_tokens: 20}},
    {model_id: 'second', request_count: 3, totals: {total_tokens: 200, input_tokens: 150, output_tokens: 50}}
  ];
  assert.deepEqual(summarizeModels(models), {
    total: 300, input: 230, output: 70, requests: 5, modelCount: 2, topModel: 'second'
  });
});
