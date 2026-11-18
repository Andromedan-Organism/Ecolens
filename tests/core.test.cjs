const test = require('node:test');
const assert = require('node:assert/strict');
const {
  attributionText,
  createSearchCoordinator,
  inspectPrompt,
  licenseLabel,
  normalizeResults,
  searchBackend,
} = require('../core.js');

const sample = {
  id: 'image-1',
  title: 'Blue flower',
  thumbnail: 'https://example.test/thumb.jpg',
  image_url: 'https://example.test/image.jpg',
  source_url: 'https://example.test/source',
  creator: 'A. Artist',
  license: 'cc-by',
  license_version: '4.0',
  license_url: 'https://creativecommons.org/licenses/by/4.0/',
  attribution: 'Blue flower by A. Artist, CC BY 4.0',
  width: 1200,
  height: 800,
};

test('privacy warning catches known patterns and clearly limits its claim', () => {
  const flagged = inspectPrompt('Use contact me at sam@example.com');
  assert.equal(flagged.hasWarning, true);
  assert.match(flagged.message, /limited local check/i);

  const clean = inspectPrompt('A yellow flower in a glass vase');
  assert.equal(clean.hasWarning, false);
  assert.match(clean.message, /not a safety guarantee/i);
  assert.match(clean.message, /does not mean.*safe to share/i);
});

test('empty search result is reported as empty', async () => {
  const result = await searchBackend('flower', {
    coordinator: createSearchCoordinator(),
    backendUrl: 'https://api.example.test',
    fetchImpl: async () => ({ ok: true, json: async () => ({ results: [] }) }),
  });
  assert.deepEqual(result, { kind: 'empty', results: [] });
});

test('API errors are surfaced as errors', async () => {
  const result = await searchBackend('flower', {
    coordinator: createSearchCoordinator(),
    backendUrl: 'https://api.example.test',
    fetchImpl: async () => ({ ok: false, status: 429 }),
  });
  assert.equal(result.kind, 'error');
  assert.match(result.message, /429/);
});

test('normalized result preserves direct license details and attribution', () => {
  const [result] = normalizeResults({ results: [sample] });
  assert.equal(result.license, 'cc-by');
  assert.equal(result.licenseVersion, '4.0');
  assert.equal(result.licenseUrl, sample.license_url);
  assert.equal(result.sourceUrl, sample.source_url);
  assert.equal(attributionText(result), sample.attribution);
  assert.equal(licenseLabel(result), 'CC BY 4.0');
});

test('search sends the prompt to the configured EcoLens backend', async () => {
  let request;
  const result = await searchBackend('blue flower', {
    coordinator: createSearchCoordinator(),
    backendUrl: 'https://api.example.test/',
    fetchImpl: async (url, options) => {
      request = { url, options };
      return { ok: true, json: async () => ({ results: [sample] }) };
    },
  });

  assert.equal(request.url, 'https://api.example.test/api/search');
  assert.equal(request.options.method, 'POST');
  assert.deepEqual(JSON.parse(request.options.body), { query: 'blue flower' });
  assert.equal(result.kind, 'results');
});

test('duplicate in-flight queries coalesce and newer queries supersede older results', async () => {
  const coordinator = createSearchCoordinator();
  let finish;
  let calls = 0;
  const task = () => {
    calls += 1;
    return new Promise((resolve) => { finish = resolve; });
  };

  const first = coordinator.begin('flower', task);
  const duplicate = coordinator.begin('flower', task);
  assert.equal(first.id, duplicate.id);
  assert.equal(first.promise, duplicate.promise);
  await Promise.resolve();
  assert.equal(calls, 1);

  const newer = coordinator.begin('tree', async () => ({ results: [] }));
  assert.equal(coordinator.isCurrent(first.id), false);
  assert.equal(coordinator.isCurrent(newer.id), true);
  finish({ results: [] });
  await first.promise;
});

test('overlapping API searches ignore a stale response', async () => {
  const coordinator = createSearchCoordinator();
  const pending = new Map();
  const fetchImpl = (_requestUrl, options) => {
    const query = JSON.parse(options.body).query;
    return new Promise((resolve) => pending.set(query, resolve));
  };
  const common = { coordinator, fetchImpl, backendUrl: 'https://api.example.test' };
  const oldSearch = searchBackend('older prompt', common);
  await Promise.resolve();
  const latestSearch = searchBackend('latest prompt', common);
  await Promise.resolve();

  pending.get('latest prompt')({ ok: true, json: async () => ({ results: [sample] }) });
  assert.equal((await latestSearch).kind, 'results');
  pending.get('older prompt')({ ok: true, json: async () => ({ results: [sample] }) });
  assert.equal((await oldSearch).kind, 'stale');
});
