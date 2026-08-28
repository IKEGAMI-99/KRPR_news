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
    // The mirror script only publishes this field when every source image was
    // downloaded successfully. Keep the count check here as a second guard so a
    // partial/stale mirror can never collapse a multi-image Weibo post.
    return mirrors.length === sourceImages.length ? mirrors : [];
  }

  window.imageList = function imageListWithWeiboMirror(item) {
    const sourceImages = originalImageList(item);
    const mirrors = validMirrorList(item, sourceImages);
    return mirrors.length ? mirrors : sourceImages;
  };
})();
