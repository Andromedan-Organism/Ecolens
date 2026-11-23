const $ = (id) => document.getElementById(id);
const promptBox = $('prompt');
const searchButton = $('search');
const resultsContainer = $('results');
const comparison = $('comparison');
const BACKEND_URL = 'https://ecolens-8mvu.onrender.com';
const coordinator = EcoLensCore.createSearchCoordinator();
const sourceInputs = [...document.querySelectorAll('input[name="source"]')];
const availableSources = sourceInputs.map((input) => input.value);
const sourcePreferenceKey = 'preferredSources';
const impactStatsKey = 'impactStats';
let selectedSources = [...availableSources];
let sourcePreferencesReady = false;
let confirmedReuses = 0;
let impactSaveQueue = Promise.resolve();
let displayedResults = [];
let selectedIds = new Set();

function updateImpactSummary() {
  const estimate = EcoLensCore.estimateAvoidedImpact(confirmedReuses);
  $('reuse-count').textContent = String(estimate.confirmedReuses);
  $('energy-estimate').textContent = `${estimate.energyWh.toFixed(1)} Wh`;
  $('carbon-estimate').textContent = `${estimate.co2eGrams.toFixed(1)} g`;
}

function updatePrivacy() {
  const result = EcoLensCore.inspectPrompt(promptBox.value);
  $('privacy').textContent = result.message;
  $('privacy').classList.toggle('warning', result.hasWarning);
  searchButton.disabled = !sourcePreferencesReady || !result.prompt || result.hasWarning;
}

function setStatus(message, state = '') {
  const status = $('status');
  status.textContent = message;
  status.dataset.state = state;
}

function renderResults(results) {
  displayedResults = results;
  selectedIds = new Set();
  resultsContainer.replaceChildren();
  comparison.replaceChildren();
  comparison.classList.add('hidden');
  for (const item of results) resultsContainer.append(makeCard(item));
  updateCompareButton();
}

async function loadSourcePreferences() {
  try {
    const stored = await chrome.storage.local.get([sourcePreferenceKey, impactStatsKey]);
    if (Array.isArray(stored[sourcePreferenceKey])) {
      const validSources = stored[sourcePreferenceKey].filter((source) => availableSources.includes(source));
      if (validSources.length) selectedSources = [...new Set(validSources)];
    }
    const storedCount = stored[impactStatsKey]?.confirmedReuses;
    confirmedReuses = Number.isSafeInteger(storedCount) && storedCount > 0 ? storedCount : 0;
    sourceInputs.forEach((input) => {
      input.checked = selectedSources.includes(input.value);
    });
    updateImpactSummary();
    sourcePreferencesReady = true;
    updatePrivacy();
  } catch {
    setStatus('Could not load source preferences. Reload EcoLens and try again.', 'error');
  }
}

async function recordReuse(button) {
  button.disabled = true;
  const save = impactSaveQueue.catch(() => {}).then(async () => {
    const nextCount = confirmedReuses + 1;
    await chrome.storage.local.set({
      [impactStatsKey]: {
        confirmedReuses: nextCount,
        updatedAt: new Date().toISOString(),
      },
    });
    confirmedReuses = nextCount;
    updateImpactSummary();
    return nextCount;
  });
  impactSaveQueue = save;

  try {
    const count = await save;
    button.textContent = 'Reuse counted';
    button.classList.add('reuse-button--counted');
    setStatus(`Reuse recorded locally. Your total is now ${count}.`, 'success');
  } catch {
    button.disabled = false;
    setStatus('Could not save this reuse on your device, so it was not counted.', 'error');
  }
}

async function saveSourcePreferences() {
  const nextSources = sourceInputs.filter((input) => input.checked).map((input) => input.value);
  if (!nextSources.length) {
    sourceInputs.find((input) => input.value === selectedSources[0]).checked = true;
    setStatus('Choose at least one search source.');
    return;
  }

  selectedSources = nextSources;
  updatePrivacy();
  try {
    await chrome.storage.local.set({ [sourcePreferenceKey]: selectedSources });
  } catch {
    setStatus('Could not save source preferences. Your choice may not persist.', 'error');
  }
}

function makeCard(item) {
  const card = document.createElement('article');
  card.className = 'card';

  const image = document.createElement('img');
  image.loading = 'lazy';
  image.src = item.thumbnail;
  image.alt = item.title;
  card.append(image);

  const details = document.createElement('div');
  details.className = 'meta';

  const title = document.createElement('h2');
  title.textContent = item.title;
  details.append(title);

  const sourceLabel = document.createElement('p');
  sourceLabel.className = 'source-label';
  sourceLabel.textContent = item.source;
  details.append(sourceLabel);

  const creator = document.createElement('p');
  creator.className = 'creator';
  creator.textContent = item.creator;
  details.append(creator);

  const license = document.createElement('a');
  license.className = 'license-link';
  license.textContent = `${EcoLensCore.licenseLabel(item)} — view terms`;
  if (item.licenseUrl) {
    license.href = item.licenseUrl;
    license.target = '_blank';
    license.rel = 'noopener noreferrer';
    details.append(license);
  } else {
    const missingLicenseUrl = document.createElement('p');
    missingLicenseUrl.className = 'license-missing';
    missingLicenseUrl.textContent = `${license.textContent}. License link not supplied; review the source before reuse.`;
    details.append(missingLicenseUrl);
  }

  const source = document.createElement('a');
  source.className = 'source-link';
  source.href = item.sourceUrl;
  source.target = '_blank';
  source.rel = 'noopener noreferrer';
  source.textContent = 'Open original source';
  details.append(source);

  const actions = document.createElement('div');
  actions.className = 'card-actions';
  const reuse = document.createElement('button');
  reuse.type = 'button';
  reuse.className = 'reuse-button';
  reuse.textContent = 'I reused this instead';
  reuse.setAttribute('aria-label', `Count ${item.title} as reused instead of generating`);
  reuse.addEventListener('click', () => recordReuse(reuse));
  actions.append(reuse);

  const copy = document.createElement('button');
  copy.type = 'button';
  copy.className = 'copy';
  copy.textContent = 'Copy attribution';
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(EcoLensCore.attributionText(item));
      setStatus('Attribution copied. Check whether your use requires it.');
    } catch {
      setStatus('Could not access the clipboard. Open the source for attribution details.', 'error');
    }
  });
  actions.append(copy);

  const selectLabel = document.createElement('label');
  selectLabel.className = 'select-result';
  const select = document.createElement('input');
  select.type = 'checkbox';
  select.value = item.id;
  select.checked = selectedIds.has(item.id);
  select.addEventListener('change', () => {
    if (select.checked && selectedIds.size >= 2) {
      select.checked = false;
      setStatus('Choose up to two images to compare.');
      return;
    }
    if (select.checked) selectedIds.add(item.id);
    else selectedIds.delete(item.id);
    updateCompareButton();
  });
  selectLabel.append(select, document.createTextNode('Compare'));
  actions.append(selectLabel);
  details.append(actions);

  card.append(details);
  return card;
}

function updateCompareButton() {
  let button = $('compare-selected');
  if (!button) {
    button = document.createElement('button');
    button.id = 'compare-selected';
    button.type = 'button';
    button.className = 'compare-button';
    button.textContent = 'Compare selected images';
    button.addEventListener('click', compareSelected);
    resultsContainer.before(button);
  }
  button.hidden = selectedIds.size !== 2;
}

function compareSelected() {
  const chosen = displayedResults.filter((item) => selectedIds.has(item.id));
  if (chosen.length !== 2) return;
  comparison.replaceChildren();
  comparison.classList.remove('hidden');
  const heading = document.createElement('h2');
  heading.textContent = 'Compare image options';
  comparison.append(heading);

  const grid = document.createElement('div');
  grid.className = 'compare-grid';
  for (const item of chosen) {
    const option = document.createElement('article');
    option.className = 'compare-option';
    const image = document.createElement('img');
    image.src = item.thumbnail;
    image.alt = item.title;
    option.append(image);
    const title = document.createElement('h3');
    title.textContent = item.title;
    option.append(title);
    const source = document.createElement('p');
    source.textContent = `Source: ${item.source}`;
    option.append(source);
    const dimensions = document.createElement('p');
    dimensions.textContent = item.width && item.height ? `${item.width} × ${item.height}px` : 'Dimensions not provided';
    option.append(dimensions);
    const license = document.createElement('p');
    license.textContent = `License: ${EcoLensCore.licenseLabel(item)}`;
    option.append(license);
    const terms = document.createElement('a');
    if (item.licenseUrl) {
      terms.href = item.licenseUrl;
      terms.target = '_blank';
      terms.rel = 'noopener noreferrer';
      terms.textContent = 'Review license terms';
      option.append(terms);
    } else {
      const missingTerms = document.createElement('p');
      missingTerms.textContent = 'License link not supplied. Review the source before reuse.';
      option.append(missingTerms);
    }
    const attribution = document.createElement('button');
    attribution.type = 'button';
    attribution.textContent = 'Copy attribution';
    attribution.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(EcoLensCore.attributionText(item));
        setStatus('Attribution copied. Check whether your use requires it.');
      } catch {
        setStatus('Could not access the clipboard. Open the source for attribution details.', 'error');
      }
    });
    option.append(attribution);
    grid.append(option);
  }
  comparison.append(grid);
}

async function runSearch() {
  const inspection = EcoLensCore.inspectPrompt(promptBox.value);
  if (!sourcePreferencesReady || !inspection.prompt || inspection.hasWarning) return;
  searchButton.disabled = true;
  const sourceLabels = selectedSources.map((source) => (
    source === 'wikimedia' ? 'Wikimedia Commons' : 'Openverse'
  ));
  setStatus(`Searching ${sourceLabels.join(' and ')}…`, 'loading');
  const outcome = await EcoLensCore.searchBackend(inspection.prompt, {
    fetchImpl: fetch,
    coordinator,
    backendUrl: BACKEND_URL,
    sources: selectedSources,
  });
  if (outcome.kind === 'stale') return;
  if (outcome.kind === 'error') {
    renderResults([]);
    setStatus(`Search failed: ${outcome.message}. Try again.`, 'error');
  } else if (outcome.kind === 'empty') {
    renderResults([]);
    setStatus(`No results found. Try a different description. ${outcome.warnings.join(' ')}`, 'empty');
  } else {
    renderResults(outcome.results);
    const warning = outcome.warnings.length ? ` ${outcome.warnings.join(' ')}` : '';
    setStatus(`${outcome.results.length} results. Review source and license details before reuse.${warning}`, outcome.warnings.length ? 'warning' : '');
  }
  updatePrivacy();
}

promptBox.addEventListener('input', updatePrivacy);
searchButton.addEventListener('click', runSearch);
sourceInputs.forEach((input) => input.addEventListener('change', saveSourcePreferences));
updatePrivacy();
loadSourcePreferences();
