(() => {
  function upgradeXImage(url) {
    if (!url) return url;
    try {
      const parsed = new URL(url, location.href);
      if (parsed.hostname !== 'pbs.twimg.com') return parsed.href;
      if (!/^\/(media|tweet_video_thumb|ext_tw_video_thumb)\//.test(parsed.pathname)) return parsed.href;
      parsed.searchParams.set('name', 'orig');
      return parsed.href;
    } catch {
      return url;
    }
  }

  function upgradeCardImages(root = document) {
    root.querySelectorAll?.('.news-card img').forEach((img) => {
      const current = img.getAttribute('src');
      const upgraded = upgradeXImage(current);
      if (upgraded && upgraded !== current) img.setAttribute('src', upgraded);
    });
  }

  const grid = document.querySelector('#newsGrid');
  if (grid) {
    new MutationObserver(() => upgradeCardImages(grid)).observe(grid, { childList: true, subtree: true });
    upgradeCardImages(grid);
  }

  if (typeof openViewer === 'function') {
    const originalOpenViewer = openViewer;
    openViewer = function(images, index = 0) {
      const upgraded = (Array.isArray(images) ? images : []).map(upgradeXImage);
      originalOpenViewer(upgraded, index);
      requestAnimationFrame(() => {
        const figure = document.querySelector('#imageViewer .viewer-figure');
        const image = document.querySelector('#imageViewer .viewer-image');
        if (figure) {
          figure.style.width = '92vw';
          figure.style.maxWidth = '1080px';
        }
        if (image) {
          image.style.display = 'block';
          image.style.width = '92vw';
          image.style.height = '82vh';
          image.style.maxWidth = '1080px';
          image.style.maxHeight = '82vh';
          image.style.objectFit = 'contain';
          image.style.objectPosition = 'center';
        }
      });
    };
  }
})();
