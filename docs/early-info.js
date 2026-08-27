(() => {
  const grid = document.querySelector('#newsGrid');
  if (!grid) return;
  const canonical = (value) => { try { return new URL(value, location.href).href; } catch { return ''; } };

  function ensureAdvanceInfoNotice() {
    const section = document.querySelector('#weeklyTopics');
    if (!section || section.querySelector('.early-info-notice')) return;
    const head = section.querySelector('.weekly-topics-head');
    const notice = document.createElement('p');
    notice.className = 'early-info-notice';
    notice.textContent = '※ AIが海外版と日本版の告知を比較して推定した参考情報です。日本版での実装・開催を保証するものではありません。';
    if (head) head.insertAdjacentElement('afterend', notice);
    else section.prepend(notice);
  }

  function decorate() {
    ensureAdvanceInfoNotice();
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
      const reason = item.earlyInfoReason || '海外版で先に告知され、日本版に同内容の告知がまだ見つかっていない可能性があります';
      badge.title = `AIによる推定情報です。日本版での実装・開催を保証するものではありません。${reason ? ` ${reason}` : ''}`;
      badge.setAttribute('aria-label', '先行情報。AIによる推定で、日本版での実装・開催を保証するものではありません');
      meta.insertBefore(badge, published || null);
    });
  }
  new MutationObserver(decorate).observe(grid, { childList:true });
  decorate();
})();