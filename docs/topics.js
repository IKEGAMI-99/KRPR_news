(() => {
  const section = document.querySelector('#weeklyTopics');
  const list = document.querySelector('#weeklyTopicsList');
  const grid = document.querySelector('#newsGrid');
  if (!section || !list || !grid) return;

  const regionLabel = { JAPAN:'日本', CHINA:'中国', KOREA:'韓国', GLOBAL:'Global' };

  function resetHorizontalScroll() {
    document.documentElement.scrollLeft = 0;
    document.body.scrollLeft = 0;
    if (window.scrollX !== 0) window.scrollTo(0, window.scrollY);
  }

  function allItems() {
    try {
      return typeof state !== 'undefined' && Array.isArray(state.items) ? state.items : [];
    } catch { return []; }
  }

  function visibleItems() {
    try {
      if (typeof state === 'undefined' || !Array.isArray(state.items)) return [];
      return state.items.filter((item) => state.region === 'ALL' || item.region === state.region);
    } catch { return []; }
  }

  function markCards() {
    const items = visibleItems();
    const cards = [...grid.querySelectorAll('.news-card')];
    cards.forEach((card, index) => {
      const item = items[index];
      if (!item?.id) return;
      card.id = `article-${item.id}`;
      card.dataset.articleId = item.id;
      card.querySelector('.importance-badge')?.remove();
    });
  }

  function advanceItems() {
    return allItems()
      .filter((item) => item?.earlyInfo === true)
      .sort((a, b) => {
        const dateDiff = Number(b?.publishedAtEpoch || 0) - Number(a?.publishedAtEpoch || 0);
        if (dateDiff) return dateDiff;
        return Number(b?.earlyInfoConfidence || 0) - Number(a?.earlyInfoConfidence || 0);
      })
      .slice(0, 3);
  }

  async function goToArticle(id) {
    let target = document.querySelector(`#article-${CSS.escape(id)}`);
    if (!target) {
      const all = document.querySelector('.region-tab[data-region="ALL"]');
      if (all && !all.classList.contains('is-active')) all.click();
      await new Promise((resolve) => setTimeout(resolve, 80));
      markCards();
      target = document.querySelector(`#article-${CSS.escape(id)}`);
    }
    if (!target) return;
    target.scrollIntoView({ behavior:'smooth', block:'center', inline:'nearest' });
    resetHorizontalScroll();
    target.classList.remove('topic-target');
    void target.offsetWidth;
    target.classList.add('topic-target');
    setTimeout(() => target.classList.remove('topic-target'), 1800);
  }

  function render() {
    const topics = advanceItems();
    if (!topics.length) {
      list.innerHTML = '<div class="weekly-topic-empty">現在、表示できる先行情報はありません</div>';
      resetHorizontalScroll();
      return;
    }

    list.replaceChildren();
    topics.forEach((item, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'weekly-topic';

      const rank = document.createElement('span');
      rank.className = 'weekly-topic-rank';
      rank.textContent = String(index + 1);

      const copy = document.createElement('span');
      copy.className = 'weekly-topic-copy';
      const title = document.createElement('strong');
      title.textContent = String(item.titleJa || item.title || '先行情報');
      const meta = document.createElement('small');
      const source = String(item.platform || '海外公式');
      meta.textContent = `${regionLabel[item.region] || item.region || '海外'} · ${source}`;
      copy.append(title, meta);

      const arrow = document.createElement('span');
      arrow.className = 'weekly-topic-arrow';
      arrow.textContent = '↓';

      button.append(rank, copy, arrow);
      button.addEventListener('click', () => goToArticle(String(item.id || '')));
      list.appendChild(button);
    });
    resetHorizontalScroll();
  }

  function refresh() {
    markCards();
    render();
  }

  new MutationObserver(refresh).observe(grid, { childList:true });
  document.querySelector('#regionTabs')?.addEventListener('click', () => setTimeout(refresh, 0));
  window.addEventListener('pageshow', () => setTimeout(resetHorizontalScroll, 0));
  window.addEventListener('resize', () => setTimeout(resetHorizontalScroll, 0));
  resetHorizontalScroll();
  setTimeout(resetHorizontalScroll, 60);
  refresh();
})();
