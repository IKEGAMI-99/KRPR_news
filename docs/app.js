const DATA_URL = 'https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/data/news.json';
const CACHE_KEY = 'kirapara-news-cache-v3';
const THEME_KEY = 'kirapara-news-theme';

const state = { items: [], region: 'ALL', installPrompt: null };
const els = {
  grid: document.querySelector('#newsGrid'), template: document.querySelector('#newsCardTemplate'),
  tabs: document.querySelector('#regionTabs'), refresh: document.querySelector('#refreshButton'),
  retry: document.querySelector('#retryButton'), theme: document.querySelector('#themeButton'),
  install: document.querySelector('#installButton'), status: document.querySelector('#statusText'),
  visibleCount: document.querySelector('#visibleCount'), empty: document.querySelector('#emptyState'),
  error: document.querySelector('#errorState'), errorMessage: document.querySelector('#errorMessage'),
};
const regionNames = { JAPAN: '🇯🇵 日本', CHINA: '🇨🇳 中国', KOREA: '🇰🇷 韓国', GLOBAL: '🌐 Global' };
const BAD_IMAGE_TOKENS = [
  'favicon','apple-touch-icon','siteicon','site-icon','logo','brandmark','avatar','profile','author',
  'qrcode','qr-code','qr_code','/qr/','_qr.','sprite','emoji','emoticon','badge','button','loading',
  'spinner','placeholder','noimage','no-image','blank.','spacer.','pixel.','tracking','googleplay',
  'google-play','appstore','app-store','/icon/','/icons/','icon_'
];
let viewerImages = [], viewerIndex = 0;

function looksLikeBadImage(url) {
  const value = String(url || '').toLowerCase();
  if (!/^https?:\/\//.test(value) || /\.(svg|ico)(?:\?|$)/.test(value)) return true;
  return BAD_IMAGE_TOKENS.some((token) => value.includes(token));
}
function imageList(item) {
  const values = [...(Array.isArray(item.imageUrls) ? item.imageUrls : []), ...(item.imageUrl ? [item.imageUrl] : [])];
  const seen = new Set();
  return values.filter((url) => {
    if (!url || looksLikeBadImage(url) || seen.has(url)) return false;
    seen.add(url); return true;
  });
}
function formatDate(epoch, fallback) {
  const seconds = Number(epoch);
  if (!Number.isFinite(seconds) || seconds <= 0) return fallback || '';
  try {
    return new Intl.DateTimeFormat('ja-JP', { month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit' })
      .format(new Date(seconds * 1000));
  } catch { return fallback || ''; }
}
function filteredItems() {
  return state.items.filter((item) => state.region === 'ALL' || item.region === state.region);
}
function updateCounts() {
  for (const region of ['ALL','JAPAN','CHINA','KOREA','GLOBAL']) {
    const count = region === 'ALL' ? state.items.length : state.items.filter((item) => item.region === region).length;
    const target = document.querySelector(`[data-count="${region}"]`);
    if (target) target.textContent = String(count);
  }
}
function setImageWithFallback(image, wrap, urls, startIndex = 0) {
  let index = startIndex;
  const tryNext = () => {
    if (index >= urls.length) { image.removeAttribute('src'); wrap.classList.add('is-fallback'); return; }
    wrap.classList.remove('is-fallback'); image.src = urls[index++];
  };
  image.referrerPolicy = 'no-referrer';
  image.addEventListener('error', tryNext);
  image.addEventListener('load', () => {
    if (image.naturalWidth > 0 && image.naturalHeight > 0 && (image.naturalWidth < 220 || image.naturalHeight < 120)) tryNext();
  });
  tryNext();
}
function ensureViewer() {
  let viewer = document.querySelector('#imageViewer');
  if (viewer) return viewer;
  viewer = document.createElement('div');
  viewer.id = 'imageViewer'; viewer.className = 'image-viewer'; viewer.hidden = true;
  viewer.setAttribute('role','dialog'); viewer.setAttribute('aria-modal','true'); viewer.setAttribute('aria-label','記事画像ビューア');
  viewer.innerHTML = `<button class="viewer-close" type="button" aria-label="閉じる">×</button>
    <button class="viewer-nav viewer-prev" type="button" aria-label="前の画像">‹</button>
    <figure class="viewer-figure"><img class="viewer-image" alt="記事画像" referrerpolicy="no-referrer"><figcaption class="viewer-count"></figcaption></figure>
    <button class="viewer-nav viewer-next" type="button" aria-label="次の画像">›</button>`;
  document.body.appendChild(viewer);
  viewer.querySelector('.viewer-close').addEventListener('click', closeViewer);
  viewer.querySelector('.viewer-prev').addEventListener('click', () => moveViewer(-1));
  viewer.querySelector('.viewer-next').addEventListener('click', () => moveViewer(1));
  viewer.addEventListener('click', (e) => { if (e.target === viewer) closeViewer(); });
  document.addEventListener('keydown', (e) => {
    if (viewer.hidden) return;
    if (e.key === 'Escape') closeViewer(); if (e.key === 'ArrowLeft') moveViewer(-1); if (e.key === 'ArrowRight') moveViewer(1);
  });
  return viewer;
}
function updateViewer() {
  const viewer = ensureViewer(), image = viewer.querySelector('.viewer-image'), count = viewer.querySelector('.viewer-count');
  image.src = viewerImages[viewerIndex] || ''; count.textContent = viewerImages.length ? `${viewerIndex + 1} / ${viewerImages.length}` : '';
  const single = viewerImages.length <= 1; viewer.querySelector('.viewer-prev').hidden = single; viewer.querySelector('.viewer-next').hidden = single;
}
function openViewer(images, index = 0) {
  if (!images.length) return; viewerImages = images; viewerIndex = Math.max(0, Math.min(index, images.length - 1));
  const viewer = ensureViewer(); updateViewer(); viewer.hidden = false; document.body.classList.add('viewer-open');
}
function closeViewer() {
  const viewer = ensureViewer(); viewer.hidden = true; viewer.querySelector('.viewer-image').removeAttribute('src'); document.body.classList.remove('viewer-open');
}
function moveViewer(delta) {
  if (viewerImages.length <= 1) return; viewerIndex = (viewerIndex + delta + viewerImages.length) % viewerImages.length; updateViewer();
}
function buildGallery(article, body, images, titleText) {
  if (!images.length) return null;
  const gallery = document.createElement('div'); gallery.className = 'article-gallery'; gallery.hidden = true;
  images.forEach((url, index) => {
    const button = document.createElement('button'); button.className = 'gallery-item'; button.type = 'button';
    button.setAttribute('aria-label', `画像 ${index + 1} を拡大`);
    const img = document.createElement('img'); img.src = url; img.alt = titleText ? `${titleText} の画像 ${index + 1}` : `記事画像 ${index + 1}`;
    img.loading = 'lazy'; img.decoding = 'async'; img.referrerPolicy = 'no-referrer'; img.addEventListener('error', () => button.remove(), { once:true });
    button.appendChild(img); button.addEventListener('click', () => openViewer(images, index)); gallery.appendChild(button);
  });
  body.insertAdjacentElement('afterend', gallery); article.classList.add('has-gallery'); return gallery;
}
function addAiSummary(body, summaryText) {
  if (!summaryText) return;
  const box = document.createElement('div'); box.className = 'ai-summary';
  const label = document.createElement('div'); label.className = 'ai-summary-label'; label.textContent = '✦ AI要約';
  const text = document.createElement('p'); text.textContent = summaryText; box.append(label, text); body.insertAdjacentElement('beforebegin', box);
}
function createCard(item) {
  const fragment = els.template.content.cloneNode(true), article = fragment.querySelector('.news-card');
  const imageLink = fragment.querySelector('.card-image-link'), imageWrap = fragment.querySelector('.card-image-wrap'), image = fragment.querySelector('.card-image');
  const badge = fragment.querySelector('.region-badge'), platform = fragment.querySelector('.platform'), published = fragment.querySelector('.published');
  const title = fragment.querySelector('.card-title'), body = fragment.querySelector('.card-body'), more = fragment.querySelector('.more-button');
  const actions = fragment.querySelector('.card-actions'), source = fragment.querySelector('.source-button');
  const sourceUrl = item.sourceUrl || '#', images = imageList(item);
  const titleOriginal = item.title || 'タイトルなし', bodyOriginal = item.body || item.title || '';
  const titleJapanese = item.titleJa || titleOriginal, bodyJapanese = item.bodyJa || bodyOriginal;
  const hasAi = Boolean(item.aiProcessed && item.summaryJa);
  const hasTranslation = Boolean(hasAi && item.region !== 'JAPAN' && (titleJapanese !== titleOriginal || bodyJapanese !== bodyOriginal));
  imageLink.href = sourceUrl; source.href = sourceUrl; badge.textContent = regionNames[item.region] || item.region || 'NEWS'; platform.textContent = item.platform || '公式';
  if (hasAi) {
    const aiBadge = document.createElement('span'); aiBadge.className = 'ai-badge'; aiBadge.textContent = item.region === 'JAPAN' ? 'AI要約' : 'AI翻訳';
    platform.insertAdjacentElement('afterend', aiBadge);
  }
  published.textContent = formatDate(item.publishedAtEpoch, item.publishedLabel);
  published.dateTime = item.publishedAtEpoch ? new Date(Number(item.publishedAtEpoch) * 1000).toISOString() : '';
  title.textContent = titleJapanese; body.textContent = bodyJapanese; if (hasAi) addAiSummary(body, item.summaryJa);
  if (images.length) { image.alt = `${titleJapanese} の画像`; setImageWithFallback(image, imageWrap, images); }
  else imageWrap.classList.add('is-fallback');
  const gallery = buildGallery(article, body, images, titleJapanese);
  if (gallery && images.length > 1) {
    const galleryButton = document.createElement('button'); galleryButton.className = 'gallery-button'; galleryButton.type = 'button'; galleryButton.textContent = `画像 ${images.length}枚`;
    galleryButton.addEventListener('click', () => { gallery.hidden = !gallery.hidden; galleryButton.classList.toggle('is-active', !gallery.hidden); galleryButton.textContent = gallery.hidden ? `画像 ${images.length}枚` : '画像を閉じる'; });
    actions.insertBefore(galleryButton, source);
  }
  if (hasTranslation) {
    let showingOriginal = false;
    const originalButton = document.createElement('button'); originalButton.className = 'original-button'; originalButton.type = 'button'; originalButton.textContent = '原文';
    originalButton.addEventListener('click', () => {
      showingOriginal = !showingOriginal; title.textContent = showingOriginal ? titleOriginal : titleJapanese; body.textContent = showingOriginal ? bodyOriginal : bodyJapanese;
      originalButton.textContent = showingOriginal ? '日本語' : '原文'; article.classList.remove('is-expanded'); more.textContent = '続きを読む';
    });
    actions.insertBefore(originalButton, source);
  }
  const canExpand = Math.max(bodyJapanese.length, bodyOriginal.length) > 150;
  if (!canExpand) more.hidden = true;
  else more.addEventListener('click', () => { const expanded = article.classList.toggle('is-expanded'); more.textContent = expanded ? '閉じる' : '続きを読む'; });
  return fragment;
}
function render() {
  const items = filteredItems(); els.grid.replaceChildren(); const fragment = document.createDocumentFragment();
  for (const item of items) fragment.appendChild(createCard(item)); els.grid.appendChild(fragment); els.grid.setAttribute('aria-busy','false');
  els.visibleCount.textContent = `${items.length}件`; els.empty.hidden = items.length !== 0 || state.items.length === 0; els.error.hidden = true; updateCounts();
}
function renderSkeletons() {
  els.grid.replaceChildren(); els.grid.setAttribute('aria-busy','true'); const fragment = document.createDocumentFragment();
  for (let i = 0; i < 4; i++) { const skeleton = document.createElement('div'); skeleton.className = 'skeleton'; skeleton.setAttribute('aria-hidden','true'); fragment.appendChild(skeleton); }
  els.grid.appendChild(fragment);
}
function latestUpdateLabel(items) {
  const latest = items.reduce((max,item) => Math.max(max, Number(item.publishedAtEpoch) || 0), 0);
  const aiCount = items.filter((item) => item.aiProcessed && item.summaryJa).length;
  if (!latest) return `${items.length}件${aiCount ? ` · AI ${aiCount}件` : ''}`;
  const label = new Intl.DateTimeFormat('ja-JP', { month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit' }).format(new Date(latest * 1000));
  return `${items.length}件 · 最新 ${label}${aiCount ? ` · AI ${aiCount}件` : ''}`;
}
async function loadNews({ force = false } = {}) {
  document.body.classList.toggle('refreshing', force); els.error.hidden = true; if (!state.items.length) renderSkeletons();
  try {
    const url = force ? `${DATA_URL}?t=${Date.now()}` : `${DATA_URL}?v=3`, response = await fetch(url, { cache: force ? 'no-store' : 'no-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`); const json = await response.json(); if (!Array.isArray(json)) throw new Error('ニュースデータの形式が不正です');
    state.items = json.filter((item) => item && typeof item === 'object').sort((a,b) => (Number(b.publishedAtEpoch)||0) - (Number(a.publishedAtEpoch)||0));
    localStorage.setItem(CACHE_KEY, JSON.stringify({ savedAt:Date.now(), items:state.items })); els.status.textContent = latestUpdateLabel(state.items); render();
  } catch (error) {
    const cached = loadCachedNews();
    if (cached.length) { state.items = cached; els.status.textContent = `${cached.length}件 · オフラインキャッシュ`; render(); }
    else { state.items = []; els.grid.replaceChildren(); els.grid.setAttribute('aria-busy','false'); els.error.hidden = false; els.empty.hidden = true; els.visibleCount.textContent = '0件'; els.errorMessage.textContent = `ニュースを取得できませんでした (${error.message})`; els.status.textContent = '読み込み失敗'; }
  } finally { document.body.classList.remove('refreshing'); }
}
function loadCachedNews() {
  try { const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null'); return Array.isArray(cached?.items) ? cached.items : []; } catch { return []; }
}
function setTheme(theme) {
  document.documentElement.dataset.theme = theme; localStorage.setItem(THEME_KEY, theme); els.theme.textContent = theme === 'light' ? '☀' : '☾';
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'light' ? '#f5f4f8' : '#101116');
}
function initTheme() {
  const saved = localStorage.getItem(THEME_KEY), preferred = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  setTheme(saved === 'light' || saved === 'dark' ? saved : preferred);
}
els.tabs.addEventListener('click', (event) => {
  const button = event.target.closest('[data-region]'); if (!button) return; state.region = button.dataset.region;
  for (const tab of els.tabs.querySelectorAll('.region-tab')) tab.classList.toggle('is-active', tab === button);
  render(); window.scrollTo({ top:0, behavior:'smooth' });
});
els.refresh.addEventListener('click', () => loadNews({ force:true }));
els.retry.addEventListener('click', () => loadNews({ force:true }));
els.theme.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'));
window.addEventListener('beforeinstallprompt', (event) => { event.preventDefault(); state.installPrompt = event; els.install.hidden = false; });
els.install.addEventListener('click', async () => { if (!state.installPrompt) return; state.installPrompt.prompt(); await state.installPrompt.userChoice; state.installPrompt = null; els.install.hidden = true; });
window.addEventListener('appinstalled', () => { state.installPrompt = null; els.install.hidden = true; });
if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('./sw.js').catch(() => {}));
initTheme(); loadNews();
