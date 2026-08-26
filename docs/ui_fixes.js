(() => {
  const grid = document.querySelector('#newsGrid');
  if (!grid) return;

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

  function cardImages(card) {
    const values = [
      card.querySelector('.card-image')?.currentSrc,
      card.querySelector('.card-image')?.src,
      ...Array.from(card.querySelectorAll('.article-gallery img')).map((img) => img.currentSrc || img.src),
    ];
    const seen = new Set();
    return values.filter((value) => {
      if (!value || seen.has(value)) return false;
      seen.add(value);
      return true;
    });
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
