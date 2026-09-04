(() => {
  const wrap = document.querySelector('#monthlyTopWrap');
  const list = document.querySelector('#monthlyTopList');
  const monthLabel = document.querySelector('#monthlyTopMonth');
  if (!wrap || !list || !monthLabel) return;

  const REGION = {
    JAPAN: '🇯🇵 日本',
    CHINA: '🇨🇳 中国',
    KOREA: '🇰🇷 韓国',
    GLOBAL: '🌐 Global',
  };
  const RANKS = ['🥇', '🥈', '🥉'];
  let cachedRows = [];
  let lastLoadedAt = 0;
  let loading = null;
  let refreshTimer = null;

  function supabaseConfig() {
    const raw = globalThis.KIRAPARA_SUPABASE || {};
    const url = String(raw.url || '').trim().replace(/\/+$/, '');
    const key = String(raw.key || raw.anonKey || raw.publishableKey || '').trim();
    return /^https:\/\//.test(url) && key ? { url, key } : null;
  }

  function currentJstMonth() {
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat('en-US', {
        timeZone: 'Asia/Tokyo',
        year: 'numeric',
        month: '2-digit',
      }).formatToParts(new Date())
        .filter((part) => part.type !== 'literal')
        .map((part) => [part.type, part.value])
    );
    const year = parts.year;
    const month = parts.month;
    return {
      key: `${year}-${month}-01`,
      label: `${Number(year)}年${Number(month)}月`,
    };
  }

  function safeImageUrls(item) {
    try {
      if (typeof imageList === 'function') return imageList(item);
    } catch {}
    const values = [
      ...(Array.isArray(item?.imageUrls) ? item.imageUrls : []),
      ...(item?.imageUrl ? [item.imageUrl] : []),
    ];
    return [...new Set(values.filter((url) => /^https?:\/\//.test(String(url || ''))))];
  }

  function currentItems() {
    try {
      if (typeof state !== 'undefined' && Array.isArray(state.items)) return state.items;
    } catch {}
    return [];
  }

  async function fetchMonthlyRows() {
    const config = supabaseConfig();
    if (!config) return [];
    const month = currentJstMonth();
    const params = new URLSearchParams({
      select: 'article_id,stamp_count',
      month_key: `eq.${month.key}`,
      order: 'stamp_count.desc,article_id.asc',
      limit: '12',
    });
    const response = await fetch(`${config.url}/rest/v1/article_reaction_monthly_counts?${params}`, {
      cache: 'no-store',
      headers: { apikey: config.key },
    });
    if (!response.ok) throw new Error(`monthly top HTTP ${response.status}`);
    const data = await response.json();
    return Array.isArray(data) ? data : [];
  }

  function createImage(item, title) {
    const imageWrap = document.createElement('div');
    imageWrap.className = 'monthly-top-image-wrap';
    const fallback = document.createElement('span');
    fallback.className = 'monthly-top-image-fallback';
    fallback.textContent = '✦';
    fallback.setAttribute('aria-hidden', 'true');
    imageWrap.appendChild(fallback);

    const urls = safeImageUrls(item);
    if (!urls.length) return imageWrap;

    const image = document.createElement('img');
    image.className = 'monthly-top-image';
    image.alt = `${title} の画像`;
    image.loading = 'lazy';
    image.decoding = 'async';
    image.referrerPolicy = 'no-referrer';
    let index = 0;
    const next = () => {
      if (index >= urls.length) {
        image.remove();
        return;
      }
      image.src = urls[index++];
    };
    image.addEventListener('error', next);
    image.addEventListener('load', () => fallback.remove(), { once: true });
    imageWrap.appendChild(image);
    next();
    return imageWrap;
  }

  function createCard(entry, rank) {
    const item = entry.item;
    const articleId = String(entry.article_id || '');
    const title = item.titleJa || item.title || 'タイトルなし';
    const card = document.createElement('a');
    card.className = 'monthly-top-card';
    card.href = `./articles/${encodeURIComponent(articleId)}.html`;
    card.setAttribute('aria-label', `${rank + 1}位 ${title}、スタンプ${entry.stamp_count}件`);

    const imageWrap = createImage(item, title);
    const rankBadge = document.createElement('span');
    rankBadge.className = 'monthly-top-rank';
    rankBadge.textContent = RANKS[rank] || `#${rank + 1}`;
    rankBadge.setAttribute('aria-hidden', 'true');
    imageWrap.appendChild(rankBadge);

    const copy = document.createElement('div');
    copy.className = 'monthly-top-copy';
    const meta = document.createElement('div');
    meta.className = 'monthly-top-meta';
    meta.textContent = [REGION[item.region] || item.region, item.platform || '公式'].filter(Boolean).join(' · ');
    const heading = document.createElement('h3');
    heading.className = 'monthly-top-card-title';
    heading.textContent = title;
    const stamps = document.createElement('div');
    stamps.className = 'monthly-top-stamps';
    stamps.append('✦ スタンプ ');
    const count = document.createElement('strong');
    count.textContent = String(Math.max(0, Number(entry.stamp_count) || 0));
    stamps.appendChild(count);
    copy.append(meta, heading, stamps);
    card.append(imageWrap, copy);
    return card;
  }

  function render() {
    const items = currentItems();
    if (!items.length || !cachedRows.length) {
      wrap.hidden = true;
      return;
    }
    const byId = new Map(items.map((item) => [String(item?.id || ''), item]));
    const ranked = cachedRows
      .map((row) => ({ ...row, item: byId.get(String(row.article_id || '')) }))
      .filter((row) => row.item && Number(row.stamp_count) > 0)
      .slice(0, 3);
    if (!ranked.length) {
      wrap.hidden = true;
      return;
    }
    list.replaceChildren(...ranked.map(createCard));
    monthLabel.textContent = currentJstMonth().label;
    wrap.hidden = false;
  }

  async function load({ force = false } = {}) {
    if (!supabaseConfig()) {
      wrap.hidden = true;
      return;
    }
    if (!force && Date.now() - lastLoadedAt < 60000 && cachedRows.length) {
      render();
      return;
    }
    if (loading) return loading;
    loading = fetchMonthlyRows()
      .then((rows) => {
        cachedRows = rows;
        lastLoadedAt = Date.now();
        render();
      })
      .catch(() => {
        if (!cachedRows.length) wrap.hidden = true;
      })
      .finally(() => { loading = null; });
    return loading;
  }

  function scheduleRefresh() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => load({ force: true }), 900);
  }

  document.addEventListener('kirapara:rendered', () => load());
  document.addEventListener('click', (event) => {
    if (event.target.closest('.reaction-chip, .reaction-emoji-choice, .reaction-custom-form button[type="submit"]')) {
      scheduleRefresh();
    }
  }, true);
  document.addEventListener('submit', (event) => {
    if (event.target.matches('.reaction-custom-form')) scheduleRefresh();
  }, true);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && Date.now() - lastLoadedAt > 60000) load({ force: true });
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => load(), { once: true });
  } else {
    load();
  }
})();
