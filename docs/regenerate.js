(() => {
  const grid = document.querySelector('#newsGrid');
  if (!grid) return;

  const ISSUE_URL = 'https://github.com/IKEGAMI-99/KRPR_news/issues/new';

  function canonicalUrl(value) {
    try { return new URL(value, location.href).href; } catch { return ''; }
  }

  function findItem(card) {
    const sourceUrl = canonicalUrl(card.querySelector('.source-button')?.href);
    try {
      if (typeof state === 'undefined' || !Array.isArray(state.items)) return null;
      return state.items.find((item) => canonicalUrl(item?.sourceUrl) === sourceUrl) || null;
    } catch { return null; }
  }

  function attach(card) {
    if (card.querySelector('.regenerate-button')) return;
    const item = findItem(card);
    const actions = card.querySelector('.card-actions');
    const source = card.querySelector('.source-button');
    if (!item || !actions || !source || !item.aiProcessed || !item.id) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'regenerate-button';
    button.textContent = item.region === 'JAPAN' ? '↻ 再要約' : '↻ 再翻訳・要約';
    button.title = '現在のAI結果を破棄して、GitHub Actionsで再生成を依頼します';
    button.addEventListener('click', () => {
      const title = `[AI再生成] ${item.id}`;
      const body = [
        `articleId: ${item.id}`,
        `sourceUrl: ${item.sourceUrl || ''}`,
        `region: ${item.region || ''}`,
        '',
        'Kirapara News PWAからの再生成依頼です。',
      ].join('\n');
      const url = `${ISSUE_URL}?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
      window.open(url, '_blank', 'noopener,noreferrer');
    });
    actions.insertBefore(button, source);
  }

  function attachAll() {
    grid.querySelectorAll('.news-card').forEach(attach);
  }

  new MutationObserver(attachAll).observe(grid, { childList: true, subtree: false });
  attachAll();
})();
