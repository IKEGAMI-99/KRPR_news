(() => {
  const grid = document.querySelector('#newsGrid');
  if (!grid) return;
  const canonical = (value) => { try { return new URL(value, location.href).href; } catch { return ''; } };
  function decorate() {
    const items = (typeof state !== 'undefined' && Array.isArray(state.items)) ? state.items : [];
    grid.querySelectorAll('.news-card').forEach((card) => {
      if (card.querySelector('.early-info-badge')) return;
      const url = canonical(card.querySelector('.source-button')?.href);
      const item = items.find((row) => canonical(row?.sourceUrl) === url);
      if (!item?.earlyInfo) return;
      const meta = card.querySelector('.card-meta');
      const published = card.querySelector('.published');
      if (!meta) return;
      const badge = document.createElement('span');
      badge.className = 'early-info-badge';
      badge.textContent = '✦ 先行情報';
      badge.title = item.earlyInfoReason || '海外版で先に告知され、日本版に同内容の告知がまだ見つかっていない可能性があります';
      meta.insertBefore(badge, published || null);
    });
  }
  new MutationObserver(decorate).observe(grid, { childList:true });
  decorate();
})();