const CACHE_NAME = 'kirapara-pwa-shell-v77';
const APP_SHELL = [
  './',
  './index.html',
  './gap.html',
  './terms.html',
  './privacy.html',
  './styles.css',
  './ai.css',
  './translation-wait.css',
  './share.css',
  './theme-kawaii.css',
  './layout-fixes.css',
  './gallery-strip.css',
  './day-sections.css',
  './monthly-top.css',
  './game-notices.css',
  './menu.css',
  './menu-install.css',
  './menu-discord.js',
  './source-buttons.css',
  './reactions.css',
  './x-image-size.css',
  './gap.css',
  './legal.css',
  './analytics-config.js',
  './analytics-track.js',
  './pagination.js',
  './app.js',
  './translation-wait.js',
  './game-notices.js',
  './x-image-fix.js',
  './source-buttons.js',
  './crawl-status.js',
  './weibo-image-fallback.js',
  './share.js',
  './reactions.js',
  './monthly-top.js',
  './menu.js',
  './menu-install.js',
  './app-share.js',
  './media/share/kirapara-news-share.b64.0',
  './media/share/kirapara-news-share.b64.1',
  './media/share/kirapara-news-share.b64.2',
  './media/share/kirapara-news-share.b64.3',
  './media/share/kirapara-news-share.b64.4',
  './media/share/kirapara-news-share.b64.5',
  './back-navigation.js',
  './viewer-lifecycle-fix.js',
  './viewer-swipe.js',
  './gap.js',
  './manifest.webmanifest',
  './icon.svg',
];
const SHELL_URLS = new Set(APP_SHELL.map((path) => new URL(path, self.registration.scope).href));

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith('kirapara-pwa-shell-') && key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

async function navigationResponse(request) {
  let response;
  try {
    response = await fetch(request, { cache: 'no-store' });
    if (response?.ok) {
      await rememberResponse(request, response);
      return response;
    }
  } catch {}
  return (await cachedResponse(request)) || (await cachedResponse('./index.html')) || response || Response.error();
}

async function rememberResponse(request, response) {
  try {
    const cache = await caches.open(CACHE_NAME);
    await cache.put(request, response.clone());
  } catch {} // Cache storage failure must not discard a successful response.
}

async function cachedResponse(request) {
  try {
    const cache = await caches.open(CACHE_NAME);
    return await cache.match(request, { ignoreSearch: true });
  } catch { return undefined; }
}

async function shellResponse(request) {
  let response;
  try {
    response = await fetch(request, { cache: 'no-store' });
    if (response?.ok) {
      await rememberResponse(request, response);
      return response;
    }
  } catch {}
  return (await cachedResponse(request)) || response || Response.error();
}

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  if (event.request.mode === 'navigate') {
    event.respondWith(navigationResponse(event.request));
    return;
  }

  if (SHELL_URLS.has(`${url.origin}${url.pathname}`)) event.respondWith(shellResponse(event.request));
});
