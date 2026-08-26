(() => {
  const grid = document.querySelector('#newsGrid');
  const tabs = document.querySelector('#regionTabs');
  if (!grid || !tabs) return;

  const active = { source: 'ALL', image: false, ai: false, early: false };

  function canonicalUrl(value) {
    try { return new URL(value, location.href).href; } catch { return ''; }
  }

  function itemForCard(card) {
    const sourceUrl = canonicalUrl(card.querySelector('.source-button')?.href);
    try {
      if (typeof state === 'undefined' || !Array.isArray(state.items)) return null;
      return state.items.find((item) => canonicalUrl(item?.sourceUrl) === sourceUrl) || null;
    } catch {
      return null;
    }
  }

  function sourceType(item) {
    const platform = String(item?.platform || '').toLowerCase();
    if (/(公式x|twitter|weibo|bilibili|youtube|tiktok|instagram|wechat)/i.test(platform)) return 'SOCIAL';
    if (/(webニュース|ニュースワイヤー|メディア|プレスリリース|4gamer|gamewith|gamer|inside|ign|kotaku|qooapp|인벤|게임메카)/i.test(platform)) return 'MEDIA';
    return 'OFFICIAL';
  }

  function hasImage(item) {
    return Boolean(item?.imageUrl || (Array.isArray(item?.imageUrls) && item.imageUrls.length));
  }

  function matches(item) {
    if (!item) return false;
    if (active.source !== 'ALL' && sourceType(item) !== active.source) return false;
    if (active.image && !hasImage(item)) return false;
    if (active.ai && !item.aiProcessed) return false;
    if (active.early && !item.earlyInfo) return false;
    return true;
  }

  function addEarlyBadge(card, item) {
    const old = card.querySelector('.early-info-badge');
    if (!item?.earlyInfo) {
      old?.remove();
      return;
    }
    if (old) return;
    const meta = card.querySelector('.card-meta');
    const published = card.querySelector('.published');
    if (!meta) return;
    const badge = document.createElement('span');
    badge.className = 'early-info-badge';
    badge.textContent = '✦ 先行情報';
    badge.title = item.earlyInfoReason || '海外版で先に告知され、日本版に同内容の告知がまだ見つかっていない可能性があります';
    meta.insertBefore(badge, published || null);
  }

  function applyFilters() {
    let visible = 0;
    grid.querySelectorAll(':scope > .news-card').forEach((card) => {
      const item = itemForCard(card);
      addEarlyBadge(card, item);
      const show = matches(item);
      card.hidden = !show;
      if (show) visible += 1;
    });

    const count = document.querySelector('#visibleCount');
    if (count) count.textContent = `${visible}件`;
    const empty = document.querySelector('#emptyState');
    if (empty && typeof state !== 'undefined' && Array.isArray(state.items)) {
      empty.hidden = visible !== 0 || state.items.length === 0;
    }
    window.dispatchEvent(new CustomEvent('kirapara:filters-changed'));
  }

  const bar = document.createElement('div');
  bar.className = 'filter-bar';
  bar.setAttribute('aria-label', 'ニュース絞り込み');
  bar.innerHTML = `
    <label class="filter-source">
      <span aria-hidden="true">✦</span>
      <select aria-label="情報源で絞り込み">
        <option value="ALL">すべての情報源</option>
        <option value="OFFICIAL">公式サイト</option>
        <option value="SOCIAL">SNS</option>
        <option value="MEDIA">メディア</option>
      </select>
    </label>
    <button class="filter-chip" type="button" data-filter="image" aria-pressed="false">🖼 画像あり</button>
    <button class="filter-chip" type="button" data-filter="ai" aria-pressed="false">✦ AI済み</button>
    <button class="filter-chip early-filter" type="button" data-filter="early" aria-pressed="false">⚡ 先行情報</button>`;
  tabs.insertAdjacentElement('afterend', bar);

  const select = bar.querySelector('select');
  select.addEventListener('change', () => {
    active.source = select.value;
    applyFilters();
  });

  bar.addEventListener('click', (event) => {
    const button = event.target.closest('[data-filter]');
    if (!button) return;
    const key = button.dataset.filter;
    active[key] = !active[key];
    button.classList.toggle('is-active', active[key]);
    button.setAttribute('aria-pressed', String(active[key]));
    applyFilters();
  });

  let queued = false;
  const observer = new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      applyFilters();
    });
  });
  observer.observe(grid, { childList: true });
  applyFilters();
})();
