const DATA_URL = 'https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/data/news.json';
const CACHE_KEY = 'kirapara-news-cache-v1';
const THEME_KEY = 'kirapara-news-theme';

const state = {
  items: [],
  region: 'ALL',
  query: '',
  installPrompt: null,
};

const els = {
  grid: document.querySelector('#newsGrid'),
  template: document.querySelector('#newsCardTemplate'),
  tabs: document.querySelector('#regionTabs'),
  search: document.querySelector('#searchInput'),
  clearSearch: document.querySelector('#clearSearchButton'),
  refresh: document.querySelector('#refreshButton'),
  retry: document.querySelector('#retryButton'),
  theme: document.querySelector('#themeButton'),
  install: document.querySelector('#installButton'),
  status: document.querySelector('#statusText'),
  visibleCount: document.querySelector('#visibleCount'),
  empty: document.querySelector('#emptyState'),
  error: document.querySelector('#errorState'),
  errorMessage: document.querySelector('#errorMessage'),
};

const regionNames = {
  JAPAN: '🇯🇵 日本',
  CHINA: '🇨🇳 中国',
  KOREA: '🇰🇷 韓国',
  GLOBAL: '🌐 Global',
};

function normalizeText(value) {
  return String(value ?? '').toLocaleLowerCase('ja');
}

function formatDate(epoch, fallback) {
  const seconds = Number(epoch);
  if (!Number.isFinite(seconds) || seconds <= 0) return fallback || '';
  try {
    return new Intl.DateTimeFormat('ja-JP', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(seconds * 1000));
  } catch {
    return fallback || '';
  }
}

function filteredItems() {
  const q = normalizeText(state.query).trim();
  return state.items.filter((item) => {
    if (state.region !== 'ALL' && item.region !== state.region) return false;
    if (!q) return true;
    const haystack = normalizeText(`${item.title}\n${item.body}\n${item.platform}\n${item.region}`);
    return haystack.includes(q);
  });
}

function updateCounts() {
  const regions = ['ALL', 'JAPAN', 'CHINA', 'KOREA', 'GLOBAL'];
  for (const region of regions) {
    const count = region === 'ALL'
      ? state.items.length
      : state.items.filter((item) => item.region === region).length;
    const target = document.querySelector(`[data-count="${region}"]`);
    if (target) target.textContent = String(count);
  }
}

function createCard(item) {
  const fragment = els.template.content.cloneNode(true);
  const article = fragment.querySelector('.news-card');
  const imageLink = fragment.querySelector('.card-image-link');
  const imageWrap = fragment.querySelector('.card-image-wrap');
  const image = fragment.querySelector('.card-image');
  const badge = fragment.querySelector('.region-badge');
  const platform = fragment.querySelector('.platform');
  const published = fragment.querySelector('.published');
  const title = fragment.querySelector('.card-title');
  const body = fragment.querySelector('.card-body');
  const more = fragment.querySelector('.more-button');
  const source = fragment.querySelector('.source-button');

  const sourceUrl = item.sourceUrl || '#';
  imageLink.href = sourceUrl;
  source.href = sourceUrl;
  badge.textContent = regionNames[item.region] || item.region || 'NEWS';
  platform.textContent = item.platform || '公式';
  published.textContent = formatDate(item.publishedAtEpoch, item.publishedLabel);
  published.dateTime = item.publishedAtEpoch
    ? new Date(Number(item.publishedAtEpoch) * 1000).toISOString()
    : '';
  title.textContent = item.title || 'タイトルなし';
  body.textContent = item.body || item.title || '';

  if (item.imageUrl) {
    image.src = item.imageUrl;
    image.alt = item.title ? `${item.title} の画像` : 'ニュース画像';
    image.addEventListener('error', () => imageWrap.classList.add('is-fallback'), { once: true });
  } else {
    imageWrap.classList.add('is-fallback');
  }

  const canExpand = (item.body || '').length > 150;
  if (!canExpand) {
    more.hidden = true;
  } else {
    more.addEventListener('click', () => {
      const expanded = article.classList.toggle('is-expanded');
      more.textContent = expanded ? '閉じる' : '続きを読む';
    });
  }

  return fragment;
}

function render() {
  const items = filteredItems();
  els.grid.replaceChildren();

  const fragment = document.createDocumentFragment();
  for (const item of items) fragment.appendChild(createCard(item));
  els.grid.appendChild(fragment);
  els.grid.setAttribute('aria-busy', 'false');

  els.visibleCount.textContent = `${items.length}件`;
  els.empty.hidden = items.length !== 0 || state.items.length === 0;
  els.error.hidden = true;
  updateCounts();
}

function renderSkeletons() {
  els.grid.replaceChildren();
  els.grid.setAttribute('aria-busy', 'true');
  const fragment = document.createDocumentFragment();
  for (let i = 0; i < 4; i += 1) {
    const skeleton = document.createElement('div');
    skeleton.className = 'skeleton';
    skeleton.setAttribute('aria-hidden', 'true');
    fragment.appendChild(skeleton);
  }
  els.grid.appendChild(fragment);
}

function latestUpdateLabel(items) {
  const latest = items.reduce((max, item) => Math.max(max, Number(item.publishedAtEpoch) || 0), 0);
  if (!latest) return `${items.length}件のニュース`;
  const label = new Intl.DateTimeFormat('ja-JP', {
    month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'
  }).format(new Date(latest * 1000));
  return `${items.length}件 · 最新 ${label}`;
}

async function loadNews({ force = false } = {}) {
  document.body.classList.toggle('refreshing', force);
  els.error.hidden = true;
  if (!state.items.length) renderSkeletons();

  try {
    const url = force ? `${DATA_URL}?t=${Date.now()}` : DATA_URL;
    const response = await fetch(url, { cache: force ? 'no-store' : 'default' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const json = await response.json();
    if (!Array.isArray(json)) throw new Error('ニュースデータの形式が不正です');

    state.items = json
      .filter((item) => item && typeof item === 'object')
      .sort((a, b) => (Number(b.publishedAtEpoch) || 0) - (Number(a.publishedAtEpoch) || 0));

    localStorage.setItem(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), items: state.items }));
    els.status.textContent = latestUpdateLabel(state.items);
    render();
  } catch (error) {
    const cached = loadCachedNews();
    if (cached.length) {
      state.items = cached;
      els.status.textContent = `${cached.length}件 · オフラインキャッシュ`;
      render();
    } else {
      state.items = [];
      els.grid.replaceChildren();
      els.grid.setAttribute('aria-busy', 'false');
      els.error.hidden = false;
      els.empty.hidden = true;
      els.visibleCount.textContent = '0件';
      els.errorMessage.textContent = `ニュースを取得できませんでした (${error.message})`;
      els.status.textContent = '読み込み失敗';
    }
  } finally {
    document.body.classList.remove('refreshing');
  }
}

function loadCachedNews() {
  try {
    const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
    return Array.isArray(cached?.items) ? cached.items : [];
  } catch {
    return [];
  }
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
  els.theme.textContent = theme === 'light' ? '☀' : '☾';
  document.querySelector('meta[name="theme-color"]')?.setAttribute(
    'content',
    theme === 'light' ? '#f5f4f8' : '#101116'
  );
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  const preferred = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  setTheme(saved === 'light' || saved === 'dark' ? saved : preferred);
}

els.tabs.addEventListener('click', (event) => {
  const button = event.target.closest('[data-region]');
  if (!button) return;
  state.region = button.dataset.region;
  for (const tab of els.tabs.querySelectorAll('.region-tab')) {
    tab.classList.toggle('is-active', tab === button);
  }
  render();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

els.search.addEventListener('input', () => {
  state.query = els.search.value;
  els.clearSearch.hidden = !state.query;
  render();
});

els.clearSearch.addEventListener('click', () => {
  els.search.value = '';
  state.query = '';
  els.clearSearch.hidden = true;
  els.search.focus();
  render();
});

els.refresh.addEventListener('click', () => loadNews({ force: true }));
els.retry.addEventListener('click', () => loadNews({ force: true }));
els.theme.addEventListener('click', () => {
  setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light');
});

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault();
  state.installPrompt = event;
  els.install.hidden = false;
});

els.install.addEventListener('click', async () => {
  if (!state.installPrompt) return;
  state.installPrompt.prompt();
  await state.installPrompt.userChoice;
  state.installPrompt = null;
  els.install.hidden = true;
});

window.addEventListener('appinstalled', () => {
  state.installPrompt = null;
  els.install.hidden = true;
});

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  });
}

initTheme();
loadNews();
