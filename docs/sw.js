const CACHE_NAME = 'kirapara-pwa-shell-v29';
const APP_SHELL = [
  './','./index.html','./gap.html','./styles.css','./ai.css','./share.css','./theme-kawaii.css','./layout-fixes.css','./gallery-strip.css','./month-sections.css','./early-info.css','./topics.css','./menu.css','./menu-install.css','./dev-release.css','./gap.css','./app.js','./feed-status.js','./topics.js','./x-image-fix.js','./ui_fixes.js','./gallery-strip.js','./month-sections.js','./early-info.js','./share.js','./menu.js','./menu-install.js','./dev-release.js','./theme-kawaii.js','./gap.js','./manifest.webmanifest','./icon.svg'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

function cacheResponse(request, response) {
  if (!response || response.status !== 200) return response;
  const copy = response.clone();
  caches.open(CACHE_NAME).then((cache) => cache.put(request, copy)).catch(() => {});
  return response;
}

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.hostname === 'raw.githubusercontent.com' || url.hostname === 'api.github.com') return;

  const sameOrigin = url.origin === self.location.origin;
  const isUiAsset = sameOrigin && (
    event.request.mode === 'navigate' ||
    /\.(?:html|js|css)$/.test(url.pathname) ||
    url.pathname.endsWith('/')
  );

  if (isUiAsset) {
    event.respondWith(
      fetch(event.request)
        .then((response) => cacheResponse(event.request, response))
        .catch(() => caches.match(event.request).then((cached) => cached || caches.match('./index.html')))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => cacheResponse(event.request, response));
    })
  );
});
