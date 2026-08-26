(() => {
  const section = document.querySelector('#weeklyTopics');
  const list = document.querySelector('#weeklyTopicsList');
  const grid = document.querySelector('#newsGrid');
  if (!section || !list || !grid) return;

  const TOPICS_URL = 'https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/data/weekly_topics.json';
  const regionLabel = { JAPAN:'日本', CHINA:'中国', KOREA:'韓国', GLOBAL:'Global' };

  function currentItems() {
    try {
      if (typeof state === 'undefined' || !Array.isArray(state.items)) return [];
      return state.items.filter((item) => state.region === 'ALL' || item.region === state.region);
    } catch { return []; }
  }

  function levelClass(score) {
    if (score >= 85) return 'is-hot';
    if (score >= 70) return 'is-high';
    return 'is-normal';
  }

  function markCards() {
    const items = currentItems();
    const cards = [...grid.querySelectorAll('.news-card')];
    cards.forEach((card, index) => {
      const item = items[index];
      if (!item?.id) return;
      card.id = `article-${item.id}`;
      card.dataset.articleId = item.id;

      const meta = card.querySelector('.card-meta');
      if (!meta) return;
      const existing = meta.querySelector('.importance-badge');
      const score = Number(item.importanceScore || 0);
      if (score <= 0) {
        existing?.remove();
        return;
      }
      const badge = existing || document.createElement('span');
      badge.className = `importance-badge ${levelClass(score)}`;
      badge.textContent = `注目 ${score}`;
      badge.title = 'AI選定用の注目度スコア';
      if (!existing) meta.appendChild(badge);
    });
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
    target.scrollIntoView({ behavior:'smooth', block:'center' });
    target.classList.remove('topic-target');
    void target.offsetWidth;
    target.classList.add('topic-target');
    setTimeout(() => target.classList.remove('topic-target'), 1800);
  }

  function render(payload) {
    const topics = Array.isArray(payload?.topics) ? payload.topics.slice(0, 3) : [];
    if (!topics.length) {
      list.innerHTML = '<div class="weekly-topic-empty">AIが今週のトピックを選定中…</div>';
      return;
    }
    list.replaceChildren();
    topics.forEach((topic, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'weekly-topic';
      button.innerHTML = `
        <span class="weekly-topic-rank">${index + 1}</span>
        <span class="weekly-topic-copy">
          <strong>${escapeHtml(topic.title || '注目トピック')}</strong>
          <small>${escapeHtml(regionLabel[topic.region] || topic.region || '')} · 注目度 ${Number(topic.score || 0)}</small>
        </span>
        <span class="weekly-topic-arrow">↓</span>`;
      button.addEventListener('click', () => goToArticle(String(topic.id || '')));
      list.appendChild(button);
    });
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
      '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;'
    })[char]);
  }

  async function loadTopics() {
    try {
      const response = await fetch(`${TOPICS_URL}?t=${Date.now()}`, { cache:'no-store' });
      if (!response.ok) throw new Error(String(response.status));
      render(await response.json());
    } catch {
      render(null);
    }
  }

  new MutationObserver(markCards).observe(grid, { childList:true });
  document.querySelector('#regionTabs')?.addEventListener('click', () => setTimeout(markCards, 0));
  markCards();
  loadTopics();
})();
