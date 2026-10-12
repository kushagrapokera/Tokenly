// Run with NODE_PATH pointing to an installed Puppeteer module and TOKENLY_URL
// pointing to the local server. API fixtures distinguish recent and older usage.
const assert = require('node:assert/strict');
const puppeteer = require('puppeteer');

const baseUrl = process.env.TOKENLY_URL || 'http://127.0.0.1:8000';
const platforms = ['opencode', 'cline', 'claude_code', 'codex'];
let failTimeline = false;
let delayedDays = null;
const requests = [];

function timeline(params, platform) {
  const start = new Date(params.get('start'));
  const days = Math.round((new Date(params.get('end')) - start) / 86400000);
  return Array.from({length: days}, (_, index) => {
    let tokens = index === days - 1 ? {opencode: 100, cline: 200}[platform] || 0 : 0;
    if (platform === 'opencode' && index === days - 20) tokens += 300;
    if (platform === 'opencode' && index === days - 60) tokens += 500;
    return {label: new Date(start.getTime() + index * 86400000).toISOString().slice(0, 10), totals: {total_tokens: tokens}};
  });
}

async function mockApi(request) {
  const url = new URL(request.url());
  if (!url.pathname.startsWith('/api/')) return request.continue();
  const params = url.searchParams;
  requests.push(url);
  let body;
  if (url.pathname === '/api/collector/status') {
    body = {collectors: platforms.map(platform => ({platform, available: platform !== 'cline'}))};
  } else {
    const models = platforms.map(platform => ({platform, model_id: platform + '-model', request_count: 1,
      totals: {total_tokens: timeline(params, platform).reduce((sum, bucket) => sum + bucket.totals.total_tokens, 0)}}));
    if (url.pathname.endsWith('/summary')) body = {totals: {total_tokens: models.reduce((sum, model) => sum + model.totals.total_tokens, 0)}};
    if (url.pathname.endsWith('/models')) body = {models};
    if (url.pathname.endsWith('/timeline')) body = {buckets: timeline(params, params.get('platform'))};
    if (delayedDays === timeline(params, 'opencode').length) await new Promise(resolve => setTimeout(resolve, 500));
  }
  return request.respond({status: failTimeline && url.pathname.endsWith('/timeline') ? 503 : 200,
    contentType: 'application/json', body: JSON.stringify(body)});
}

async function waitForChart(page, days, platform) {
  await page.waitForFunction((count, selected) => {
    const chart = document.getElementById('bar-chart-columns');
    const bars = chart.querySelectorAll('.bar-hover-col');
    const segments = Array.from(chart.querySelectorAll('.bar-segment'));
    return chart.getAttribute('aria-busy') === 'false' && bars.length === count &&
      (!selected || segments.every(segment => segment.dataset.platform === selected));
  }, {}, days, platform);
}

async function assertCardTrends(page, days) {
  const trends = await page.$$eval('#platform-cards-container [data-platform]', cards => cards.map(card => {
    const graph = card.querySelector('svg[data-point-count]');
    const bounds = graph.getBoundingClientRect();
    return {points: Number(graph.dataset.pointCount), total: Number(graph.dataset.trendTotal),
      cardTotal: Number(card.querySelector('[data-card-total]').dataset.cardTotal),
      visible: bounds.width > 0 && bounds.height > 0, path: graph.querySelector('[data-trend-line]').getAttribute('d')};
  }));
  assert.equal(trends.length, 4);
  for (const trend of trends) {
    assert.equal(trend.points, days);
    assert.equal(trend.total, trend.cardTotal);
    assert.ok(trend.visible && trend.path.startsWith('M'));
  }
}

async function assertBreakdownTotal(page, platform, expected) {
  const value = await page.$eval(`.usage-card[data-platform="${platform}"] .usage-metrics dd`,
    element => Number(element.textContent.replace(/,/g, '')));
  assert.equal(value, expected);
  assert.equal(await page.$$eval('#usage-card-grid [role="alert"]', elements => elements.length), 0);
}

async function chooseMenu(page, button, selector) {
  await page.click(button);
  await page.click(selector);
}

(async () => {
  const browser = await puppeteer.launch({headless: true,
    executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome-stable', args: ['--no-sandbox']});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewport({width: 1600, height: 1200});
    await page.emulateTimezone('Asia/Kolkata');
    await page.setRequestInterception(true);
    page.on('request', request => mockApi(request).catch(error => {errors.push(error.message); request.abort();}));
    await page.goto(baseUrl, {waitUntil: 'networkidle0'});
    await waitForChart(page, 7);
    await assertCardTrends(page, 7);
    await assertBreakdownTotal(page, 'opencode', 100);
    await assertBreakdownTotal(page, 'cline', 200);
    assert.equal(await page.$eval('#filter-duration-label', element => element.textContent), 'Past 7 Days');

    for (const [days, total] of [[7, 100], [30, 400], [90, 900], [7, 100]]) {
      await chooseMenu(page, '#usage-range-filter-trigger', `#usage-range-filter-menu [data-value="${days}"]`);
      await waitForChart(page, days);
      await assertBreakdownTotal(page, 'opencode', total);
      await assertCardTrends(page, days);
      assert.equal(await page.$eval('#filter-duration-label', element => element.textContent), `Past ${days} Days`);
    }
    console.log('PASS detailed range dropdown loads 7/30/90 days and synchronizes other date controls');

    for (const [days, total] of [[30, 400], [90, 900], [7, 100]]) {
      await chooseMenu(page, '#filter-duration-btn', `[data-duration="Past ${days} Days"]`);
      await waitForChart(page, days);
      await assertCardTrends(page, days);
      assert.equal(await page.$eval('#usage-range-filter', element => element.value), String(days));
      assert.equal(await page.$eval('#timeframe-group [aria-pressed="true"]', element => element.dataset.range), days + 'D');
      const actual = await page.$$eval('.bar-segment[data-platform="opencode"]', elements => elements.reduce((sum, element) => sum + Number(element.dataset.tokens), 0));
      assert.equal(actual, total);
      console.log(`PASS ${days}-day dropdown: ${days} buckets and ${total} historical OpenCode tokens`);
    }

    await page.click('[data-range="30D"]');
    await waitForChart(page, 30);
    assert.equal(await page.$eval('#filter-duration-label', element => element.textContent), 'Past 30 Days');
    const rangeRequests = requests.filter(url => url.pathname.startsWith('/api/usage/')).slice(-6);
    assert.equal(new Set(rangeRequests.map(url => url.searchParams.get('start'))).size, 1);
    assert.equal(new Set(rangeRequests.map(url => url.searchParams.get('end'))).size, 1);
    console.log('PASS top-level range control and shared request bounds');

    for (const [label, platform, total] of [['OpenCode', 'opencode', 400], ['Cline CLI', 'cline', 200], ['Claude Code', 'claude_code', 0], ['Codex CLI', 'codex', 0]]) {
      await chooseMenu(page, '#filter-platform-btn', `#filter-platform-menu [data-val="${label}"]`);
      await waitForChart(page, 30, platform);
      await assertCardTrends(page, 30);
      assert.equal(await page.$$eval('.bar-segment', elements => elements.reduce((sum, element) => sum + Number(element.dataset.tokens), 0)), total);
      // The section's platform dropdown filters the card grid, so a chosen platform
      // leaves exactly one card rather than one unhidden row.
      assert.equal(await page.$$eval('.usage-card', cards => cards.length), 1);
      assert.equal(await page.$eval('#usage-card-grid', grid => grid.dataset.focused), 'true');
      const ranking = await page.$$eval('.model-ranking-row', rows => rows.map(row => ({tokens: Number(row.dataset.tokens), requests: Number(row.dataset.requests)})));
      assert.deepEqual(ranking, [{tokens: total, requests: 1}]);
      const modelBeforeClick = await page.$eval(`#usage-model-${platform}`, select => select.value);
      await page.click('.model-ranking-row');
      assert.equal(await page.$eval(`#usage-model-${platform}`, select => select.value), modelBeforeClick);
      if (!total) assert.match(await page.$eval('#chart-caption', element => element.textContent), /No token usage/);
    }
    console.log('PASS individual platforms, historical usage from an unavailable collector, and empty states');

    await chooseMenu(page, '#filter-platform-btn', '#filter-platform-menu [data-val="all"]');
    await waitForChart(page, 30);
    assert.equal(await page.$('.usage-model-ranking'), null);
    await page.click('#toggle-grouped-btn');
    assert.equal(await page.$eval('.bar-column-wrapper', element => element.style.height), '100%');
    await page.click('[data-range="90D"]');
    await waitForChart(page, 90);
    assert.equal(await page.$eval('.bar-column-wrapper', element => element.style.height), '100%');
    await page.click('#toggle-stacked-btn');
    const stacked = await page.$$eval('.bar-column-wrapper', wrappers => wrappers.filter(wrapper => parseFloat(wrapper.style.height) > 0).map(wrapper => Array.from(wrapper.children).reduce((sum, segment) => sum + parseFloat(segment.style.height), 0)));
    assert.ok(stacked.every(value => Math.abs(value - 100) < 0.01));
    console.log('PASS grouped/stacked scales and mode persistence after reload');

    delayedDays = 30;
    const delayedResponse = page.waitForResponse(response => response.url().includes('/api/usage/models') && timeline(new URL(response.url()).searchParams, 'opencode').length === 30);
    await page.click('[data-range="30D"]');
    await page.click('[data-range="7D"]');
    await waitForChart(page, 7);
    await delayedResponse;
    await waitForChart(page, 7);
    console.log('PASS stale responses cannot overwrite the most recent range');

    delayedDays = null;
    failTimeline = true;
    await page.click('[data-range="30D"]');
    await page.waitForSelector('#bar-chart-columns [role="alert"]');
    assert.equal(await page.$eval('#bar-chart-columns', element => element.getAttribute('aria-busy')), 'false');
    assert.equal(await page.$$eval('#platform-cards-container [role="alert"]', alerts => alerts.length), 4);
    failTimeline = false;
    await page.click('[data-range="7D"]');
    await waitForChart(page, 7);
    await page.reload({waitUntil: 'networkidle0'});
    await waitForChart(page, 7);
    await assertCardTrends(page, 7);
    await assertBreakdownTotal(page, 'opencode', 100);
    await assertBreakdownTotal(page, 'cline', 200);
    await chooseMenu(page, '#usage-model-opencode-trigger', '#usage-model-opencode-menu [data-value="opencode-model"]');
    await page.waitForSelector('.usage-card[data-platform="opencode"] .usage-day-row');
    await assertBreakdownTotal(page, 'cline', 200);
    await assertCardTrends(page, 7);
    await waitForChart(page, 7);
    await page.select('#usage-range-filter', '90');
    await waitForChart(page, 90);
    assert.equal(await page.$eval('#usage-model-opencode', element => element.value), 'opencode-model');
    assert.equal(await page.$$eval('.usage-card[data-platform="opencode"] .usage-day-row', rows => rows.length), 90);
    await page.select('#usage-range-filter', '7');
    await waitForChart(page, 7);
    assert.equal(await page.$$eval('.usage-card[data-platform="opencode"] .usage-day-row', rows => rows.length), 7);
    console.log('PASS detailed range changes preserve model selection and reload daily breakdowns');
    await chooseMenu(page, '#usage-model-opencode-trigger', '#usage-model-opencode-menu [data-value=""]');
    await assertBreakdownTotal(page, 'opencode', 100);
    console.log('PASS overview and breakdown renderers remain populated through refresh and model drill-down');
    console.log('PASS four visible live sparklines across ranges, platform selection, errors, and refresh');
    assert.deepEqual(errors, []);
    console.log('PASS visible API errors and recovery; no browser JavaScript errors');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
