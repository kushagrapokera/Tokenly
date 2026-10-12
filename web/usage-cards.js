/* Platform cards for the Detailed Platform Usage Breakdown.
 *
 * Each platform gets one card. The card is a summary first — totals, cache hits,
 * cache misses, input and output — with its own model dropdown in the corner. Choosing
 * a model swaps that card's body for a per-day usage bar list, so one platform can be
 * drilled into while its neighbours keep showing summaries.
 *
 * This module renders only. It never fetches: the app hands it the day series it
 * already loaded and receives model changes back through a callback. That split keeps
 * the markup testable in Node without a browser or a network.
 */
(function (root) {
  'use strict';

  var METRIC_ORDER = ['total_tokens', 'requests', 'cache_read_tokens',
    'cache_hit_requests', 'cache_miss_requests', 'input_tokens', 'output_tokens'];

  function createRenderer(options) {
    var element = options.element;
    var bars = options.dayBars;
    var fmtCompact = options.formatCompact;
    var fmtInteger = options.formatInteger;
    var fmtPercent = options.formatPercent;
    var escapeHtml = options.escapeHtml;
    var rates = options.rates;

    function render(view) {
      var grid = element('usage-card-grid');
      if (!grid) return;
      var shown = visiblePlatforms(view);
      var focused = !!view.platformFilter && shown.length === 1;
      grid.setAttribute('data-focused', String(focused));
      grid.innerHTML = shown.map(function (platform) {
        return renderCard(platform, view);
      }).join('');
      if (focused) {
        grid.innerHTML += options.modelRanking.render({
          platform: shown[0], models: view.models, rangeLabel: view.rangeLabel
        });
      }
      describe(view, shown);
    }

    /* A platform with no stored usage still earns a card: an absent card would read
     * as "this assistant is gone" rather than "it was quiet this week". */
    function visiblePlatforms(view) {
      return view.platforms.filter(function (platform) {
        return !view.platformFilter || platform.id === view.platformFilter;
      });
    }

    function renderCard(platform, view) {
      var metrics = view.rows[platform.id] || null;
      var selected = view.modelByPlatform[platform.id] || '';
      return '<article class="usage-card spotlight-card hover:-translate-y-1 transition-all duration-300" data-platform="' + escapeHtml(platform.id) + '" style="--spotlight-color:' + platform.color + '22">' +
        renderCardHead(platform, metrics, view) +
        renderModelSelect(platform, view, selected) +
        (selected ? renderDrillDown(platform, selected, view)
                  : renderMetrics(metrics)) +
        '</article>';
    }

    function renderCardHead(platform, metrics, view) {
      var status = view.statusFor ? view.statusFor(platform.id) : null;
      return '<header class="usage-card-head">' +
        '<span class="usage-card-swatch" style="background:' + platform.color + '"></span>' +
        '<h3 class="usage-card-name">' + escapeHtml(platform.label) + '</h3>' +
        renderBadge(status) +
        '</header>';
    }

    function renderBadge(status) {
      if (!status) return '';
      var tone = status.available ? 'live' : 'historical';
      return '<span class="usage-card-badge usage-card-badge-' + tone + '">' +
        (status.available ? 'Live' : 'Historical') + '</span>';
    }

    /* The placeholder is the way back: it is the card's default, unselected state. */
    function renderModelSelect(platform, view, selected) {
      var options = [placeholderOption(selected)].concat(
        view.modelsFor(platform.id).map(function (modelId) {
          return option(modelId, escapeHtml(modelId), modelId === selected);
        })
      ).join('');
      return '<div class="usage-card-models">' +
        '<label class="sr-only" for="usage-model-' + escapeHtml(platform.id) + '">' +
        'Model for ' + escapeHtml(platform.label) + '</label>' +
        '<select class="usage-model-select" id="usage-model-' + escapeHtml(platform.id) +
        '" data-platform="' + escapeHtml(platform.id) + '">' + options + '</select>' +
        '</div>';
    }

    function placeholderOption(selected) {
      var label = selected ? 'Change model' : 'Choose a model';
      return option('', label, !selected);
    }

    function option(value, label, isSelected) {
      return '<option value="' + value + '"' + (isSelected ? ' selected' : '') + '>' +
        label + '</option>';
    }

    function renderDrillDown(platform, modelId, view) {
      var series = view.daySeriesFor(platform.id, modelId);
      return '<div class="usage-card-days">' + renderDayHeader(modelId) +
        bars.render(series.buckets, null) + '</div>';
    }

    function renderDayHeader(modelId) {
      return '<div class="usage-day-head">' +
        '<span class="usage-day-model">' + escapeHtml(rates.shortModel(modelId)) + '</span>' +
        '<span class="usage-day-hint">Hover a day for cache detail</span>' +
        '</div>';
    }

    /* The card body is the seven figures worth scanning at a glance, in a fixed order
     * so two cards can be compared down the columns without reading them. */
    function renderMetrics(metrics) {
      if (!metrics) return renderNoUsage();
      var values = metricValues(metrics);
      return '<dl class="usage-metrics">' + METRIC_ORDER.map(function (key) {
        return metricCell(key, values[key]);
      }).join('') + renderRateCell(metrics) + '</dl>';
    }

    function metricValues(metrics) {
      var cache = metrics.cache;
      return {
        total_tokens: metrics.total_tokens,
        requests: metrics.request_count,
        cache_read_tokens: cache.cache_read_tokens,
        cache_hit_requests: cache.cache_hit_requests,
        cache_miss_requests: cache.cache_miss_requests,
        input_tokens: metrics.input_tokens,
        output_tokens: metrics.output_tokens
      };
    }

    function metricCell(key, value) {
      return '<div class="usage-metric"><dt>' + metricLabel(key) + '</dt><dd>' +
        fmtInteger(value) + '</dd></div>';
    }

    function renderRateCell(metrics) {
      var request = rates.requestHitRate(metrics.cache);
      var token = rates.tokenHitRate(metrics.cache);
      return '<div class="usage-metric usage-metric-rate"><dt>Hit rate</dt><dd>' +
        rateValue(request) + ' <span class="usage-metric-alt">' + rateValue(token) + '</span>' +
        '</dd></div>';
    }

    function rateValue(rate) {
      return rate === null ? '—' : fmtPercent(rate);
    }

    function renderNoUsage() {
      return '<p class="usage-bar-empty" role="status">No stored usage in this range.</p>';
    }

    function metricLabel(key) {
      return {
        total_tokens: 'Total tokens', requests: 'Requests',
        cache_read_tokens: 'Cache read', cache_hit_requests: 'Cache hits',
        cache_miss_requests: 'Cache misses', input_tokens: 'Input',
        output_tokens: 'Output'
      }[key];
    }

    function describe(view, shown) {
      var caption = element('usage-card-caption');
      if (!caption) return;
      var used = shown.filter(function (platform) {
        return view.rows[platform.id] && view.rows[platform.id].total_tokens > 0;
      });
      var drilled = shown.filter(function (platform) {
        return view.modelByPlatform[platform.id];
      });
      caption.textContent = describeRange(view, shown.length) + describeDrillDown(drilled);
    }

    function describeRange(view, count) {
      var scope = view.platformFilter ? ' for one platform' : ' across ' + count + ' platforms';
      return 'Usage' + scope + ' in ' + view.rangeLabel + '.';
    }

    function describeDrillDown(drilled) {
      return drilled.length
        ? ' ' + drilled.length + ' card' + (drilled.length > 1 ? 's are' : ' is') +
          ' showing one model by day.'
        : '';
    }

    function clear(message) {
      var grid = element('usage-card-grid');
      if (grid) {
        grid.innerHTML = '<p class="usage-bar-empty" role="alert">' +
          escapeHtml(message || 'Usage data unavailable') + '</p>';
      }
      var caption = element('usage-card-caption');
      if (caption) caption.textContent = '';
    }

    return {render: render, clear: clear};
  }

  var api = {createRenderer: createRenderer};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TokenlyUsageCards = api;
})(typeof window === 'undefined' ? globalThis : window);
