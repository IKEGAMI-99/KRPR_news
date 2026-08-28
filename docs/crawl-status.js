(() => {
  const IS_LOCAL_PREVIEW = ['localhost', '127.0.0.1'].includes(location.hostname);
  const STATUS_URL = IS_LOCAL_PREVIEW
    ? '../data/crawl_status.json'
    : 'https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/data/crawl_status.json';
  const CACHE_KEY = 'kirapara-crawl-status-v1';
  const status = document.querySelector('#statusText');
  const formatter = new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });

  if (!status) return;

  function parseStatus(value) {
    const raw = value && typeof value === 'object' ? value.lastCrawlAt : '';
    const date = new Date(raw);
    return raw && Number.isFinite(date.getTime()) ? { lastCrawlAt: raw } : null;
  }

  function readCached() {
    try { return parseStatus(JSON.parse(localStorage.getItem(CACHE_KEY) || 'null')); }
    catch { return null; }
  }

  function writeCached(value) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(value)); }
    catch { /* Storage may be unavailable in private browsing. */ }
  }

  function apply(value) {
    const parsed = parseStatus(value);
    if (!parsed) return false;
    status.textContent = `最終更新 ${formatter.format(new Date(parsed.lastCrawlAt))}`;
    return true;
  }

  function showLoading() {
    status.textContent = '最終更新 取得中…';
  }

  let current = readCached();
  if (current) apply(current);
  else showLoading();

  async function load({ force = false } = {}) {
    try {
      const suffix = force ? `?t=${Date.now()}` : '?v=1';
      const response = await fetch(`${STATUS_URL}${suffix}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const parsed = parseStatus(await response.json());
      if (!parsed) throw new Error('invalid crawl status');
      current = parsed;
      writeCached(parsed);
      apply(parsed);
    } catch {
      if (current) apply(current);
      else status.textContent = '最終更新 不明';
    }
  }

  document.addEventListener('kirapara:rendered', () => {
    if (current) apply(current);
    else {
      showLoading();
      load();
    }
  });

  document.querySelector('#refreshButton')?.addEventListener('click', () => load({ force: true }));
  document.querySelector('#retryButton')?.addEventListener('click', () => load({ force: true }));

  load();
})();
