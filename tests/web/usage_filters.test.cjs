const assert = require('node:assert/strict');
const test = require('node:test');
const { rangeParams, platformId } = require('../../web/usage-filters.js');

for (const days of [7, 30, 90]) {
  test(`${days} days includes today and starts at a calendar boundary`, () => {
    const now = new Date(2026, 9, 13, 12, 30);
    const params = new URLSearchParams(rangeParams(days, now));
    const start = new Date(params.get('start'));
    const end = new Date(params.get('end'));
    assert.equal(params.get('range'), 'custom');
    assert.equal(start.getTime(), new Date(2026, 9, 14 - days).getTime());
    assert.equal(end.getTime(), new Date(2026, 9, 14).getTime());
    assert.equal(params.get('timezone'), Intl.DateTimeFormat().resolvedOptions().timeZone);
  });
}

test('calendar ranges remain correct across daylight saving', () => {
  const params = new URLSearchParams(rangeParams(7, new Date(2026, 2, 10, 12)));
  assert.equal(new Date(params.get('start')).getTime(), new Date(2026, 2, 4).getTime());
  assert.equal(new Date(params.get('end')).getTime(), new Date(2026, 2, 11).getTime());
});

test('platform labels and IDs resolve to API identifiers', () => {
  for (const [input, expected] of [['All Platforms (4)', null], ['all', null],
    ['OpenCode', 'opencode'], ['Cline CLI', 'cline'], ['Claude Code', 'claude_code'],
    ['Codex CLI', 'codex'], ['claude_code', 'claude_code']]) {
    assert.equal(platformId(input), expected);
  }
});

test('invalid filters fail explicitly', () => {
  assert.throws(() => platformId('unknown'), /Unknown platform/);
  assert.throws(() => rangeParams(0), /Unsupported day range/);
});
