/* Read-only comparison of the selected platform's models in the active range. */
(function (root) {
  'use strict';

  function rankModels(models, platformId) {
    var grouped = new Map();
    (models || []).forEach(function (model) {
      if (model.platform !== platformId) return;
      var row = grouped.get(model.model_id) || {
        model_id: model.model_id, total_tokens: 0, request_count: 0
      };
      row.total_tokens += (model.totals && model.totals.total_tokens) || 0;
      row.request_count += model.request_count || 0;
      grouped.set(model.model_id, row);
    });
    return Array.from(grouped.values()).sort(function (a, b) {
      return b.total_tokens - a.total_tokens || a.model_id.localeCompare(b.model_id);
    });
  }

  function createRenderer(options) {
    var compact = options.formatCompact;
    var integer = options.formatInteger;
    var escape = options.escapeHtml;

    function renderRow(row, maximum, color) {
      var width = maximum ? row.total_tokens / maximum * 100 : 0;
      return '<li class="model-ranking-row" data-model="' + escape(row.model_id) + '" data-tokens="' + row.total_tokens + '" data-requests="' + row.request_count + '">' +
        '<div class="model-ranking-label"><span class="model-ranking-name" title="' + escape(row.model_id) + '">' + escape(row.model_id) + '</span>' +
        '<span class="model-ranking-total" title="' + integer(row.total_tokens) + ' tokens">' + compact(row.total_tokens) + ' tokens</span></div>' +
        '<div class="model-ranking-bar-line"><div class="model-ranking-track" aria-hidden="true"><span class="model-ranking-fill" style="width:' + width + '%;background:' + color + '"></span></div>' +
        '<span class="model-ranking-requests">' + integer(row.request_count) + (row.request_count === 1 ? ' request' : ' requests') + '</span></div></li>';
    }

    function render(view) {
      var rows = rankModels(view.models, view.platform.id);
      var maximum = rows.length ? rows[0].total_tokens : 0;
      var body = rows.length ? '<ol class="model-ranking-list">' + rows.map(function (row) {
        return renderRow(row, maximum, view.platform.color);
      }).join('') + '</ol>' : '<p class="usage-bar-empty" role="status">No models recorded in this range.</p>';
      return '<aside class="usage-model-ranking" aria-labelledby="model-ranking-title">' +
        '<h3 class="model-ranking-title" id="model-ranking-title">Model comparison</h3>' +
        '<p class="model-ranking-description">' + escape(view.platform.label) + ' · ' + escape(view.rangeLabel) + ' · Ranked by token usage</p>' + body + '</aside>';
    }

    return {render: render};
  }

  var api = {rankModels: rankModels, createRenderer: createRenderer};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TokenlyModelRanking = api;
})(typeof window === 'undefined' ? globalThis : window);
