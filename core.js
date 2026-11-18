(() => {
  const privatePatterns = [
    /\b\d{3}-\d{2}-\d{4}\b/,
    /\b(?:\d[ -]*?){13,19}\b/,
    /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i,
    /\b(?:password|passcode|secret|api[_ -]?key)\s*[:=]/i,
    /\b(?:my|our)\s+(?:medical|health|bank|account)\s+(?:record|number|details?)\b/i,
  ];

  function inspectPrompt(value) {
    const prompt = String(value || '').trim();
    const hasWarning = privatePatterns.some((pattern) => pattern.test(prompt));
    return {
      prompt,
      hasWarning,
      message: hasWarning
        ? 'This limited local check found a possible personal detail. Remove it before searching.'
        : 'This is a limited warning check, not a safety guarantee. A clean result does not mean your prompt is safe to share.',
    };
  }

  function normalizeResults(payload) {
    return (Array.isArray(payload?.results) ? payload.results : [])
      .filter((item) => item?.thumbnail && (item?.source_url || item?.sourceUrl))
      .map((item, index) => ({
        id: item.id || `result-${index}`,
        title: item.title || 'Untitled image',
        thumbnail: item.thumbnail,
        sourceUrl: item.source_url || item.sourceUrl,
        imageUrl: item.image_url || item.imageUrl || item.thumbnail,
        creator: item.creator || 'Creator not listed',
        license: item.license || 'License not listed',
        licenseVersion: item.license_version || item.licenseVersion || '',
        licenseUrl: item.license_url || item.licenseUrl || '',
        attribution: item.attribution || '',
        width: Number(item.width) || null,
        height: Number(item.height) || null,
      }));
  }

  function attributionText(item) {
    if (item.attribution) return item.attribution;
    const creator = item.creator === 'Creator not listed' ? 'Creator not listed' : `by ${item.creator}`;
    const license = licenseLabel(item);
    return `"${item.title}" ${creator}. ${license}. Source: ${item.sourceUrl}`;
  }

  function readableLicense(value) {
    if (value === 'cc0') return 'CC0';
    if (value === 'pdm') return 'Public Domain Mark';
    if (value.startsWith('cc-')) return `CC ${value.slice(3).replaceAll('-', ' ').toUpperCase()}`;
    return value;
  }

  function licenseLabel(item) {
    const version = item.licenseVersion ? ` ${item.licenseVersion}` : '';
    return `${readableLicense(item.license)}${version}`;
  }

  function createSearchCoordinator() {
    let nextId = 0;
    let currentId = 0;
    let currentQuery = '';
    let currentPromise = null;

    return {
      begin(query, task) {
        if (query === currentQuery && currentPromise) {
          return { id: currentId, promise: currentPromise };
        }
        currentId = ++nextId;
        currentQuery = query;
        const id = currentId;
        currentPromise = Promise.resolve().then(task).finally(() => {
          if (currentId === id) currentPromise = null;
        });
        return { id, promise: currentPromise };
      },
      isCurrent(id) {
        return id === currentId;
      },
      get currentId() {
        return currentId;
      },
    };
  }

  async function searchBackend(query, { fetchImpl, coordinator, backendUrl }) {
    const { id, promise } = coordinator.begin(query, async () => {
      const response = await fetchImpl(`${backendUrl.replace(/\/+$/, '')}/api/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      if (!response.ok) throw new Error(`EcoLens API returned ${response.status}`);
      return response.json();
    });

    try {
      const payload = await promise;
      if (!coordinator.isCurrent(id)) return { kind: 'stale', results: [] };
      const results = normalizeResults(payload);
      return results.length ? { kind: 'results', results } : { kind: 'empty', results: [] };
    } catch (error) {
      if (!coordinator.isCurrent(id)) return { kind: 'stale', results: [] };
      return { kind: 'error', message: error.message, results: [] };
    }
  }

  const api = { attributionText, createSearchCoordinator, inspectPrompt, licenseLabel, normalizeResults, searchBackend };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else globalThis.EcoLensCore = api;
})();
