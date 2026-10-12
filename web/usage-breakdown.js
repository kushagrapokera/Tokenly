/* Metric arithmetic and per-day usage bars for the platform breakdown.
 *
 * Two rules hold everywhere in this file, and they are the reason the numbers are
 * right rather than merely plausible:
 *
 * 1. Rates are never averaged. The API groups usage by (platform, provider, model),
 *    and this module adds those rows up to reach a platform. Every field summed here
 *    is an additive counter; a rate is a ratio, so averaging ratios is meaningless.
 *    Rates are re-derived from the summed counters instead, using the same rules as
 *    aggregation/cache.py.
 * 2. Unknown is not a miss. A request whose source never reported cache data is
 *    counted apart from a genuine miss and excluded from the hit-rate denominator.
 *    Otherwise a provider that stopped reporting looks like one whose cache stopped
 *    working — the opposite of what happened.
 */
(function (root) {
  'use strict';

  var ALL_MODELS = '';

  function num(value) {
    return typeof value === 'number' && isFinite(value) ? value : 0;
  }

  function emptyCache() {
    return {
      cache_read_tokens: 0, cache_write_tokens: 0, cache_hit_requests: 0,
      cache_miss_requests: 0, cache_unknown_requests: 0, cache_prompt_tokens: 0
    };
  }

  /* Read a cache block off a model row or a timeline bucket, tolerating its absence.
   * Older stored usage and some collectors carry no cache block at all, and a missing
   * block means "nothing was reported", not "zero". */
  function cacheOf(record) {
    var totals = record ? record.totals : null;
    var cache = totals ? totals.cache : null;
    if (!cache) return emptyCache();
    return {
      cache_read_tokens: num(cache.cache_read_tokens),
      cache_write_tokens: num(cache.cache_write_tokens),
      cache_hit_requests: num(cache.cache_hit_requests),
      cache_miss_requests: num(cache.cache_miss_requests),
      cache_unknown_requests: num(cache.cache_unknown_requests),
      cache_prompt_tokens: num(cache.cache_prompt_tokens)
    };
  }

  function totalsOf(record) {
    var totals = record ? record.totals : null;
    return {
      input_tokens: num(totals && totals.input_tokens),
      output_tokens: num(totals && totals.output_tokens),
      total_tokens: num(totals && totals.total_tokens),
      consumption_tokens: num(totals && totals.consumption_tokens)
    };
  }

  /* Hits over the requests the source actually spoke about; null when it spoke of none. */
  function requestHitRate(cache) {
    var known = cache.cache_hit_requests + cache.cache_miss_requests;
    return known > 0 ? cache.cache_hit_requests / known : null;
  }

  /* Cache reads over the overlap-aware prompt denominator, per aggregation/cache.py. */
  function tokenHitRate(cache) {
    return cache.cache_prompt_tokens > 0
      ? cache.cache_read_tokens / cache.cache_prompt_tokens
      : null;
  }

  function emptyRow() {
    return {
      request_count: 0, unknown_total_events: 0,
      input_tokens: 0, output_tokens: 0, total_tokens: 0,
      consumption_tokens: 0, reasoning_tokens: 0, cache: emptyCache()
    };
  }

  function addCache(target, source) {
    target.cache_read_tokens += source.cache_read_tokens;
    target.cache_write_tokens += source.cache_write_tokens;
    target.cache_hit_requests += source.cache_hit_requests;
    target.cache_miss_requests += source.cache_miss_requests;
    target.cache_unknown_requests += source.cache_unknown_requests;
    target.cache_prompt_tokens += source.cache_prompt_tokens;
    return target;
  }

  function addRow(target, model) {
    var totals = totalsOf(model);
    target.request_count += num(model.request_count);
    target.unknown_total_events += num(model.unknown_total_events);
    target.input_tokens += totals.input_tokens;
    target.output_tokens += totals.output_tokens;
    target.total_tokens += totals.total_tokens;
    target.consumption_tokens += totals.consumption_tokens;
    addCache(target.cache, cacheOf(model));
    return target;
  }

  function matchesModel(model, modelId) {
    return !modelId || modelId === ALL_MODELS || model.model_id === modelId;
  }

  /* Reduce every model row onto its platform. Returns a map keyed by platform id.
   *
   * The model filter is applied here rather than by the caller so the numbers on
   * screen and the numbers under test come from one code path. Filtering rows the API
   * already returned is exact: the endpoint honours `model_id` server-side too, so this
   * reproduces its arithmetic without a second round trip.
   */
  function aggregateByPlatform(models, modelId) {
    var rows = {};
    (models || []).filter(function (model) { return matchesModel(model, modelId); })
      .forEach(function (model) {
        var row = rows[model.platform] || (rows[model.platform] = emptyRow());
        addRow(row, model);
      });
    return rows;
  }

  /* The model names a platform has actually used, sorted, for that card's dropdown. */
  function modelsForPlatform(models, platformId) {
    var seen = {};
    (models || []).forEach(function (model) {
      if (model.platform === platformId && model.model_id) seen[model.model_id] = true;
    });
    return Object.keys(seen).sort();
  }

  function shortModel(modelId) {
    var id = String(modelId || '');
    var slash = id.lastIndexOf('/');
    var tail = slash >= 0 ? id.slice(slash + 1) : id;
    return tail.length > 28 ? tail.slice(0, 27) + '…' : tail;
  }

  /* --- per-day bars --- */

  function dayLabel(isoDay) {
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    var parts = String(isoDay || '').split('-');
    if (parts.length !== 3) return String(isoDay || '');
    return months[parseInt(parts[1], 10) - 1] + ' ' + parseInt(parts[2], 10);
  }

  function widestBucket(buckets) {
    return (buckets || []).reduce(function (widest, bucket) {
      return Math.max(widest, num(bucket.totals && bucket.totals.total_tokens));
    }, 0);
  }

  function createDayBarRenderer(options) {
    var element = options.element;
    var fmtCompact = options.formatCompact;
    var fmtInteger = options.formatInteger;
    var fmtPercent = options.formatPercent;
    var escapeHtml = options.escapeHtml;

    /* Renders one bucket per row, scaled against the busiest day. The tooltip follows
     * the bar it describes rather than preceding it, so a keyboard focus on the bar
     * reaches the tooltip through the same sibling selector the hover rule uses. */
    function render(buckets, caption) {
      var rows = buckets || [];
      if (!rows.some(hasUsage)) return renderEmpty(caption);
      var widest = widestBucket(rows);
      return captionHtml(caption) + rows.map(function (bucket) {
        return renderDay(bucket, widest);
      }).join('');
    }

    function hasUsage(bucket) {
      return num(bucket.totals && bucket.totals.total_tokens) > 0;
    }

    function captionHtml(caption) {
      return caption ? '<div class="usage-day-caption">' + escapeHtml(caption) + '</div>' : '';
    }

    function renderEmpty(caption) {
      return captionHtml(caption) +
        '<p class="usage-bar-empty" role="status">No usage on any day in this range.</p>';
    }

    function renderDay(bucket, widest) {
      var totals = totalsOf(bucket);
      var cache = cacheOf(bucket);
      var share = widest > 0 ? (totals.total_tokens / widest) * 100 : 0;
      return '<div class="usage-day-row">' +
        '<span class="usage-day-label">' + escapeHtml(dayLabel(bucket.label)) + '</span>' +
        renderTrack(bucket, share, totals) +
        '<span class="usage-day-total">' + fmtCompact(totals.total_tokens) + '</span>' +
        renderTooltip(bucket, totals, cache) +
        '</div>';
    }

    function renderTrack(bucket, share, totals) {
      var label = bucket.label + ': ' + fmtInteger(totals.total_tokens) + ' tokens';
      return '<div class="usage-bar-track" tabindex="0" role="img" aria-label="' +
        escapeHtml(label) + '">' +
        '<div class="usage-bar-fill" style="width:' + share.toFixed(2) + '%"></div></div>';
    }

    function renderTooltip(bucket, totals, cache) {
      return '<div class="usage-bar-tooltip" role="tooltip">' +
        '<div class="usage-tooltip-heading">' + escapeHtml(dayLabel(bucket.label)) + '</div>' +
        metricRows(bucket, totals, cache).join('') + '</div>';
    }

    function metricRows(bucket, totals, cache) {
      var rows = [
        row('Requests', fmtInteger(num(bucket.request_count))),
        row('Input tokens', fmtCompact(totals.input_tokens)),
        row('Output tokens', fmtCompact(totals.output_tokens)),
        row('Total tokens', fmtCompact(totals.total_tokens)),
        row('Cache read', fmtCompact(cache.cache_read_tokens)),
        row('Cache hits', fmtInteger(cache.cache_hit_requests)),
        row('Cache misses', fmtInteger(cache.cache_miss_requests))
      ];
      if (cache.cache_write_tokens > 0) {
        rows.push(row('Cache writes', fmtInteger(cache.cache_write_tokens)));
      }
      if (cache.cache_unknown_requests > 0) {
        rows.push(row('Cache unreported', fmtInteger(cache.cache_unknown_requests)));
      }
      rows.push(rateRow('Request hit rate', requestHitRate(cache)));
      rows.push(rateRow('Token hit rate', tokenHitRate(cache)));
      return rows;
    }

    function row(label, value) {
      return '<div class="usage-tooltip-row"><span>' + label +
        '</span><span class="usage-tooltip-value">' + value + '</span></div>';
    }

    /* An absent measurement reads as a dash, never as a real-looking 0.0%. */
    function rateRow(label, rate) {
      return row(label, rate === null ? '&mdash;' : fmtPercent(rate));
    }

    return {render: render};
  }

  var api = {
    ALL_MODELS: ALL_MODELS,
    aggregateByPlatform: aggregateByPlatform,
    cacheOf: cacheOf,
    createDayBarRenderer: createDayBarRenderer,
    dayLabel: dayLabel,
    emptyCache: emptyCache,
    modelsForPlatform: modelsForPlatform,
    requestHitRate: requestHitRate,
    shortModel: shortModel,
    tokenHitRate: tokenHitRate,
    totalsOf: totalsOf
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TokenlyUsageBreakdown = api;
})(typeof window === 'undefined' ? globalThis : window);