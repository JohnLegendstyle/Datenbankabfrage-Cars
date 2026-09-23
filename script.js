const search = document.getElementById('search');
const media = document.getElementById('media');
const sort = document.getElementById('sort');
const cards = document.getElementById('cards');
const status = document.getElementById('status');
const template = document.getElementById('card-template');
const error = document.getElementById('error');
const empty = document.getElementById('empty');
const pagination = document.getElementById('pagination');
const previous = document.getElementById('previous');
const next = document.getElementById('next');
let page = 1;
let pages = 0;
let timer;
let controller;
let requestNumber = 0;
let metadataLoaded = false;

const initial = new URLSearchParams(location.search);
search.value = (initial.get('q') || '').slice(0, 120);
if (['featured', 'name', 'name-desc'].includes(initial.get('sort'))) {
  sort.value = initial.get('sort');
}
const initialPage = Number(initial.get('page'));
if (Number.isInteger(initialPage) && initialPage > 0 && initialPage <= 100000) page = initialPage;

function safeUrl(value, hosts) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && hosts.includes(url.hostname) ? url.href : null;
  } catch {
    return null;
  }
}

function render(items) {
  const fragment = document.createDocumentFragment();
  for (const character of items) {
    const card = template.content.cloneNode(true);
    const image = card.querySelector('.character-image');
    const fallback = card.querySelector('.image-fallback');
    const imageUrl = safeUrl(character.image, ['lumiere-a.akamaihd.net', 'static.wikia.nocookie.net', 'images.squarespace-cdn.com']);
    if (imageUrl) {
      image.alt = character.name;
      image.hidden = false;
      fallback.hidden = true;
      image.addEventListener('error', () => {
        image.hidden = true;
        fallback.hidden = false;
        fallback.textContent = 'Bild momentan nicht verfügbar';
      }, { once: true });
      image.src = imageUrl;
    }
    card.querySelector('h3').textContent = character.name;
    card.querySelector('.badge').textContent = character.type;
    card.querySelector('.description').textContent = character.description;
    if (character.aliases.length) {
      const aliases = card.querySelector('.aliases');
      aliases.hidden = false;
      aliases.textContent = 'Auch bekannt als: ' + character.aliases.join(' · ');
    }
    if (character.model) {
      const model = card.querySelector('.model');
      model.hidden = false;
      model.textContent = character.model;
    }
    for (const appearance of character.media) {
      const item = document.createElement('li');
      item.textContent = appearance.title;
      card.querySelector('.appearances').appendChild(item);
    }
    const link = card.querySelector('.source-link');
    const source = safeUrl(character.source_url, ['pixarcars.fandom.com', 'cars.disney.com']);
    if (source) link.href = source;
    else link.hidden = true;
    fragment.appendChild(card);
  }
  cards.replaceChildren(fragment);
}

async function loadMetadata(signal) {
  if (metadataLoaded) return;
  const response = await fetch('/api/media', { signal });
  if (!response.ok) throw new Error('Das Figurenverzeichnis ist momentan nicht erreichbar.');
  const data = await response.json();
  media.replaceChildren(new Option('Alle Filme & Serien', ''));
  for (const item of data.media) {
    media.appendChild(new Option(`${item.title} (${item.count})`, item.id));
  }
  const wanted = initial.get('media');
  if (data.media.some(item => item.id === wanted)) media.value = wanted;
  document.getElementById('updated').textContent = new Date(data.updated + 'T12:00:00').toLocaleDateString('de-DE');
  document.getElementById('scope').textContent = data.scope;
  metadataLoaded = true;
}

function setBusy(busy) {
  cards.setAttribute('aria-busy', String(busy));
  previous.disabled = busy || page <= 1;
  next.disabled = busy || page >= pages;
}

async function loadCharacters() {
  clearTimeout(timer);
  controller?.abort();
  controller = new AbortController();
  const signal = controller.signal;
  const current = ++requestNumber;
  setBusy(true);
  error.hidden = true;
  empty.hidden = true;
  status.textContent = 'Suche läuft …';
  try {
    if (location.protocol === 'file:') {
      throw new Error('Bitte öffne die Website über den gestarteten Server unter http://localhost:8000.');
    }
    await loadMetadata(signal);
    const params = new URLSearchParams({ q: search.value.trim(), media: media.value, sort: sort.value, page: String(page) });
    const response = await fetch('/api/characters?' + params, { signal });
    if (!response.ok) throw new Error('Die Suche ist momentan nicht erreichbar. Bitte versuche es erneut.');
    const data = await response.json();
    if (current !== requestNumber) return;
    pages = data.pages;
    if (data.total > 0 && page > pages) {
      page = pages;
      await loadCharacters();
      return;
    }
    render(data.items);
    const total = data.total.toLocaleString('de-DE');
    status.textContent = `${total} ${data.total === 1 ? 'Charakter' : 'Charaktere'} gefunden`;
    document.getElementById('catalog-count').textContent = `${data.catalog_total.toLocaleString('de-DE')} Figuren im Katalog`;
    empty.hidden = data.total !== 0;
    pagination.hidden = pages <= 1;
    document.getElementById('page-label').textContent = `Seite ${page} von ${pages}`;
    history.replaceState(null, '', '?' + params);
  } catch (failure) {
    if (failure.name === 'AbortError' || current !== requestNumber) return;
    cards.replaceChildren();
    pagination.hidden = true;
    status.textContent = 'Die Suche konnte nicht geladen werden.';
    document.getElementById('error-message').textContent = failure.message;
    error.hidden = false;
  } finally {
    if (current === requestNumber) setBusy(false);
  }
}

function changeFilters(delayed = false) {
  page = 1;
  controller?.abort();
  ++requestNumber;
  clearTimeout(timer);
  setBusy(true);
  if (delayed) timer = setTimeout(loadCharacters, 250);
  else loadCharacters();
}

search.addEventListener('input', () => changeFilters(true));
media.addEventListener('change', () => changeFilters());
sort.addEventListener('change', () => changeFilters());
document.getElementById('search-form').addEventListener('submit', event => {
  event.preventDefault();
  changeFilters();
});
document.getElementById('retry').addEventListener('click', loadCharacters);
document.getElementById('reset').addEventListener('click', () => {
  search.value = '';
  media.value = '';
  changeFilters();
  search.focus();
});
previous.addEventListener('click', () => { if (page > 1) { page--; loadCharacters(); } });
next.addEventListener('click', () => { if (page < pages) { page++; loadCharacters(); } });
loadCharacters();
