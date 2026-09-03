(() => {
  const panel = document.querySelector('#gameNoticePanel');
  const list = document.querySelector('#gameNoticeList');
  const count = document.querySelector('#gameNoticeCount');
  const status = document.querySelector('#gameNoticeStatus');
  if (!panel || !list || !count || !status) return;

  const IS_LOCAL_PREVIEW = ['localhost', '127.0.0.1'].includes(location.hostname);
  const DATA_URL = IS_LOCAL_PREVIEW
    ? '../data/news.json'
    : 'https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/data/news.json';
  const MAX_ITEMS = 8;
  const NOTICE_URL_RE = /^https:\/\/cms\.archosaur\.com\/jeecms\/smhwjp(?:news|event)\/\d+\.jhtml(?:[?#].*)?$/i;

  function safeHttpUrl(value) {
    try {
      const url = new URL(String(value || ''), location.href);
      return /^https?:$/.test(url.protocol) ? url.href : '';
    } catch {
      return '';
    }
  }

  function noticeType(url) {
    return /\/smhwjpevent\//i.test(url) ? 'イベント' : 'お知らせ';
  }

  function formatDate(epoch, fallback = '') {
    const seconds = Number(epoch);
    if (!Number.isFinite(seconds) || seconds <= 0) return fallback;
    try {
      return new Intl.DateTimeFormat('ja-JP', {
        timeZone: 'Asia/Tokyo',
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
      }).format(new Date(seconds * 1000));
    } catch {
      return fallback;
    }
  }

  function normalizedNotices(items) {
    const seen = new Set();
    return items
      .filter((item) => item && typeof item === 'object' && item.region === 'JAPAN')
      .map((item) => ({ ...item, sourceUrl: safeHttpUrl(item.sourceUrl) }))
      .filter((item) => item.sourceUrl && NOTICE_URL_RE.test(item.sourceUrl))
      .filter((item) => {
        if (seen.has(item.sourceUrl)) return false;
        seen.add(item.sourceUrl);
        return true;
      })
      .sort((a, b) => (Number(b.publishedAtEpoch) || 0) - (Number(a.publishedAtEpoch) || 0))
      .slice(0, MAX_ITEMS);
  }

  function createNotice(item) {
    const link = document.createElement('a');
    link.className = 'game-notice-item';
    link.href = item.sourceUrl;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';

    const meta = document.createElement('div');
    meta.className = 'game-notice-meta';

    const type = document.createElement('span');
    type.className = 'game-notice-type';
    type.textContent = noticeType(item.sourceUrl);

    const date = document.createElement('time');
    date.className = 'game-notice-date';
    date.textContent = formatDate(item.publishedAtEpoch, item.publishedLabel || '');
    const epoch = Number(item.publishedAtEpoch);
    if (Number.isFinite(epoch) && epoch > 0) date.dateTime = new Date(epoch * 1000).toISOString();
    meta.append(type, date);

    const title = document.createElement('strong');
    title.className = 'game-notice-title';
    title.textContent = item.titleJa || item.title || '公式お知らせ';

    const bodyText = item.summaryJa || item.bodyJa || item.body || '';
    if (bodyText) {
      const body = document.createElement('p');
      body.className = 'game-notice-body';
      body.textContent = bodyText;
      link.append(meta, title, body);
    } else {
      link.append(meta, title);
    }

    const arrow = document.createElement('span');
    arrow.className = 'game-notice-link-arrow';
    arrow.setAttribute('aria-hidden', 'true');
    arrow.textContent = '↗';
    link.appendChild(arrow);
    return link;
  }

  function render(items) {
    const notices = normalizedNotices(items);
    list.replaceChildren();
    count.textContent = String(notices.length);

    if (!notices.length) {
      status.textContent = '現在表示できるお知らせはありません';
      const empty = document.createElement('p');
      empty.className = 'game-notice-empty';
      empty.textContent = '公式のお知らせを取得できませんでした。次回更新時に再取得します。';
      list.appendChild(empty);
      panel.hidden = false;
      return;
    }

    status.textContent = `最新${notices.length}件`;
    const fragment = document.createDocumentFragment();
    notices.forEach((item) => fragment.appendChild(createNotice(item)));
    list.appendChild(fragment);
    panel.hidden = false;
  }

  async function load({ force = false } = {}) {
    status.textContent = '取得中…';
    try {
      const suffix = force ? `?t=${Date.now()}` : '?game-notices=1';
      const response = await fetch(`${DATA_URL}${suffix}`, { cache: force ? 'no-store' : 'no-cache' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const json = await response.json();
      if (!Array.isArray(json)) throw new Error('invalid data');
      render(json);
    } catch (error) {
      count.textContent = '0';
      status.textContent = '取得失敗';
      list.replaceChildren();
      const empty = document.createElement('p');
      empty.className = 'game-notice-empty';
      empty.textContent = 'ゲーム内お知らせを取得できませんでした。';
      list.appendChild(empty);
      panel.hidden = false;
      console.warn('game notices load failed', error);
    }
  }

  document.querySelector('#refreshButton')?.addEventListener('click', () => load({ force: true }));
  document.querySelector('#retryButton')?.addEventListener('click', () => load({ force: true }));
  load();
})();
