(function (root) {
  'use strict';

  function rangeParams(days, now) {
    if ([7, 30, 90].indexOf(days) === -1) throw new RangeError('Unsupported day range: ' + days);
    now = now || new Date();
    var start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - days + 1);
    var end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    return new URLSearchParams({
      range: 'custom', start: start.toISOString(), end: end.toISOString(),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
    }).toString();
  }

  function platformId(value) {
    var key = String(value || 'all').toLowerCase().trim();
    var platforms = {
      'all': null, 'all platforms (4)': null, 'opencode': 'opencode',
      'cline': 'cline', 'cline cli': 'cline', 'claude code': 'claude_code',
      'claude_code': 'claude_code', 'codex': 'codex', 'codex cli': 'codex'
    };
    if (!Object.prototype.hasOwnProperty.call(platforms, key)) {
      throw new RangeError('Unknown platform: ' + value);
    }
    return platforms[key];
  }

  var api = { rangeParams: rangeParams, platformId: platformId };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TokenlyUsageFilters = api;
})(typeof window === 'undefined' ? globalThis : window);
