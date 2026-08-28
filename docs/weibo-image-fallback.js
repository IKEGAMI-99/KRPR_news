(() => {
  const originalImageList = window.imageList;
  if (typeof originalImageList !== 'function') return;

  function validMirrorList(item, sourceImages) {
    if (!Array.isArray(item?.imageMirrorUrls)) return [];
    const mirrors = item.imageMirrorUrls.filter((value) => {
      if (typeof value !== 'string' || !/^https:\/\//i.test(value)) return false;
      try {
        const parsed = new URL(value);
        return parsed.hostname === 'raw.githubusercontent.com' && parsed.pathname.includes('/IKEGAMI-99/KRPR_news/');
      } catch {
        return false;
      }
    });
    // The mirror job only publishes this field when every source image was
    // downloaded. Keep the count check here too so a stale/partial mirror can
    // never turn one Weibo gallery item into missing or duplicated slides.
    return mirrors.length === sourceImages.length ? mirrors : [];
  }

  window.imageList = function imageListWithWeiboMirror(item) {
    const sourceImages = originalImageList(item);
    const mirrors = validMirrorList(item, sourceImages);
    return mirrors.length ? mirrors : sourceImages;
  };

  // app.js starts loadNews() before this shim executes. Normally the fetch is
  // still pending, but do not rely on network timing: if rendering somehow
  // finished first, immediately rebuild the grid with the mirror-aware list.
  try {
    if (typeof render === 'function' && typeof state === 'object' && Array.isArray(state.items) && state.items.length) {
      render();
    }
  } catch {
    // The normal async load path will use the override on its first render.
  }
})();
