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

  function isSinaImage(url) {
    try {
      const host = new URL(url, location.href).hostname.toLowerCase();
      return /(^|\.)sinaimg\.(?:cn|com)$/.test(host);
    } catch {
      return false;
    }
  }

  function weiboVariants(url) {
    if (!isSinaImage(url)) return [url];
    try {
      const parsed = new URL(url, location.href);
      const match = parsed.hostname.match(/(?:tvax|tva|wx|ww)(\d+)/i);
      const shard = match?.[1] || '1';
      const filename = parsed.pathname.split('/').filter(Boolean).pop();
      if (!filename) return [url];
      const values = [
        `https://wx${shard}.sinaimg.cn/large/${filename}`,
        `https://ww${shard}.sinaimg.cn/large/${filename}`,
        `https://wx${shard}.sinaimg.cn/mw2000/${filename}`,
        `https://tvax${shard}.sinaimg.cn/large/${filename}`,
        parsed.href.replace(/^http:/i, 'https:')
      ];
      return [...new Set(values)];
    } catch {
      return [url];
    }
  }

  function armWeiboFallback(img) {
    const current = img.getAttribute('src') || '';
    if (!current || !isSinaImage(current)) return;

    let candidates = [];
    try { candidates = JSON.parse(img.dataset.weiboCandidates || '[]'); } catch {}
    if (!Array.isArray(candidates) || !candidates.length) {
      candidates = weiboVariants(current);
      img.dataset.weiboCandidates = JSON.stringify(candidates);
      img.dataset.weiboCandidateIndex = '0';
    }

    const currentAbsolute = (() => { try { return new URL(current, location.href).href; } catch { return current; } })();
    const currentIndex = candidates.indexOf(currentAbsolute);
    if (currentIndex >= 0) img.dataset.weiboCandidateIndex = String(currentIndex);

    const preferred = candidates[0];
    if (preferred && currentIndex < 0 && preferred !== currentAbsolute) {
      img.dataset.weiboCandidateIndex = '0';
      img.setAttribute('src', preferred);
    }
    img.referrerPolicy = 'no-referrer';
  }

  // Sina's image CDN is inconsistent about which host/size alias accepts a
  // browser hotlink. Catch the failure before app.js removes the image and try
  // equivalent CDN forms of the same Weibo image ID.
  document.addEventListener('error', (event) => {
    const img = event.target;
    if (!(img instanceof HTMLImageElement) || !isSinaImage(img.getAttribute('src') || '')) return;
    let candidates = [];
    try { candidates = JSON.parse(img.dataset.weiboCandidates || '[]'); } catch {}
    if (!Array.isArray(candidates) || !candidates.length) candidates = weiboVariants(img.getAttribute('src') || '');
    const index = Number(img.dataset.weiboCandidateIndex || 0);
    if (index + 1 >= candidates.length) return;
    event.stopImmediatePropagation();
    event.preventDefault?.();
    const next = index + 1;
    img.dataset.weiboCandidates = JSON.stringify(candidates);
    img.dataset.weiboCandidateIndex = String(next);
    img.referrerPolicy = 'no-referrer';
    img.setAttribute('src', candidates[next]);
  }, true);

  function upgradeCardImages(root = document) {
    root.querySelectorAll?.('.news-card img, #imageViewer img').forEach((img) => {
      const current = img.getAttribute('src');
      const upgraded = upgradeXImage(current);
      if (upgraded && upgraded !== current) img.setAttribute('src', upgraded);
      armWeiboFallback(img);
    });
  }

  const grid = document.querySelector('#newsGrid');
  if (grid) {
    new MutationObserver(() => upgradeCardImages(document)).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['src'] });
    upgradeCardImages(document);
  }

  if (typeof openViewer === 'function') {
    const originalOpenViewer = openViewer;
    openViewer = function(images, index = 0) {
      const upgraded = (Array.isArray(images) ? images : []).map((url) => {
        const x = upgradeXImage(url);
        return weiboVariants(x)[0] || x;
      });
      originalOpenViewer(upgraded, index);
      requestAnimationFrame(() => {
        const figure = document.querySelector('#imageViewer .viewer-figure');
        const image = document.querySelector('#imageViewer .viewer-image');
        if (figure) {
          figure.style.width = '92vw';
          figure.style.maxWidth = '1080px';
        }
        if (image) {
          armWeiboFallback(image);
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

  window.kiraparaWeiboImageVariants = weiboVariants;
})();
