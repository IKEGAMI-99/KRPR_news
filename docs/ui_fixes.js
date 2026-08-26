(() => {
  const grid = document.querySelector('#newsGrid');
  if (!grid) return;

  const MIN_SHORT_SIDE = 260;
  const MIN_AREA = 150000;

  function largeEnough(img) {
    if (!img || !img.naturalWidth || !img.naturalHeight) return true;
    return Math.min(img.naturalWidth, img.naturalHeight) >= MIN_SHORT_SIDE &&
      img.naturalWidth * img.naturalHeight >= MIN_AREA;
  }

  function probeLarge(url) {
    return new Promise((resolve) => {
      if (!url) return resolve(false);
      const probe = new Image();
      probe.referrerPolicy = 'no-referrer';
      probe.onload = () => resolve(largeEnough(probe));
      probe.onerror = () => resolve(false);
      probe.src = url;
    });
  }

  function repairReadMore(card) {
    const body = card.querySelector('.card-body');
    const button = card.querySelector('.more-button');
    if (!body || !button || !button.hidden || button.dataset.overflowFix === '1') return;

    requestAnimationFrame(() => {
      if (!button.hidden || button.dataset.overflowFix === '1') return;
      const clipped = body.scrollHeight > body.clientHeight + 2;
      if (!clipped) return;

      button.hidden = false;
      button.dataset.overflowFix = '1';
      button.addEventListener('click', () => {
        const expanded = card.classList.toggle('is-expanded');
        button.textContent = expanded ? '閉じる' : '続きを読む';
      });
    });
  }

  async function repairMainImage(card) {
    const image = card.querySelector('.card-image');
    const wrap = card.querySelector('.card-image-wrap');
    if (!image || !wrap || image.dataset.qualityFix === '1') return;
    image.dataset.qualityFix = '1';

    const validate = async () => {
      if (largeEnough(image)) return;
      const current = image.currentSrc || image.src;
      const candidates = Array.from(card.querySelectorAll('.article-gallery img'))
        .map((img) => img.currentSrc || img.src)
        .filter((url) => url && url !== current);

      for (const url of candidates) {
        if (await probeLarge(url)) {
          image.src = url;
          wrap.classList.remove('is-fallback');
          return;
        }
      }
      image.removeAttribute('src');
      wrap.classList.add('is-fallback');
    };

    image.addEventListener('load', validate);
    if (image.complete && image.naturalWidth) validate();
  }

  function repairGallery(card) {
    for (const img of card.querySelectorAll('.article-gallery img')) {
      if (img.dataset.qualityFix === '1') continue;
      img.dataset.qualityFix = '1';
      const validate = () => {
        if (!largeEnough(img)) img.closest('.gallery-item')?.remove();
      };
      img.addEventListener('load', validate);
      if (img.complete && img.naturalWidth) validate();
    }
  }

  function cardImages(card) {
    const nodes = [card.querySelector('.card-image'), ...card.querySelectorAll('.article-gallery img')].filter(Boolean);
    const seen = new Set();
    const values = [];
    for (const img of nodes) {
      if (!largeEnough(img)) continue;
      const value = img.currentSrc || img.src;
      if (!value || seen.has(value)) continue;
      seen.add(value);
      values.push(value);
    }
    return values;
  }

  function repairThumbnail(card) {
    const link = card.querySelector('.card-image-link');
    const wrap = card.querySelector('.card-image-wrap');
    if (!link || !wrap || link.dataset.viewerFix === '1') return;

    link.dataset.viewerFix = '1';
    link.removeAttribute('href');
    link.removeAttribute('target');
    link.removeAttribute('rel');
    link.setAttribute('role', 'button');
    link.setAttribute('tabindex', '0');
    link.setAttribute('aria-label', 'サムネイル画像を拡大');

    const open = (event) => {
      event.preventDefault();
      if (wrap.classList.contains('is-fallback')) return;
      const images = cardImages(card);
      if (!images.length || typeof openViewer !== 'function') return;
      openViewer(images, 0);
    };

    link.addEventListener('click', open);
    link.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      open(event);
    });
  }

  function repairCard(card) {
    repairReadMore(card);
    repairGallery(card);
    repairMainImage(card);
    repairThumbnail(card);
  }

  function repairAll() {
    grid.querySelectorAll('.news-card').forEach(repairCard);
  }

  const observer = new MutationObserver(repairAll);
  observer.observe(grid, { childList: true, subtree: false });
  window.addEventListener('resize', repairAll, { passive: true });
  repairAll();
})();
