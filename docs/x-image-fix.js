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

      url.pathname = url.pathname.replace(LEGACY_SIZE_SUFFIX, '');
      url.searchParams.set('name', 'orig');
      return url.href;
    } catch {
      return String(value || '');
    }
  }

  // app.js calls upgradeXImage while building cards and viewer candidates.
  // Replacing that helper is enough; a document-wide MutationObserver that
  // rewrites every img[src] caused unnecessary work during scrolling on Android.
  try {
    if (typeof upgradeXImage === 'function') upgradeXImage = preferOriginalXImage;
  } catch {}
})();
