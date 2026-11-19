const $ = (id) => document.getElementById(id);
const promptBox = $('prompt');
const searchButton = $('search');
const resultsContainer = $('results');
const comparison = $('comparison');
const BACKEND_URL = 'https://ecolens-8mvu.onrender.com';
const coordinator = EcoLensCore.createSearchCoordinator();
let displayedResults = [];
let selectedIds = new Set();

function updatePrivacy() {
  const result = EcoLensCore.inspectPrompt(promptBox.value);
  $('privacy').textContent = result.message;
  $('privacy').classList.toggle('warning', result.hasWarning);
  searchButton.disabled = !result.prompt || result.hasWarning;
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
  if (!inspection.prompt || inspection.hasWarning) return;
  searchButton.disabled = true;
  setStatus('Searching Openverse…', 'loading');
  const outcome = await EcoLensCore.searchBackend(inspection.prompt, {
    fetchImpl: fetch,
    coordinator,
    backendUrl: BACKEND_URL,
  });
  if (outcome.kind === 'stale') return;
  if (outcome.kind === 'error') {
    renderResults([]);
    setStatus(`Search failed: ${outcome.message}. Try again.`, 'error');
  } else if (outcome.kind === 'empty') {
    renderResults([]);
    setStatus('No results found. Try a different description.', 'empty');
  } else {
    renderResults(outcome.results);
    setStatus(`${outcome.results.length} results. Review source and license details before reuse.`);
  }
  updatePrivacy();
}

promptBox.addEventListener('input', updatePrivacy);
searchButton.addEventListener('click', runSearch);
updatePrivacy();
