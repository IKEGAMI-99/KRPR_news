(() => {
  const X_IMAGE_HOST = 'pbs.twimg.com';
  const X_IMAGE_PATH = /^\/(?:media|tweet_video_thumb|ext_tw_video_thumb)\//;
  const LEGACY_SIZE_SUFFIX = /:(?:thumb|small|medium|large)$/i;

  function preferOriginalXImage(value) {
    try {
      const url = new URL(String(value || ''), location.href);
      if (url.hostname.toLowerCase() !== X_IMAGE_HOST || !X_IMAGE_PATH.test(url.pathname)) {
        return url.href;
      }

      // X sometimes exposes legacy URLs such as image.jpg:small.
      url.pathname = url.pathname.replace(LEGACY_SIZE_SUFFIX, '');

      // Modern pbs.twimg.com URLs use the name query parameter for sizing.
      // Force the original asset instead of thumb/small/medium/large variants.
      url.searchParams.set('name', 'orig');
      return url.href;
    } catch {
      return String(value || '');
    }
  }

  // Replace app.js' helper for any image URLs processed after this script loads.
  try {
    if (typeof upgradeXImage === 'function') {
      upgradeXImage = preferOriginalXImage;
    }
  } catch {}

  function upgradeImageElement(image) {
    if (!(image instanceof HTMLImageElement)) return;
    const current = image.getAttribute('src');
    if (!current) return;
    const upgraded = preferOriginalXImage(current);
    if (upgraded && upgraded !== new URL(current, location.href).href) {
      image.src = upgraded;
    }
  }

  function scan(root = document) {
    if (root instanceof HTMLImageElement) upgradeImageElement(root);
    root.querySelectorAll?.('img[src]').forEach(upgradeImageElement);
  }

  scan();

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'attributes') {
        upgradeImageElement(mutation.target);
        continue;
      }
      for (const node of mutation.addedNodes) {
        if (node instanceof Element) scan(node);
      }
    }
  });

  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['src'],
  });
})();
