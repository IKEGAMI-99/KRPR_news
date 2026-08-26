(() => {
  const grid = document.querySelector('#newsGrid');
  if (!grid) return;

  const MIN_SHORT_SIDE = 260;
  const MIN_AREA = 150000;

  function goodImage(img) {
    if (!img?.naturalWidth || !img?.naturalHeight) return true;
    return Math.min(img.naturalWidth, img.naturalHeight) >= MIN_SHORT_SIDE &&
      img.naturalWidth * img.naturalHeight >= MIN_AREA;
  }

  function sourceUrls(card) {
    const nodes = [
      card.querySelector('.card-image'),
      ...card.querySelectorAll('.article-gallery img')
    ].filter(Boolean);
    const seen = new Set();
    const urls = [];
    for (const img of nodes) {
      const url = img.currentSrc || img.src || img.getAttribute('src');
      if (!url || seen.has(url)) continue;
      seen.add(url);
      urls.push(url);
    }
    return urls;
  }

  function viewerUrls(strip) {
    return [...strip.querySelectorAll('.inline-image-slide img')]
      .filter((img) => goodImage(img))
      .map((img) => img.currentSrc || img.src)
      .filter(Boolean);
  }

  function updateCounts(strip) {
    const slides = [...strip.querySelectorAll('.inline-image-slide')];
    slides.forEach((slide, index) => {
      const count = slide.querySelector('.inline-image-count');
      if (!count) return;
      count.textContent = `${index + 1}/${slides.length}`;
    });
  }

  function buildStrip(card) {
    if (card.dataset.inlineGallery === '1') return;
    card.dataset.inlineGallery = '1';

    const oldHero = card.querySelector('.card-image-link');
    const oldGallery = card.querySelector('.article-gallery');
    if (oldGallery) oldGallery.hidden = true;
    card.querySelector('.gallery-button')?.setAttribute('hidden', '');

    const urls = sourceUrls(card);
    if (!urls.length) return;

    // One image: original large cover only.
    if (urls.length === 1) {
      if (oldHero) oldHero.hidden = false;
      return;
    }

    // Two or more: large representative cover + compact swipe strip directly
    // below it, then the article text.
    if (oldHero) oldHero.hidden = false;

    const strip = document.createElement('div');
    strip.className = 'inline-image-strip';
    strip.setAttribute('role', 'group');
    strip.setAttribute('aria-label', `${urls.length}枚の記事画像。横にスワイプできます`);

    urls.forEach((url) => {
      const button = document.createElement('button');
      button.className = 'inline-image-slide';
      button.type = 'button';
      button.setAttribute('aria-label', '画像を拡大');

      const img = document.createElement('img');
      img.src = url;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';

      const count = document.createElement('span');
      count.className = 'inline-image-count';
      count.setAttribute('aria-hidden', 'true');

      img.addEventListener('load', () => {
        if (goodImage(img)) return;
        button.remove();
        updateCounts(strip);
        if (strip.querySelectorAll('.inline-image-slide').length < 2) strip.remove();
      });
      img.addEventListener('error', () => {
        button.remove();
        updateCounts(strip);
        if (strip.querySelectorAll('.inline-image-slide').length < 2) strip.remove();
      }, { once: true });

      button.addEventListener('click', () => {
        const slides = [...strip.querySelectorAll('.inline-image-slide')];
        const currentIndex = Math.max(0, slides.indexOf(button));
        const images = viewerUrls(strip);
        if (images.length && typeof openViewer === 'function') {
          openViewer(images, Math.min(currentIndex, images.length - 1));
        }
      });

      button.append(img, count);
      strip.appendChild(button);
    });

    if (oldHero) oldHero.insertAdjacentElement('afterend', strip);
    else card.prepend(strip);
    updateCounts(strip);
  }

  function enhanceAll() {
    grid.querySelectorAll('.news-card').forEach(buildStrip);
  }

  const observer = new MutationObserver(enhanceAll);
  observer.observe(grid, { childList: true, subtree: false });
  enhanceAll();
})();
