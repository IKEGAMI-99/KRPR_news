(() => {
  function cleanLabel(source) {
    const raw = String(source?.label || source?.platform || '元記事').trim();
    if (raw === '公式サイト') return raw;
    return raw.replace(/^(公式|官方)/, '').replace(/\s*·\s*(記事|動態)$/, '').trim() || '元記事';
  }

  function safeUrl(value) {
    try {
      const url = new URL(String(value || ''), location.href);
      return /^https?:$/.test(url.protocol) ? url.href : '';
    } catch {
      return '';
    }
  }

  function sourcesFor(item) {
    const values = Array.isArray(item?.sources) ? item.sources : [];
    const rows = values.length ? values : [{ platform: item?.platform, url: item?.sourceUrl }];
    const seen = new Set();
    return rows.map((source) => ({
      label: cleanLabel(source),
      url: safeUrl(source?.url || source?.sourceUrl),
    })).filter((source) => {
      if (!source.url || seen.has(source.url)) return false;
      seen.add(source.url);
      return true;
    });
  }

  function renderSourceButtons() {
    if (typeof state === 'undefined' || !Array.isArray(state.items)) return;
    const byId = new Map(state.items.map((item) => [String(item?.id || ''), item]));
    document.querySelectorAll('.news-card[data-article-id]').forEach((card) => {
      const item = byId.get(card.dataset.articleId || '');
      if (!item) return;
      const actions = card.querySelector('.card-actions');
      const original = actions?.querySelector('.source-button:not([data-source-extra="true"])') || actions?.querySelector('.source-button');
      if (!actions || !original) return;

      actions.querySelectorAll('.source-button-extra, [data-source-extra="true"]').forEach((node) => node.remove());
      original.classList.remove('source-button-extra');
      original.removeAttribute('data-source-extra');

      const sources = sourcesFor(item);
      if (!sources.length) {
        original.hidden = true;
        return;
      }

      const setButton = (button, source) => {
        button.hidden = false;
        button.href = source.url;
        button.textContent = `${source.label}で開く ↗`;
        button.setAttribute('aria-label', `${source.label}の元記事を開く`);
      };

      setButton(original, sources[0]);
      for (const source of sources.slice(1)) {
        const button = document.createElement('a');
        button.className = 'source-button';
        button.dataset.sourceExtra = 'true';
        button.target = '_blank';
        button.rel = 'noopener noreferrer';
        setButton(button, source);
        actions.appendChild(button);
      }
      card.classList.toggle('has-multiple-sources', sources.length > 1);
    });
  }

  document.addEventListener('kirapara:rendered', renderSourceButtons);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderSourceButtons, { once: true });
  } else {
    renderSourceButtons();
  }
})();
