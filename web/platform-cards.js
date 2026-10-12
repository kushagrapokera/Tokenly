(function (root) {
  'use strict';

  function sparklinePaths(values) {
    if (!values.length) return {line: '', area: ''};
    if (values.length === 1) values = [values[0], values[0]];
    var maximum = Math.max.apply(null, values);
    var line = values.map(function (value, index) {
      var x = (2 + index / (values.length - 1) * 196).toFixed(2);
      var y = (34 - (maximum ? value / maximum * 32 : 0)).toFixed(2);
      return (index ? 'L' : 'M') + Number(x) + ',' + Number(y);
    }).join(' ');
    return {line: line, area: line + ' L198,36 L2,36 Z'};
  }

  function summarizeModels(models) {
    var metrics = {total: 0, input: 0, output: 0, requests: 0, modelCount: models.length, topModel: '—'};
    var topTotal = -1;
    models.forEach(function (model) {
      var total = model.totals.total_tokens || 0;
      metrics.total += total;
      metrics.input += model.totals.input_tokens || 0;
      metrics.output += model.totals.output_tokens || 0;
      metrics.requests += model.request_count || 0;
      if (total > topTotal) { topTotal = total; metrics.topModel = model.model_id; }
    });
    return metrics;
  }

  function createRenderer(options) {
    var element = options.element;
    var compact = options.formatCompact;
    var integer = options.formatInteger;
    var escape = options.escapeHtml;

    function inputOutputBar(metrics, color) {
      var known = metrics.input + metrics.output;
      var inputShare = known ? metrics.input / known * 100 : 0;
      var outputShare = known ? metrics.output / known * 100 : 0;
      return '<div class="mt-3 space-y-1">' +
        '<div class="h-1.5 w-full bg-surface-container-low rounded-full overflow-hidden flex" role="img" aria-label="Input ' + inputShare.toFixed(1) + ' percent, output ' + outputShare.toFixed(1) + ' percent">' +
          '<span style="width:' + inputShare + '%;background:' + color + '"></span>' +
          '<span style="width:' + outputShare + '%;background:' + color + ';opacity:0.4"></span>' +
        '</div><div class="flex justify-between gap-2 font-mono text-[10px] text-muted-foreground">' +
          '<span>In: ' + compact(metrics.input) + '</span><span>Out: ' + compact(metrics.output) + '</span>' +
        '</div></div>';
    }

    function cardMarkup(platform, metrics, view) {
      var share = view.grand ? (metrics.total / view.grand * 100).toFixed(1) + '%' : '—';
      var status = view.statuses.find(function (item) { return item.platform === platform.id; });
      return '<div class="spotlight-card relative bg-surface-dark/90 border border-border-dark rounded-xl p-4 min-w-0 flex flex-col justify-between hover:-translate-y-1 transition-all duration-300" data-platform="' + platform.id + '" style="--spotlight-color:' + platform.color + '22">' +
        '<div class="flex items-center justify-between gap-2 mb-3">' +
          '<div class="flex items-center gap-2.5"><span class="w-2 h-2 rounded-full" style="background:' + platform.color + '"></span>' +
          '<h2 class="text-sm font-semibold">' + platform.label + '</h2></div>' +
          '<span class="text-[11px] text-muted-foreground">' + (status && status.available ? 'Connected' : 'Not installed') + '</span></div>' +
        '<div class="font-mono text-2xl font-bold tracking-tight" data-card-total="' + metrics.total + '" style="color:' + platform.color + '">' + compact(metrics.total) + '</div>' +
        '<div class="text-[11px] text-muted-foreground mt-0.5">' + share + ' of total &middot; ' + integer(metrics.requests) + ' requests</div>' +
        inputOutputBar(metrics, platform.color) +
        '<div class="text-[11px] text-muted-foreground mt-3 truncate" title="' + escape(metrics.topModel) + '">Top model: ' + escape(metrics.topModel) + '</div>' +
        '<div class="text-[10px] text-muted-foreground mt-1">' + metrics.modelCount + ' models in range</div>' +
        '<div class="mt-3" id="platform-trend-' + platform.id + '" aria-busy="true"><div class="h-10 rounded bg-surface-container-low"></div><p class="font-mono text-[10px] text-muted-foreground mt-1">Loading daily usage…</p></div></div>';
    }

    function render(view) {
      var container = element('platform-cards-container');
      if (!container) return;
      container.innerHTML = options.platforms.map(function (platform) {
        var models = view.models.filter(function (model) { return model.platform === platform.id; });
        return cardMarkup(platform, summarizeModels(models), view);
      }).join('');
      container.setAttribute('aria-busy', 'false');
    }

    function renderTrend(series) {
      var container = element('platform-trend-' + series.p.id);
      if (!container) return;
      var values = series.buckets.slice().sort(function (a, b) { return a.label.localeCompare(b.label); })
        .map(function (bucket) { return bucket.totals.total_tokens || 0; });
      var paths = sparklinePaths(values);
      var total = values.reduce(function (sum, value) { return sum + value; }, 0);
      var label = series.p.label + ' daily token usage over ' + values.length + ' days';
      var gradientId = 'trend-fill-' + series.p.id;
      container.innerHTML = '<svg class="w-full h-10" viewBox="0 0 200 36" preserveAspectRatio="none" role="img" aria-label="' + escape(label) + '" data-point-count="' + values.length + '" data-trend-total="' + total + '">' +
        '<title>' + escape(label) + '</title><defs><linearGradient id="' + gradientId + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="' + series.p.color + '" stop-opacity="0.25"/><stop offset="100%" stop-color="' + series.p.color + '" stop-opacity="0"/></linearGradient></defs>' +
        '<path d="' + paths.area + '" fill="url(#' + gradientId + ')"/><path data-trend-line d="' + paths.line + '" fill="none" stroke="' + series.p.color + '" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>' +
        '<p class="font-mono text-[10px] text-muted-foreground mt-1">' + (total ? 'Daily usage · Past ' + values.length + ' days' : 'No token usage in this range') + '</p>';
      container.setAttribute('aria-busy', 'false');
    }

    function showTrendError() {
      options.platforms.forEach(function (platform) {
        var container = element('platform-trend-' + platform.id);
        if (!container) return;
        container.setAttribute('aria-busy', 'false');
        container.innerHTML = '<p role="alert" class="h-10 text-xs text-muted-foreground">Daily usage unavailable. Refresh to retry.</p>';
      });
      var container = element('platform-cards-container');
      if (container) container.setAttribute('aria-busy', 'false');
    }

    return {render: render, renderTrend: renderTrend, showTrendError: showTrendError};
  }

  var api = {sparklinePaths: sparklinePaths, summarizeModels: summarizeModels, createRenderer: createRenderer};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TokenlyPlatformCards = api;
})(typeof window === 'undefined' ? globalThis : window);
