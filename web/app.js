/* Tokenly dashboard — wires the static design to the local FastAPI backend.
 *
 * The HTML/CSS is the design shell; every number here comes from /api. Nothing
 * is hardcoded. Vanilla JS, no build step.
 */
(function () {
  'use strict';

  var PLATFORMS = [
    { id: 'opencode', label: 'OpenCode', color: '#8b5cf6' },
    { id: 'cline', label: 'Cline', color: '#06b6d4' },
    { id: 'claude_code', label: 'Claude Code', color: '#10b981' },
    { id: 'codex', label: 'Codex', color: '#f59e0b' }
  ];
  var state = {
    days: 7,
    platform: null,
    statuses: [],
    sectionPlatform: '',
    // One model per platform: drilling into OpenCode must not disturb Cline's card.
    modelByPlatform: {},
    daySeries: {}
  };
  var loadVersion = 0;
  var lastBreakdown = null;
  var chartData = null;
  var chartPlatforms = [];
  var chartMode = 'stacked';
  // dayBarRenderer is declared first: the card renderer is handed it as a dependency,
  // and a `var` referenced before its assignment would arrive undefined.
  var dayBarRenderer = TokenlyUsageBreakdown.createDayBarRenderer({
    element: qs, formatCompact: fmtCompact, formatInteger: fmtInt,
    formatPercent: fmtPct, escapeHtml: escapeHtml
  });
  var breakdownRenderer = TokenlyUsageCards.createRenderer({
    element: qs, dayBars: dayBarRenderer, formatCompact: fmtCompact,
    formatInteger: fmtInt, formatPercent: fmtPct, escapeHtml: escapeHtml,
    rates: TokenlyUsageBreakdown,
    modelRanking: TokenlyModelRanking.createRenderer({
      formatCompact: fmtCompact, formatInteger: fmtInt, escapeHtml: escapeHtml
    })
  });
  var overviewCardRenderer = TokenlyPlatformCards.createRenderer({
    element: qs, formatCompact: fmtCompact, formatInteger: fmtInt,
    escapeHtml: escapeHtml, platforms: PLATFORMS
  });
  var chartRenderer = TokenlyUsageChart.createRenderer({
    element: qs, formatCompact: fmtCompact, escapeHtml: escapeHtml,
    dayLabel: TokenlyUsageBreakdown.dayLabel
  });

  function qs(id) { return document.getElementById(id); }
  function fmtInt(n) { return (n || 0).toLocaleString(); }

  // Cache rates arrive as fractions, and as null when there is no denominator to divide
  // by. A null is rendered as an empty cell rather than 0.0%, so an absent measurement is
  // never mistaken for a real zero.
  function fmtPct(fraction) {
    if (fraction === null || fraction === undefined) return '';
    return (fraction * 100).toFixed(1) + '%';
  }
  function fmtCompact(n) {
    n = n || 0;
    if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(2) + 'K';
    return String(n);
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function rangeParams() {
    return TokenlyUsageFilters.rangeParams(state.days);
  }
  function fetchJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + ' -> ' + r.status);
      return r.json();
    });
  }
  function statusFor(id) {
    for (var i = 0; i < state.statuses.length; i++) {
      if (state.statuses[i].platform === id) return state.statuses[i];
    }
    return null;
  }

  function load() {
    var version = ++loadVersion;
    var params = rangeParams();
    var days = state.days;
    syncRangeControls();
    var chart = qs('bar-chart-columns');
    if (chart) chart.setAttribute('aria-busy', 'true');
    console.info('Tokenly loading usage', {days: days, platform: state.platform});
    return Promise.all([
      fetchJson('/api/collector/status'),
      fetchJson('/api/usage/summary?' + params),
      fetchJson('/api/usage/models?' + params)
    ]).then(function (res) {
      if (version !== loadVersion) return;
      state.statuses = res[0].collectors || [];
      lastBreakdown = res[2];
      state.daySeries = {};
      renderHeader();
      renderCards(res[1], res[2]);
      renderMiniCards(res[2]);
      return loadDaySeries(params, version)
        .then(function () { if (version === loadVersion) renderBreakdown(res[2]); })
        .then(function () { return renderChart(params, version); });
    }).catch(function (err) {
      if (version !== loadVersion) return;
      console.error('Tokenly load failed', err);
      breakdownRenderer.clear('Could not reach the Tokenly API. Start the backend (python main.py), then refresh.');
      showChartError(err);
    });
  }

  function renderHeader() {
    var available = state.statuses.filter(function (s) { return s.available; });
    setTextStartingWith('Nodes Active', available.length + ' Nodes Active');
  }

  function setTextStartingWith(needle, text) {
    var nodes = document.querySelectorAll('span, div, p');
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].children.length === 0 && nodes[i].textContent.indexOf(needle) === 0) {
        nodes[i].textContent = text;
        return;
      }
    }
  }

  function renderCards(summary, breakdown) {
    overviewCardRenderer.render({grand: summary.totals.total_tokens || 0,
      models: breakdown.models, statuses: state.statuses});
  }

  function renderBreakdown(breakdown) {
    syncPlatformFilter();
    breakdownRenderer.render({
      models: breakdown.models,
      rows: TokenlyUsageBreakdown.aggregateByPlatform(breakdown.models, ''),
      platforms: PLATFORMS,
      platformFilter: effectivePlatform(),
      rangeLabel: rangeLabel(),
      statusFor: statusFor,
      modelByPlatform: state.modelByPlatform,
      modelsFor: function (platformId) {
        return TokenlyUsageBreakdown.modelsForPlatform(breakdown.models, platformId);
      },
      daySeriesFor: daySeriesFor
    });
    var grid = qs('usage-card-grid');
    if (grid) grid.setAttribute('aria-busy', 'false');
    TokenlyDropdowns.enhance();
  }

  /* The section's own dropdown wins over the page-wide one, since choosing here is the
   * more recent and more specific act. Without this the header's "Cline" filter would
   * still leave OpenCode cards below it, which reads as a broken filter. */
  function effectivePlatform() {
    return state.sectionPlatform || state.platform || '';
  }

  /* A missing series renders as an empty state rather than a crash: a model can be
     chosen whose usage falls entirely outside the current range. */
  function daySeriesFor(platformId, modelId) {
    var series = state.daySeries[platformId];
    return series && series.modelId === modelId ? series : {modelId: modelId, buckets: []};
  }

  function syncPlatformFilter() {
    var select = qs('usage-platform-filter');
    if (!select) return;
    var effective = effectivePlatform();
    // "All platforms" must also read as chosen when only the page-wide filter is set,
    // otherwise the dropdown would claim a breadth the grid is not showing.
    var shown = state.sectionPlatform || effective;
    select.innerHTML = [option('', 'All platforms')].concat(PLATFORMS.map(function (platform) {
      return option(platform.id, platform.label);
    })).join('');
    select.value = shown;
  }

  function option(value, label) {
    return '<option value="' + escapeHtml(value) + '">' + escapeHtml(label) + '</option>';
  }

  function rangeLabel() {
    return 'the last ' + state.days + ' days';
  }

  function renderMiniCards(breakdown) {
    // The four "Avg / Prompt" tiles under the chart are static demo numbers in the
    // mockup (3,420 / 4,110 / 5,840 / 2,190). Replace with total/requests per platform.
    var tiles = document.querySelectorAll('[data-avg-prompt]');
    if (!tiles.length) return;
    var byPlatform = {};
    PLATFORMS.forEach(function (p) { byPlatform[p.id] = { total: 0, requests: 0 }; });
    (breakdown.models || []).forEach(function (m) {
      var slot = byPlatform[m.platform];
      if (!slot) return;
      slot.total += m.totals.total_tokens || 0;
      slot.requests += m.request_count || 0;
    });
    tiles.forEach(function (el) {
      var slot = byPlatform[el.getAttribute('data-avg-prompt')] || { total: 0, requests: 0 };
      var avg = slot.requests ? Math.round(slot.total / slot.requests) : 0;
      var num = el.querySelector('[data-avg-value]');
      if (num) {
        num.textContent = fmtInt(avg);
        num.setAttribute('data-target', String(avg));
      }
      var sub = el.querySelector('[data-avg-sub]');
      if (sub) sub.textContent = slot.requests ? fmtInt(slot.requests) + ' requests' : 'No usage in range';
      var delta = el.querySelector('[data-avg-delta]');
      if (delta) delta.style.display = 'none';
    });
  }

  /* One request per drilled-in card. Cards showing a summary need no series, so an
   * untouched dashboard issues none of these. */
  function loadDaySeries(params, version) {
    var pending = Object.keys(state.modelByPlatform)
      .filter(function (platformId) { return !!state.modelByPlatform[platformId]; })
      .map(function (platformId) {
        return loadPlatformDaySeries(platformId, params)
          .catch(function (error) {
            console.error('Tokenly day series failed for ' + platformId, error);
            return null;
          });
      });
    return Promise.all(pending);
  }

  function loadPlatformDaySeries(platformId, params) {
    var modelId = state.modelByPlatform[platformId];
    var url = '/api/usage/timeline?' + params + '&granularity=day&platform=' +
      encodeURIComponent(platformId) + '&model_id=' + encodeURIComponent(modelId);
    return fetchJson(url).then(function (timeline) {
      state.daySeries[platformId] = {modelId: modelId, buckets: timeline.buckets || []};
    });
  }

  function renderChart(params, version) {
    var container = qs('bar-chart-columns');
    if (!container) return Promise.resolve();
    // Stored history remains visible even when its collector is no longer installed.
    var available = PLATFORMS.filter(function (platform) {
      return !state.platform || platform.id === state.platform;
    });
    return Promise.all(PLATFORMS.map(function (p) {
      return fetchJson('/api/usage/timeline?' + params + '&granularity=day&platform=' + p.id)
        .then(function (timeline) { return {p: p, buckets: timeline.buckets || []}; });
    })).then(function (series) {
      if (version !== loadVersion) return;
      series.forEach(overviewCardRenderer.renderTrend);
      var selectedSeries = series.filter(function (entry) { return !state.platform || entry.p.id === state.platform; });
      chartData = TokenlyUsageChart.summarizeSeries(selectedSeries);
      chartPlatforms = available;
      drawChart();
      container.setAttribute('aria-busy', 'false');
      console.info('Tokenly chart loaded', {days: chartData.labels.length, platform: state.platform});
    }).catch(function (error) {
      if (version === loadVersion) showChartError(error);
    });
  }

  function showChartError(error) {
    console.error('Tokenly chart failed', error);
    chartData = null;
    var container = qs('bar-chart-columns');
    if (container) {
      container.setAttribute('aria-busy', 'false');
      container.innerHTML = '<p role="alert" class="p-4 text-xs text-muted-foreground">Could not load usage for this range. Refresh to retry.</p>';
    }
    chartRenderer.clear();
    overviewCardRenderer.showTrendError();
  }

  function drawChart() {
    chartRenderer.render({data: chartData, platforms: chartPlatforms, mode: chartMode,
      days: state.days, platform: state.platform});
  }

  function wire() {
    var group = qs('timeframe-group');
    if (group) {
      group.querySelectorAll('button').forEach(function (btn) {
        btn.addEventListener('click', function () {
          selectRange(parseInt(btn.getAttribute('data-range'), 10));
        });
      });
    }
    document.addEventListener('tokenly:range', function (event) { selectRange(event.detail); });
    document.addEventListener('tokenly:platform', function (event) {
      state.platform = TokenlyUsageFilters.platformId(event.detail);
      load();
    });
    document.addEventListener('tokenly:chart-mode', function (event) {
      chartMode = event.detail;
      ['stacked', 'grouped'].forEach(function (mode) {
        var button = qs('toggle-' + mode + '-btn');
        var selected = chartMode === mode;
        button.setAttribute('aria-pressed', String(selected));
        button.classList.toggle('bg-surface-container-high', selected);
        button.classList.toggle('text-foreground-dark', selected);
        button.classList.toggle('text-muted-foreground', !selected);
      });
      drawChart();
    });
    var platformFilter = qs('usage-platform-filter');
    if (platformFilter) {
      platformFilter.addEventListener('change', function () {
        state.sectionPlatform = platformFilter.value;
        redrawBreakdown();
      });
    }
    var rangeFilter = qs('usage-range-filter');
    if (rangeFilter) {
      rangeFilter.addEventListener('change', function () {
        selectRange(Number(rangeFilter.value));
      });
    }
    // Each card renders its own select, so the listener is delegated from the grid.
    var grid = qs('usage-card-grid');
    if (grid) {
      grid.addEventListener('change', function (event) {
        if (event.target.classList.contains('usage-model-select')) {
          selectCardModel(event.target.getAttribute('data-platform'), event.target.value);
        }
      });
    }
    var exportBtn = qs('export-csv-btn');
    if (exportBtn) exportBtn.addEventListener('click', exportCsv);
  }

  function selectRange(days) {
    state.days = days;
    load();
  }

  function syncRangeControls() {
    qs('filter-duration-label').textContent = 'Past ' + state.days + ' Days';
    var rangeFilter = qs('usage-range-filter');
    if (rangeFilter) rangeFilter.value = String(state.days);
    document.querySelectorAll('#timeframe-group button').forEach(function (button) {
      var selected = parseInt(button.getAttribute('data-range'), 10) === state.days;
      button.setAttribute('aria-pressed', String(selected));
      button.classList.toggle('text-foreground-dark', selected);
      button.classList.toggle('font-semibold', selected);
      button.classList.toggle('text-muted-foreground', !selected);
      if (selected) {
        qs('timeframe-pill').style.left = button.getAttribute('data-left');
        qs('timeframe-pill').style.width = button.getAttribute('data-width');
      }
    });
    document.querySelectorAll('#filter-duration-menu button').forEach(function (button) {
      var selected = parseInt(button.getAttribute('data-duration').match(/\d+/)[0], 10) === state.days;
      button.setAttribute('aria-pressed', String(selected));
      button.classList.toggle('text-opencode-purple', selected);
      button.classList.toggle('text-muted-foreground', !selected);
      var check = button.querySelector('.material-symbols-outlined');
      if (check) check.remove();
      if (selected) button.insertAdjacentHTML('beforeend', '<span class="material-symbols-outlined text-[14px]">check</span>');
    });
    var description = qs('usage-breakdown-description');
    if (description) {
      description.textContent = 'Usage across active platforms for ' + rangeLabel() + '.';
    }
    TokenlyDropdowns.enhance();
  }

  /* Choosing a model swaps that one card to a day series and leaves the rest alone. */
  function selectCardModel(platformId, modelId) {
    state.modelByPlatform[platformId] = modelId;
    if (!modelId) delete state.daySeries[platformId];
    if (!lastBreakdown) return;
    if (!modelId) { redrawBreakdown(); return; }
    loadPlatformDaySeries(platformId, rangeParams())
      .then(function () { redrawBreakdown(); })
      .catch(function (error) {
        console.error('Tokenly day series failed for ' + platformId, error);
        redrawBreakdown();
      });
  }

  /* Re-rendering from the last response keeps a switch instant: the models endpoint
   * already returned every model for this range, so no second round trip is needed. */
  function redrawBreakdown() {
    if (lastBreakdown) renderBreakdown(lastBreakdown);
  }

  /* Reports what actually happened, so a failed export never claims success. */
  function setExportState(state, label, icon) {
    var text = qs('export-text');
    var glyph = qs('export-icon');
    if (text) text.textContent = label;
    if (!glyph) return;
    glyph.textContent = icon;
    glyph.classList.toggle('animate-spin', state === 'busy');
    glyph.classList.toggle('text-opencode-purple', state === 'busy');
    glyph.classList.toggle('text-claude-emerald', state === 'done');
    glyph.classList.toggle('text-red-400', state === 'failed');
  }

  function exportCsv() {
    var button = qs('export-csv-btn');
    if (button) button.classList.add('scale-95');
    setExportState('busy', 'Generating...', 'progress_activity');
    fetchJson('/api/usage/models?' + rangeParams()).then(function (b) {
      var rows = [['platform', 'provider', 'model', 'requests', 'input', 'output', 'total',
        'cache_read', 'cache_write', 'cache_hits', 'cache_misses', 'cache_unknown',
        'request_hit_pct', 'token_hit_pct']];
      (b.models || []).forEach(function (m) {
        var cache = (m.totals && m.totals.cache) || {};
        rows.push([m.platform, m.provider_id, m.model_id, m.request_count,
          m.totals.input_tokens, m.totals.output_tokens, m.totals.total_tokens,
          cache.cache_read_tokens, cache.cache_write_tokens, cache.cache_hit_requests,
          cache.cache_miss_requests, cache.cache_unknown_requests,
          fmtPct(cache.request_hit_rate), fmtPct(cache.token_hit_rate)]);
      });
      var csv = rows.map(function (r) {
        return r.map(function (c) { return '"' + String(c).replace(/"/g, '""') + '"'; }).join(',');
      }).join('\n');
      var blob = new Blob([csv], { type: 'text/csv' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'tokenly-usage.csv';
      a.click();
      URL.revokeObjectURL(a.href);
      setExportState('done', 'Downloaded!', 'check_circle');
    }).catch(function (error) {
      console.error('Tokenly CSV export failed', error);
      setExportState('failed', 'Export failed', 'error');
    }).then(function () {
      if (button) button.classList.remove('scale-95');
      window.setTimeout(function () {
        setExportState('idle', 'Export CSV', 'download');
      }, 2000);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { wire(); load(); });
  } else {
    wire();
    load();
  }
})();
