const CACHE_NAME = 'kirapara-pwa-shell-v50';
const APP_SHELL = [
  './',
  './index.html',
  './gap.html',
  './styles.css',
  './ai.css',
  './share.css',
  './theme-kawaii.css',
  './layout-fixes.css',
  './gallery-strip.css',
  './day-sections.css',
  './menu.css',
  './menu-install.css',
  './source-buttons.css',
  './x-image-size.css',
  './gap.css',
  './analytics-config.js',
  './analytics-track.js',
  './app.js',
  './x-image-fix.js',
  './source-buttons.js',
  './crawl-status.js',
  './weibo-image-fallback.js',
  './share.js',
  './menu.js',
  './menu-install.js',
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
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

async function navigationResponse(request) {
  try {
    const response = await fetch(request);
    if (response?.ok) {
      const cache = await caches.open(CACHE_NAME);
      await cache.put(request, response.clone());
    }
    return response;
  } catch {
    return (await caches.match(request)) || caches.match('./index.html');
  }
}

async function shellResponse(request) {
  const cached = await caches.match(request, { ignoreSearch: true });
  if (cached) return cached;
  return fetch(request);
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
