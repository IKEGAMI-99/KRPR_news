(() => {
  const originalImageList = window.imageList;
  const originalImageCandidates = window.imageCandidates;
  if (typeof originalImageList !== 'function' || typeof originalImageCandidates !== 'function') return;

  function isRepoMirror(value) {
    if (typeof value !== 'string' || !/^https:\/\//i.test(value)) return false;
    try {
      const parsed = new URL(value);
      const pagesMirror = parsed.hostname === 'ikegami-99.github.io' && parsed.pathname.startsWith('/KRPR_news/media/weibo/');
      const rawMirror = parsed.hostname === 'raw.githubusercontent.com' && parsed.pathname.includes('/IKEGAMI-99/KRPR_news/main/docs/media/weibo/');
      return pagesMirror || rawMirror;
    } catch {
      return false;
    }
  }

  function validMirrorList(item, sourceImages) {
    if (!Array.isArray(item?.imageMirrorUrls)) return [];
    const mirrors = item.imageMirrorUrls.filter(isRepoMirror);
    // The mirror job only publishes this field when every source image was
    // downloaded. Keep the count check here too so a stale/partial mirror can
    // never turn one Weibo gallery item into missing or duplicated slides.
    return mirrors.length === sourceImages.length ? mirrors : [];
  }

  function rawBackupForPages(url) {
    try {
      const parsed = new URL(url);
      if (parsed.hostname !== 'ikegami-99.github.io' || !parsed.pathname.startsWith('/KRPR_news/media/weibo/')) return '';
      const filename = parsed.pathname.split('/').pop();
      return filename ? `https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/docs/media/weibo/${filename}` : '';
    } catch {
      return '';
    }
  }

  window.imageList = function imageListWithWeiboMirror(item) {
    const sourceImages = originalImageList(item);
    const mirrors = validMirrorList(item, sourceImages);
    return mirrors.length ? mirrors : sourceImages;
  };

  window.imageCandidates = function imageCandidatesWithMirrorBackup(urls) {
    const expanded = [];
    for (const url of urls || []) {
      expanded.push(url);
      const rawBackup = rawBackupForPages(url);
      if (rawBackup) expanded.push(rawBackup);
    }
    return originalImageCandidates(expanded);
  };

  // app.js starts loadNews() before this shim executes. Normally the fetch is
  // still pending, but do not rely on network timing: if rendering somehow
  // finished first, immediately rebuild the grid with the mirror-aware list.
  try {
    if (typeof render === 'function' && typeof state === 'object' && Array.isArray(state.items) && state.items.length) {
      render();
    }
  } catch {
    // The normal async load path will use the overrides on its first render.
  }
})();
