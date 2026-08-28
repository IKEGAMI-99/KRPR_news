const IS_LOCAL_PREVIEW = ['localhost', '127.0.0.1'].includes(location.hostname);
const DATA_URL = IS_LOCAL_PREVIEW
  ? '../data/news.json'
  : 'https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/data/news.json';
const CACHE_KEY = 'kirapara-news-cache-v4';
const THEME_KEY = 'kirapara-news-theme';
const MIN_IMAGE_SHORT_SIDE = 260;
const MIN_IMAGE_AREA = 150000;

const state = {
  items: [],
  region: 'ALL',
  installPrompt: null,
};

const els = {
  grid: document.querySelector('#newsGrid'),
  template: document.querySelector('#newsCardTemplate'),
  tabs: document.querySelector('#regionTabs'),
  refresh: document.querySelector('#refreshButton'),
  retry: document.querySelector('#retryButton'),
  theme: document.querySelector('#themeButton'),
  install: document.querySelector('#installButton'),
  status: document.querySelector('#statusText'),
  empty: document.querySelector('#emptyState'),
  emptyMessage: document.querySelector('#emptyMessage'),
  error: document.querySelector('#errorState'),
  errorMessage: document.querySelector('#errorMessage'),
};

const regionNames = {
  JAPAN: '🇯🇵 日本',
  CHINA: '🇨🇳 中国',
  KOREA: '🇰🇷 韓国',
  GLOBAL: '🌐 Global',
};

const BAD_IMAGE_TOKENS = [
  'favicon', 'apple-touch-icon', 'siteicon', 'site-icon', 'logo', 'brandmark', 'avatar', 'profile', 'author',
  'qrcode', 'qr-code', 'qr_code', '/qr/', '_qr.', 'sprite', 'emoji', 'emoticon', 'badge', 'button', 'loading',
  'spinner', 'placeholder', 'noimage', 'no-image', 'blank.', 'spacer.', 'pixel.', 'tracking', 'googleplay',
  'google-play', 'appstore', 'app-store', '/icon/', '/icons/', 'icon_',
];

const dayParts = new Intl.DateTimeFormat('ja-JP', {
  timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit',
});
const dayLabel = new Intl.DateTimeFormat('ja-JP', {
  timeZone: 'Asia/Tokyo', year: 'numeric', month: 'long', day: 'numeric', weekday: 'short',
});

let viewerImages = [];
let viewerIndex = 0;
let viewerOpener = null;

function storageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function storageSet(key, value) {
  try { localStorage.setItem(key, value); return true; } catch { return false; }
}

function filteredItems() {
  return state.items.filter((item) => state.region === 'ALL' || item.region === state.region);
}

function safeHttpUrl(value) {
  try {
    const url = new URL(String(value || ''), location.href);
    return /^https?:$/.test(url.protocol) ? url.href : '';
  } catch { return ''; }
}

function looksLikeBadImage(url) {
  const value = String(url || '').toLowerCase();
  if (!/^https?:\/\//.test(value) || /\.(svg|ico)(?:\?|$)/.test(value)) return true;
  return BAD_IMAGE_TOKENS.some((token) => value.includes(token));
}

function isSinaImage(url) {
  try { return /(^|\.)sinaimg\.(?:cn|com)$/.test(new URL(url).hostname.toLowerCase()); }
  catch { return false; }
}

function upgradeXImage(url) {
  try {
    const parsed = new URL(url);
    if (parsed.hostname === 'pbs.twimg.com' && /^\/(media|tweet_video_thumb|ext_tw_video_thumb)\//.test(parsed.pathname)) {
      parsed.searchParams.set('name', 'orig');
    }
    return parsed.href;
  } catch { return String(url || ''); }
}

function weiboVariants(url) {
  if (!isSinaImage(url)) return [url];
  try {
    const parsed = new URL(url);
    const match = parsed.hostname.match(/(?:tvax|tva|wx|ww)(\d+)/i);
    const shard = match?.[1] || '1';
    const filename = parsed.pathname.split('/').filter(Boolean).pop();
    if (!filename) return [parsed.href];
    return [...new Set([
      `https://wx${shard}.sinaimg.cn/large/${filename}`,
      `https://ww${shard}.sinaimg.cn/large/${filename}`,
      `https://wx${shard}.sinaimg.cn/mw2000/${filename}`,
      parsed.href.replace(/^http:/i, 'https:'),
    ])];
  } catch { return [url]; }
}

function imageList(item) {
  const values = [
    ...(Array.isArray(item.imageUrls) ? item.imageUrls : []),
    ...(item.imageUrl ? [item.imageUrl] : []),
  ];
  const seen = new Set();
  return values.map(upgradeXImage).filter((url) => {
    if (!url || looksLikeBadImage(url) || seen.has(url)) return false;
    seen.add(url);
    return true;
  });
}

function imageCandidates(urls) {
  const seen = new Set();
  return urls.flatMap((url) => weiboVariants(upgradeXImage(url))).filter((url) => {
    if (!url || seen.has(url)) return false;
    seen.add(url);
    return true;
  });
}

function largeEnough(image) {
  return Boolean(image?.naturalWidth && image?.naturalHeight &&
    Math.min(image.naturalWidth, image.naturalHeight) >= MIN_IMAGE_SHORT_SIDE &&
    image.naturalWidth * image.naturalHeight >= MIN_IMAGE_AREA);
}

function setImageWithFallback(image, wrap, urls, { onValid, onExhausted } = {}) {
  const candidates = imageCandidates(urls);
  let index = 0;
  const fail = () => {
    if (index < candidates.length) {
      image.src = candidates[index++];
      return;
    }
    image.removeAttribute('src');
    wrap?.classList.add('is-fallback');
    onExhausted?.();
  };
  image.referrerPolicy = 'no-referrer';
  image.addEventListener('error', fail);
  image.addEventListener('load', () => {
    if (!largeEnough(image)) { fail(); return; }
    wrap?.classList.remove('is-fallback');
    onValid?.(image);
  });
  fail();
}

function formatDate(epoch, fallback) {
  const seconds = Number(epoch);
  if (!Number.isFinite(seconds) || seconds <= 0) return fallback || '';
  try {
    return new Intl.DateTimeFormat('ja-JP', {
      timeZone: 'Asia/Tokyo', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
    }).format(new Date(seconds * 1000));
  } catch { return fallback || ''; }
}

function dayKey(epoch) {
  const seconds = Number(epoch);
  if (!Number.isFinite(seconds) || seconds <= 0) return 'unknown';
  const parts = Object.fromEntries(dayParts.formatToParts(new Date(seconds * 1000))
    .filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function createDayDivider(item) {
  const divider = document.createElement('div');
  const seconds = Number(item.publishedAtEpoch);
  const label = Number.isFinite(seconds) && seconds > 0 ? dayLabel.format(new Date(seconds * 1000)) : '日時不明';
  divider.className = 'day-divider';
  divider.dataset.day = dayKey(item.publishedAtEpoch);
  divider.setAttribute('role', 'separator');
  divider.setAttribute('aria-label', label);
  const left = document.createElement('span');
  left.className = 'day-sparkle';
  left.setAttribute('aria-hidden', 'true');
  left.textContent = '✦';
  const ribbon = document.createElement('span');
  ribbon.className = 'day-ribbon';
  ribbon.textContent = label;
  const right = document.createElement('span');
  right.className = 'day-sparkle day-sparkle-right';
  right.setAttribute('aria-hidden', 'true');
  right.textContent = '✧';
  divider.append(left, ribbon, right);
  return divider;
}

function ensureViewer() {
  let viewer = document.querySelector('#imageViewer');
  if (viewer) return viewer;
  viewer = document.createElement('div');
  viewer.id = 'imageViewer';
  viewer.className = 'image-viewer';
  viewer.hidden = true;
  viewer.setAttribute('role', 'dialog');
  viewer.setAttribute('aria-modal', 'true');
  viewer.setAttribute('aria-label', '記事画像ビューア');
  viewer.innerHTML = `<button class="viewer-close" type="button" aria-label="閉じる">×</button>
    <button class="viewer-nav viewer-prev" type="button" aria-label="前の画像">‹</button>
    <figure class="viewer-figure"><img class="viewer-image" alt="記事画像" referrerpolicy="no-referrer"><figcaption class="viewer-count"></figcaption></figure>
    <button class="viewer-nav viewer-next" type="button" aria-label="次の画像">›</button>`;
  document.body.appendChild(viewer);
  viewer.querySelector('.viewer-close').addEventListener('click', closeViewer);
  viewer.querySelector('.viewer-prev').addEventListener('click', () => moveViewer(-1));
  viewer.querySelector('.viewer-next').addEventListener('click', () => moveViewer(1));
  viewer.addEventListener('click', (event) => { if (event.target === viewer) closeViewer(); });
  document.addEventListener('keydown', (event) => {
    if (viewer.hidden) return;
    if (event.key === 'Escape') closeViewer();
    if (event.key === 'ArrowLeft') moveViewer(-1);
    if (event.key === 'ArrowRight') moveViewer(1);
  });
  return viewer;
}

function updateViewer() {
  const viewer = ensureViewer();
  const image = viewer.querySelector('.viewer-image');
  const count = viewer.querySelector('.viewer-count');
  const candidates = imageCandidates([viewerImages[viewerIndex]]);
  let candidateIndex = 0;
  image.onerror = () => {
    candidateIndex += 1;
    if (candidateIndex < candidates.length) image.src = candidates[candidateIndex];
  };
  image.src = candidates[0] || '';
  count.textContent = viewerImages.length ? `${viewerIndex + 1} / ${viewerImages.length}` : '';
  const single = viewerImages.length <= 1;
  viewer.querySelector('.viewer-prev').hidden = single;
  viewer.querySelector('.viewer-next').hidden = single;
}

function openViewer(images, index = 0, opener = null) {
  const unique = [...new Set(images.filter(Boolean))];
  if (!unique.length) return;
  viewerImages = unique;
  viewerIndex = Math.max(0, Math.min(index, unique.length - 1));
  viewerOpener = opener instanceof HTMLElement ? opener : document.activeElement;
  const viewer = ensureViewer();
  updateViewer();
  viewer.hidden = false;
  document.body.classList.add('viewer-open');
  viewer.querySelector('.viewer-close').focus();
}

function closeViewer() {
  const viewer = document.querySelector('#imageViewer');
  if (!viewer || viewer.hidden) return;
  viewer.hidden = true;
  viewer.querySelector('.viewer-image').removeAttribute('src');
  document.body.classList.remove('viewer-open');
  viewerOpener?.focus?.();
  viewerOpener = null;
}

function moveViewer(delta) {
  if (viewerImages.length <= 1) return;
  viewerIndex = (viewerIndex + delta + viewerImages.length) % viewerImages.length;
  updateViewer();
}

function updateStripCounts(strip) {
  const slides = [...strip.querySelectorAll('.inline-image-slide')];
  slides.forEach((slide, index) => {
    const count = slide.querySelector('.inline-image-count');
    if (count) count.textContent = `${index + 1}/${slides.length}`;
  });
  if (slides.length < 2) strip.remove();
}

function fitSlideToImage(button, image) {
  const ratio = image.naturalWidth / image.naturalHeight;
  const height = button.getBoundingClientRect().height || (window.innerWidth <= 700 ? 180 : 196);
  const minWidth = window.innerWidth <= 700 ? 96 : 108;
  const maxWidth = Math.min(window.innerWidth * .70, 300);
  button.style.width = `${Math.round(Math.max(minWidth, Math.min(maxWidth, height * ratio)))}px`;
}

function buildInlineGallery(article, heroButton, images, titleText) {
  if (images.length < 2) return;
  const strip = document.createElement('div');
  strip.className = 'inline-image-strip';
  strip.setAttribute('role', 'group');
  strip.setAttribute('aria-label', `${images.length}枚の記事画像。横にスワイプできます`);
  images.forEach((url, originalIndex) => {
    const button = document.createElement('button');
    button.className = 'inline-image-slide';
    button.type = 'button';
    button.setAttribute('aria-label', `画像 ${originalIndex + 1} を拡大`);
    const image = document.createElement('img');
    image.alt = titleText ? `${titleText} の画像 ${originalIndex + 1}` : '';
    image.loading = 'lazy';
    image.decoding = 'async';
    const count = document.createElement('span');
    count.className = 'inline-image-count';
    count.setAttribute('aria-hidden', 'true');
    button.append(image, count);
    strip.appendChild(button);
    setImageWithFallback(image, null, [url], {
      onValid: () => { fitSlideToImage(button, image); updateStripCounts(strip); },
      onExhausted: () => { button.remove(); updateStripCounts(strip); },
    });
    button.addEventListener('click', () => {
      const validImages = [...strip.querySelectorAll('.inline-image-slide img')]
        .filter(largeEnough).map((img) => img.currentSrc || img.src).filter(Boolean);
      const validSlides = [...strip.querySelectorAll('.inline-image-slide')];
      openViewer(validImages.length ? validImages : images, Math.max(0, validSlides.indexOf(button)), button);
    });
  });
  heroButton.insertAdjacentElement('afterend', strip);
  updateStripCounts(strip);
  article.classList.add('has-inline-gallery');
}

function addAiSummary(body, summaryText) {
  if (!summaryText) return null;
  const box = document.createElement('div');
  box.className = 'ai-summary';
  const label = document.createElement('div');
  label.className = 'ai-summary-label';
  label.textContent = '✦ AI要約';
  const text = document.createElement('p');
  text.textContent = summaryText;
  box.append(label, text);
  body.insertAdjacentElement('beforebegin', box);
  return box;
}

function createCard(item) {
  const fragment = els.template.content.cloneNode(true);
  const article = fragment.querySelector('.news-card');
  const imageButton = fragment.querySelector('.card-image-link');
  const imageWrap = fragment.querySelector('.card-image-wrap');
  const image = fragment.querySelector('.card-image');
  const badge = fragment.querySelector('.region-badge');
  const platform = fragment.querySelector('.platform');
  const published = fragment.querySelector('.published');
  const title = fragment.querySelector('.card-title');
  const body = fragment.querySelector('.card-body');
  const more = fragment.querySelector('.more-button');
  const actions = fragment.querySelector('.card-actions');
  const source = fragment.querySelector('.source-button');
  const sourceUrl = safeHttpUrl(item.sourceUrl);
  const images = imageList(item);
  const titleOriginal = item.title || 'タイトルなし';
  const bodyOriginal = item.body || item.title || '';
  const titleJapanese = item.titleJa || titleOriginal;
  const bodyJapanese = item.bodyJa || bodyOriginal;
  const hasAi = Boolean(item.aiProcessed && item.summaryJa);
  const hasTranslation = Boolean(hasAi && item.region !== 'JAPAN' &&
    (titleJapanese !== titleOriginal || bodyJapanese !== bodyOriginal));
  article.id = item.id ? `article-${item.id}` : '';
  article.dataset.articleId = item.id || '';
  article.dataset.sourceUrl = sourceUrl;
  source.href = sourceUrl || '#';
  if (!sourceUrl) source.hidden = true;
  badge.textContent = regionNames[item.region] || item.region || 'NEWS';
  platform.textContent = item.platform || '公式';
  if (hasAi) {
    const aiBadge = document.createElement('span');
    aiBadge.className = 'ai-badge';
    aiBadge.textContent = item.region === 'JAPAN' ? 'AI要約' : 'AI翻訳';
    platform.insertAdjacentElement('afterend', aiBadge);
  }
  published.textContent = formatDate(item.publishedAtEpoch, item.publishedLabel);
  const epoch = Number(item.publishedAtEpoch);
  if (Number.isFinite(epoch) && epoch > 0) published.dateTime = new Date(epoch * 1000).toISOString();
  title.textContent = titleJapanese;
  body.textContent = bodyJapanese;
  const summary = hasAi ? addAiSummary(body, item.summaryJa) : null;
  if (images.length) {
    image.alt = `${titleJapanese} の画像`;
    setImageWithFallback(image, imageWrap, images);
    imageButton.addEventListener('click', () => {
      if (imageWrap.classList.contains('is-fallback')) return;
      const loaded = [image, ...article.querySelectorAll('.inline-image-slide img')]
        .filter(largeEnough).map((img) => img.currentSrc || img.src).filter(Boolean);
      openViewer(loaded.length ? loaded : images, 0, imageButton);
    });
  } else {
    imageWrap.classList.add('is-fallback');
    imageButton.disabled = true;
  }
  buildInlineGallery(article, imageButton, images, titleJapanese);
  let showingOriginal = false;
  if (hasTranslation) {
    const originalButton = document.createElement('button');
    originalButton.className = 'original-button';
    originalButton.type = 'button';
    originalButton.textContent = '原文';
    originalButton.addEventListener('click', () => {
      showingOriginal = !showingOriginal;
      title.textContent = showingOriginal ? titleOriginal : titleJapanese;
      body.textContent = showingOriginal ? bodyOriginal : bodyJapanese;
      summary?.classList.toggle('is-hidden-for-original', showingOriginal);
      originalButton.textContent = showingOriginal ? '日本語' : '原文';
      article.classList.remove('is-expanded');
      more.textContent = '続きを読む';
    });
    actions.insertBefore(originalButton, source);
  }
  more.hidden = Math.max(bodyJapanese.length, bodyOriginal.length) <= 150;
  more.addEventListener('click', () => {
    const expanded = article.classList.toggle('is-expanded');
    more.textContent = expanded ? '閉じる' : '続きを読む';
  });
  return fragment;
}

function updateCounts() {
  for (const region of ['ALL', 'JAPAN', 'CHINA', 'KOREA', 'GLOBAL']) {
    const count = region === 'ALL' ? state.items.length : state.items.filter((item) => item.region === region).length;
    const target = document.querySelector(`[data-count="${region}"]`);
    if (target) target.textContent = String(count);
  }
}

function repairOverflowButtons() {
  for (const card of els.grid.querySelectorAll('.news-card')) {
    const body = card.querySelector('.card-body');
    const button = card.querySelector('.more-button');
    if (body && button?.hidden && body.scrollHeight > body.clientHeight + 2) button.hidden = false;
  }
}

function render() {
  const items = filteredItems();
  const fragment = document.createDocumentFragment();
  let previousDay = null;
  for (const item of items) {
    const key = dayKey(item.publishedAtEpoch);
    if (key !== previousDay) {
      previousDay = key;
      fragment.appendChild(createDayDivider(item));
    }
    fragment.appendChild(createCard(item));
  }
  els.grid.replaceChildren(fragment);
  els.grid.setAttribute('aria-busy', 'false');
  els.empty.hidden = items.length !== 0 || state.items.length === 0;
  els.emptyMessage.textContent = '地域タブを変えてみてください。';
  els.error.hidden = true;
  updateCounts();
  document.dispatchEvent(new CustomEvent('kirapara:rendered', {
    detail: { items, region: state.region },
  }));
  requestAnimationFrame(repairOverflowButtons);
}

function renderSkeletons() {
  els.grid.replaceChildren();
  els.grid.setAttribute('aria-busy', 'true');
  const fragment = document.createDocumentFragment();
  for (let index = 0; index < 4; index += 1) {
    const skeleton = document.createElement('div');
    skeleton.className = 'skeleton';
    skeleton.setAttribute('aria-hidden', 'true');
    fragment.appendChild(skeleton);
  }
  els.grid.appendChild(fragment);
}

function latestUpdateLabel(items) {
  const latest = items.reduce((max, item) => Math.max(max, Number(item.publishedAtEpoch) || 0), 0);
  const aiCount = items.filter((item) => item.aiProcessed && item.summaryJa).length;
  if (!latest) return `${items.length}件${aiCount ? ` · AI ${aiCount}件` : ''}`;
  const label = new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(new Date(latest * 1000));
  return `${items.length}件 · 最新記事 ${label}${aiCount ? ` · AI ${aiCount}件` : ''}`;
}

function loadCachedNews() {
  try {
    const cached = JSON.parse(storageGet(CACHE_KEY) || 'null');
    return Array.isArray(cached?.items) ? cached.items : [];
  } catch { return []; }
}

async function loadNews({ force = false } = {}) {
  document.body.classList.toggle('refreshing', force);
  els.error.hidden = true;
  if (!state.items.length) renderSkeletons();
  try {
    const url = force ? `${DATA_URL}?t=${Date.now()}` : `${DATA_URL}?v=4`;
    const response = await fetch(url, { cache: force ? 'no-store' : 'no-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const json = await response.json();
    if (!Array.isArray(json)) throw new Error('ニュースデータの形式が不正です');
    state.items = json.filter((item) => item && typeof item === 'object')
      .sort((a, b) => (Number(b.publishedAtEpoch) || 0) - (Number(a.publishedAtEpoch) || 0));
    storageSet(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), items: state.items }));
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
      els.errorMessage.textContent = `ニュースを取得できませんでした (${error.message})`;
      els.status.textContent = '読み込み失敗';
    }
  } finally {
    document.body.classList.remove('refreshing');
  }
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  storageSet(THEME_KEY, theme);
  els.theme.textContent = theme === 'light' ? '☀' : '☾';
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'light' ? '#fff7fc' : '#120913');
}

function initTheme() {
  const saved = storageGet(THEME_KEY);
  const preferred = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  setTheme(saved === 'light' || saved === 'dark' ? saved : preferred);
}

els.tabs.addEventListener('click', (event) => {
  const button = event.target.closest('[data-region]');
  if (!button) return;
  state.region = button.dataset.region;
  for (const tab of els.tabs.querySelectorAll('.region-tab')) tab.classList.toggle('is-active', tab === button);
  render();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});
els.refresh.addEventListener('click', () => loadNews({ force: true }));
els.retry.addEventListener('click', () => loadNews({ force: true }));
els.theme.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'));
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
  window.addEventListener('load', () => navigator.serviceWorker.register('./sw.js').then((registration) => registration.update()).catch(() => {}));
}

initTheme();
loadNews();
