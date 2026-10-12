(function (root) {
  'use strict';

  function summarizeSeries(series) {
    var byLabel = {}, totals = {};
    series.forEach(function (entry) {
      totals[entry.p.id] = 0;
      entry.buckets.forEach(function (bucket) {
        if (!byLabel[bucket.label]) byLabel[bucket.label] = {};
        var value = bucket.totals.total_tokens || 0;
        byLabel[bucket.label][entry.p.id] = value;
        totals[entry.p.id] += value;
      });
    });
    var labels = Object.keys(byLabel).sort();
    var maxStacked = 0, maxGrouped = 0;
    labels.forEach(function (label) {
      var values = Object.values(byLabel[label]);
      maxStacked = Math.max(maxStacked, values.reduce(function (sum, value) { return sum + value; }, 0));
      maxGrouped = Math.max(maxGrouped, Math.max.apply(null, values));
    });
    return {labels: labels, byLabel: byLabel, totals: totals, maxStacked: maxStacked, maxGrouped: maxGrouped};
  }

  function columnScale(values, maximum, mode) {
    var total = values.reduce(function (sum, value) { return sum + value; }, 0);
    var denominator = mode === 'grouped' ? maximum : total;
    return {
      height: mode === 'grouped' ? 100 : maximum ? total / maximum * 100 : 0,
      segments: values.map(function (value) { return denominator ? value / denominator * 100 : 0; })
    };
  }

  function createRenderer(options) {
    var qs = options.element;
    var fmtCompact = options.formatCompact;
    var escapeHtml = options.escapeHtml;
    /* Owned by TokenlyUsageBreakdown and injected, so a day reads the same on the
     * chart axis, the chart tooltip, and the per-card bars. */
    var dayLabel = options.dayLabel;

    function render(view) {
      var chartData = view.data;
      var chartPlatforms = view.platforms;
      var chartMode = view.mode;
      if (!chartData) return;
      var container = qs('bar-chart-columns');
      var available = chartPlatforms;
      var labels = chartData.labels;
      var byLabel = chartData.byLabel;
      var max = chartMode === 'grouped' ? chartData.maxGrouped : chartData.maxStacked;
      container.innerHTML = labels.map(function (l, index) {
        var total = available.reduce(function (a, p) { return a + (byLabel[l][p.id] || 0); }, 0);
        var values = available.map(function (p) { return byLabel[l][p.id] || 0; });
        var scale = columnScale(values, max, chartMode);
        var colH = scale.height;
        var segs = available.map(function (p, i) {
          return '<div class="bar-segment" data-platform="' + p.id + '" data-tokens="' + values[i] + '" style="width:' + (chartMode === 'grouped' ? 100 / available.length : 100) + '%;height:' + scale.segments[i].toFixed(3) + '%;background-color:' + p.color + '"></div>';
        }).join('');
        var tipRows = available.map(function (p) {
          return '<div class="flex justify-between text-muted-foreground"><span>' + p.label + ':</span>' +
            '<span class="text-foreground-dark">' + fmtCompact(byLabel[l][p.id] || 0) + '</span></div>';
        }).join('');
        var showLabel = index === 0 || index === labels.length - 1 || index % Math.ceil(labels.length / 8) === 0;
        var wrapperClass = chartMode === 'grouped' ? 'flex-row items-end gap-[2px] max-w-[36px]' : 'flex-col max-w-[26px]';
        return '<div data-date="' + escapeHtml(l) + '" class="bar-hover-col flex-1 flex flex-col justify-end items-center h-full group relative cursor-pointer">' +
          '<div class="bar-column-wrapper w-full rounded-t flex ' + wrapperClass + ' justify-end overflow-hidden transition-all duration-300 group-hover:scale-105 group-hover:shadow-[0_0_14px_rgba(139,92,246,0.3)] border border-border-dark/40 chart-bar-anim" style="height:' + colH.toFixed(1) + '%;">' + segs + '</div>' +
          '<div class="chart-tooltip absolute -top-24 z-30 flex flex-col items-center"><div class="p-2.5 rounded-lg bg-surface-dark/95 border border-opencode-purple/40 text-[10px] font-mono whitespace-nowrap shadow-2xl backdrop-blur-md min-w-[130px]">' +
          '<div class="flex justify-between border-b border-border-dark pb-1 mb-1 font-bold"><span>' + escapeHtml(dayLabel(l)) + '</span><span class="text-opencode-purple">' + fmtCompact(total) + '</span></div>' +
          tipRows + '</div><div class="w-2 h-2 bg-surface-dark rotate-45 border-r border-b border-opencode-purple/40 -mt-1"></div></div>' +
          '<span class="absolute -bottom-5 whitespace-nowrap font-mono text-[10px] text-muted-foreground hidden md:block">' + (showLabel ? escapeHtml(dayLabel(l)) : '') + '</span></div>';
      }).join('');
      renderLegend(available, chartData.totals);
      renderYAxis(max);
      renderChartCaption(max, byLabel, labels, available);
      if (!max) {
        qs('chart-caption').textContent = 'No token usage for ' + (view.platform ? available[0].label : 'these platforms') + ' in the past ' + view.days + ' days.';
      }
    }

    function renderLegend(available, totals) {
      var legend = qs('platform-legend');
      if (!legend) return;
      /* summarizeSeries already totalled each platform across every bucket, so the
       * legend reads those numbers instead of re-summing byLabel a second time. */
      var source = totals || {};
      var grand = available.reduce(function (a, p) { return a + (source[p.id] || 0); }, 0);
      legend.innerHTML = available.map(function (p) {
        var total = source[p.id] || 0;
        var share = grand ? ((total / grand) * 100).toFixed(1) + '%' : '—';
        return '<div class="flex items-center gap-1.5 cursor-pointer hover:opacity-80 transition-opacity" onclick="togglePlatformHighlight(\'' + p.id + '\')">' +
          '<span class="w-2.5 h-2.5 rounded-sm" style="background-color:' + p.color + ';box-shadow:0 0 6px ' + p.color + '"></span>' +
          '<span class="text-foreground-dark font-medium">' + p.label + '</span>' +
          '<span class="px-1 py-0.2 rounded bg-surface-container-high text-muted-foreground text-[10px]">' + fmtCompact(total) + ' (' + share + ')</span></div>';
      }).join('');
    }

    function renderYAxis(max) {
      var axis = qs('chart-y-axis');
      if (!axis) return;
      var steps = [max, max * 0.75, max * 0.5, max * 0.25, 0];
      var spans = axis.querySelectorAll('span');
      steps.forEach(function (v, i) {
        if (spans[i]) spans[i].textContent = fmtCompact(Math.round(v));
      });
    }

    function renderChartCaption(max, byLabel, labels, available) {
      var caption = qs('chart-caption');
      if (!caption) return;
      var peak = 0;
      var peakLabel = '';
      labels.forEach(function (l) {
        var sum = available.reduce(function (a, p) { return a + (byLabel[l][p.id] || 0); }, 0);
        if (sum > peak) { peak = sum; peakLabel = l; }
      });
      var interval = max ? fmtCompact(Math.round(max / 4)) : '—';
      caption.innerHTML = '<span>Grid: ' + interval + ' interval</span><span>•</span>' +
        '<span class="text-amber-400 font-medium flex items-center gap-1.5">' +
        '<span class="relative flex h-1.5 w-1.5 text-amber-400"><span class="beacon-ring"></span>' +
        '<span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber-400"></span></span>' +
        'Peak: ' + fmtCompact(peak) + ' tokens (' + escapeHtml(peakLabel ? dayLabel(peakLabel) : '—') + ')</span>';
    }

    function clear() {
      renderLegend([]);
      renderYAxis(0);
      var caption = qs('chart-caption');
      if (caption) caption.textContent = 'Usage data unavailable';
    }
    return {render: render, clear: clear};
  }

  var api = {summarizeSeries: summarizeSeries, columnScale: columnScale, createRenderer: createRenderer};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TokenlyUsageChart = api;
})(typeof window === 'undefined' ? globalThis : window);
