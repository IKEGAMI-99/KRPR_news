(() => {
  const BATCH_SIZE = 3;
  const RUN_INTERVAL_MINUTES = 15;
  const RUN_MINUTES_UTC = [7, 22, 37, 52];
  const QUEUE_REFRESH_MS = 60 * 1000;
  const IS_LOCAL = ['localhost', '127.0.0.1'].includes(location.hostname);
  const NEWS_URL = IS_LOCAL
    ? '../data/news.json'
    : 'https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/data/news.json';

  let queueItems = [];
  let queueFetchedAt = 0;
  let latestRenderedItems = [];

  function text(value) {
    return typeof value === 'string' ? value.trim() : '';
  }

  function articleKey(item) {
    return text(item?.id) || text(item?.sourceUrl);
  }

  function hasJapaneseTranslation(item) {
    if (!item || item.region === 'JAPAN') return true;
    const originalTitle = text(item.title);
    const originalBody = text(item.body) || originalTitle;
    const translatedTitle = text(item.titleJa);
    const translatedBody = text(item.bodyJa);
    if (!translatedTitle && !translatedBody) return false;
    if (item.aiProcessed && text(item.summaryJa)) return true;
    return Boolean(
      (translatedTitle && translatedTitle !== originalTitle) ||
      (translatedBody && translatedBody !== originalBody)
    );
  }

  function needsAiWork(item) {
    return Boolean(item && !(item.aiProcessed && text(item.summaryJa)));
  }

  function minutesUntilNextScheduledRun(now = new Date()) {
    const current = now.getUTCMinutes() + now.getUTCSeconds() / 60;
    for (const minute of RUN_MINUTES_UTC) {
      if (minute > current) return Math.max(1, Math.ceil(minute - current));
    }
    return Math.max(1, Math.ceil(60 - current + RUN_MINUTES_UTC[0]));
  }

  function estimateMinutes(queueIndex) {
    if (!Number.isInteger(queueIndex) || queueIndex < 0) return null;
    const batchIndex = Math.floor(queueIndex / BATCH_SIZE);
    return minutesUntilNextScheduledRun() + batchIndex * RUN_INTERVAL_MINUTES;
  }

  function formatEta(minutes) {
    if (!Number.isFinite(minutes) || minutes <= 0) return '';
    if (minutes <= 5) return '約5分';
    if (minutes < 60) return `約${Math.ceil(minutes / 15) * 15}分`;
    const rounded = Math.ceil(minutes / 15) * 15;
    const hours = Math.floor(rounded / 60);
    const rest = rounded % 60;
    return rest ? `約${hours}時間${rest}分` : `約${hours}時間`;
  }

  function buildQueueIndex() {
    const pending = queueItems.filter(needsAiWork);
    const positions = new Map();
    pending.forEach((item, index) => {
      const key = articleKey(item);
      if (key) positions.set(key, index);
    });
    return positions;
  }

  function decorate() {
    if (!latestRenderedItems.length) return;
    const positions = buildQueueIndex();
    const byKey = new Map(latestRenderedItems.map((item) => [articleKey(item), item]));

    document.querySelectorAll('#newsGrid .news-card').forEach((card) => {
      card.querySelector('.translation-wait-badge')?.remove();
      const key = card.dataset.articleId || card.dataset.sourceUrl || '';
      const item = byKey.get(key) || latestRenderedItems.find((row) => articleKey(row) === key);
      if (!item || hasJapaneseTranslation(item) || item.region === 'JAPAN') return;

      const platform = card.querySelector('.platform');
      if (!platform) return;
      const badge = document.createElement('span');
      badge.className = 'translation-wait-badge';
      const position = positions.get(articleKey(item));
      const eta = formatEta(estimateMinutes(position));
      badge.textContent = eta ? `翻訳待ち · 目安 ${eta}` : '翻訳待ち';
      badge.title = 'Gemma翻訳キューの現在位置と、最大3件・15分間隔の定期処理から算出した概算です。失敗や再試行で遅れる場合があります。';
      badge.setAttribute('aria-label', badge.textContent);
      platform.insertAdjacentElement('afterend', badge);
    });
  }

  async function refreshQueue() {
    try {
      const response = await fetch(`${NEWS_URL}${NEWS_URL.includes('?') ? '&' : '?'}translationWait=${Date.now()}`, {
        cache: 'no-store',
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const json = await response.json();
      if (!Array.isArray(json)) throw new Error('invalid news payload');
      queueItems = json
        .filter((item) => item && typeof item === 'object')
        .sort((a, b) => (Number(b.publishedAtEpoch) || 0) - (Number(a.publishedAtEpoch) || 0));
      queueFetchedAt = Date.now();
      decorate();
    } catch {
      if (!queueItems.length) queueItems = latestRenderedItems.slice();
      decorate();
    }
  }

  document.addEventListener('kirapara:rendered', (event) => {
    latestRenderedItems = Array.isArray(event.detail?.items) ? event.detail.items : [];
    decorate();
    if (!queueItems.length || Date.now() - queueFetchedAt >= QUEUE_REFRESH_MS) refreshQueue();
  });
})();
