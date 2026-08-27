(() => {
  const DATA_URL = 'https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/data/gap_analysis.json';
  const THEME_KEY = 'kirapara-news-theme';
  const REGION = {
    CHINA: { label:'中国', flag:'🇨🇳' },
    GLOBAL: { label:'Global', flag:'🌐' },
    KOREA: { label:'韓国', flag:'🇰🇷' },
    JAPAN: { label:'日本', flag:'🇯🇵' },
  };
  const CATEGORY = {
    ALL:'すべて', GACHA:'ガチャ', OUTFIT:'衣装', EVENT:'イベント', UPDATE:'アップデート', FEATURE:'新機能', OTHER:'その他'
  };

  const els = {
    status: document.querySelector('#gapStatus'),
    stats: document.querySelector('#gapStats'),
    forecasts: document.querySelector('#gapForecasts'),
    matches: document.querySelector('#gapMatches'),
    filters: document.querySelector('#gapFilters'),
    theme: document.querySelector('#gapThemeButton'),
  };

  let payload = null;
  let selectedCategory = 'ALL';

  function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(THEME_KEY, theme); } catch {}
    if (els.theme) els.theme.textContent = theme === 'light' ? '☀' : '☾';
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'light' ? '#fff7fc' : '#120913');
  }

  function initTheme() {
    let saved = null;
    try { saved = localStorage.getItem(THEME_KEY); } catch {}
    const preferred = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    setTheme(saved === 'light' || saved === 'dark' ? saved : preferred);
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function formatDate(value) {
    if (!value) return '不明';
    try {
      return new Intl.DateTimeFormat('ja-JP', { year:'numeric', month:'numeric', day:'numeric', timeZone:'Asia/Tokyo' })
        .format(new Date(`${value}T00:00:00Z`));
    } catch { return String(value); }
  }

  function formatGenerated(value) {
    if (!value) return '未生成';
    try {
      return new Intl.DateTimeFormat('ja-JP', {
        month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit', timeZone:'Asia/Tokyo'
      }).format(new Date(value));
    } catch { return String(value); }
  }

  function formatGap(days) {
    const value = Number(days);
    if (!Number.isFinite(value)) return '—';
    const d = Math.round(value);
    if (d === 0) return '同日';
    if (d > 0) return `${d}日後`;
    return `日本が${Math.abs(d)}日先行`;
  }

  function renderStats() {
    const stats = payload?.stats || {};
    els.stats.innerHTML = ['CHINA','GLOBAL','KOREA'].map((region) => {
      const s = stats[region] || {};
      const meta = REGION[region];
      if (!Number(s.n) || !Number.isFinite(Number(s.median))) {
        return `<article class="gap-stat-card is-empty"><div class="gap-stat-top"><span class="gap-stat-route">${meta.flag} ${meta.label} → 🇯🇵 日本</span><span class="gap-stat-samples">0件</span></div><div class="gap-stat-value">データ不足</div><div class="gap-stat-meta">一致する実装記事が増えると翌日の分析で更新されます</div></article>`;
      }
      const median = Number(s.median);
      const average = Number(s.average);
      const spread = Number(s.mad);
      return `<article class="gap-stat-card"><div class="gap-stat-top"><span class="gap-stat-route">${meta.flag} ${meta.label} → 🇯🇵 日本</span><span class="gap-stat-samples">${Number(s.n)}件</span></div><div class="gap-stat-value">${escapeHtml(formatGap(median).replace('後',''))}<small>${median > 0 ? '遅れ中央値' : '中央値'}</small></div><div class="gap-stat-meta">平均 ${escapeHtml(formatGap(average))}${Number.isFinite(spread) ? ` · ばらつき ±${Math.max(1,Math.round(spread))}日` : ''}</div></article>`;
    }).join('');
  }

  function renderFilters() {
    const forecasts = Array.isArray(payload?.forecasts) ? payload.forecasts : [];
    const available = new Set(forecasts.map((item) => item.category));
    const keys = ['ALL','GACHA','OUTFIT','EVENT','UPDATE','FEATURE','OTHER'].filter((key) => key === 'ALL' || available.has(key));
    els.filters.replaceChildren();
    for (const key of keys) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `gap-filter${selectedCategory === key ? ' is-active' : ''}`;
      button.textContent = CATEGORY[key];
      button.addEventListener('click', () => {
        selectedCategory = key;
        renderFilters();
        renderForecasts();
      });
      els.filters.appendChild(button);
    }
  }

  function renderForecasts() {
    let forecasts = Array.isArray(payload?.forecasts) ? payload.forecasts.slice() : [];
    if (selectedCategory !== 'ALL') forecasts = forecasts.filter((item) => item.category === selectedCategory);
    forecasts = forecasts.slice(0, 18);

    if (!forecasts.length) {
      els.forecasts.innerHTML = '<div class="gap-empty">このカテゴリには現在、予測対象の先行情報がありません。</div>';
      return;
    }

    els.forecasts.innerHTML = forecasts.map((item) => {
      const region = REGION[item.region] || { flag:'🌐', label:item.region || '海外' };
      const title = escapeHtml(item.title || '先行情報');
      const href = escapeHtml(item.sourceUrl || '#');
      const category = escapeHtml(item.categoryLabel || CATEGORY[item.category] || CATEGORY.OTHER);
      const sourceDate = escapeHtml(formatDate(item.sourceDate));
      const sourceBasis = escapeHtml(item.sourceBasis || '不明');
      const prediction = item.prediction;

      if (!prediction?.date) {
        return `<article class="gap-forecast"><div class="gap-forecast-head"><div class="gap-forecast-title"><a class="gap-source-link" href="${href}" target="_blank" rel="noopener noreferrer"><strong>${title}</strong></a><small>${region.flag} ${escapeHtml(region.label)} · ${sourceBasis}</small></div><span class="gap-category">${category}</span></div><div class="gap-forecast-note">日本版予測: まだ比較サンプルが足りません。</div></article>`;
      }

      return `<article class="gap-forecast"><div class="gap-forecast-head"><div class="gap-forecast-title"><a class="gap-source-link" href="${href}" target="_blank" rel="noopener noreferrer"><strong>${title}</strong></a><small>${region.flag} ${escapeHtml(region.label)} · ${sourceBasis}</small></div><span class="gap-category">${category}</span></div><div class="gap-forecast-grid"><div class="gap-date-box"><span>${region.flag} ${escapeHtml(region.label)}</span><strong>${sourceDate}</strong></div><div class="gap-date-arrow">→</div><div class="gap-date-box"><span>🇯🇵 日本版予想</span><strong>${escapeHtml(formatDate(prediction.date))}</strong></div></div><div class="gap-forecast-note">予想範囲 ${escapeHtml(formatDate(prediction.rangeStart))}〜${escapeHtml(formatDate(prediction.rangeEnd))} · ${escapeHtml(prediction.modelSource || '統計')} ${Number(prediction.samples || 0)}件から推定<span class="gap-confidence">確度 ${escapeHtml(prediction.confidence || '低め')}</span></div></article>`;
    }).join('');
  }

  function renderMatches() {
    const matches = Array.isArray(payload?.matches) ? payload.matches.slice(0, 36) : [];
    if (!matches.length) {
      els.matches.innerHTML = '<div class="gap-empty">高一致と判断できるコンテンツがまだありません。ニュース履歴と翻訳が増えるほど比較精度が上がります。</div>';
      return;
    }

    els.matches.innerHTML = matches.map((item) => {
      const region = REGION[item.sourceRegion] || { flag:'🌐', label:item.sourceRegion || '海外' };
      const srcHref = escapeHtml(item.sourceUrl || '#');
      const jpHref = escapeHtml(item.jpUrl || '#');
      return `<article class="gap-match"><div class="gap-match-head"><div class="gap-match-title"><strong>${escapeHtml(item.title || '名称不明')}</strong><small>${region.flag} ${escapeHtml(region.label)} → 🇯🇵 日本</small></div><span class="gap-category">${escapeHtml(item.categoryLabel || CATEGORY[item.category] || CATEGORY.OTHER)}</span></div><div class="gap-match-timeline"><a class="gap-date-box gap-source-link" href="${srcHref}" target="_blank" rel="noopener noreferrer"><span>${region.flag} ${escapeHtml(region.label)} · ${escapeHtml(item.sourceBasis || '不明')}</span><strong>${escapeHtml(formatDate(item.sourceDate))}</strong></a><div class="gap-match-gap">${escapeHtml(formatGap(item.gapDays))}</div><a class="gap-date-box gap-source-link" href="${jpHref}" target="_blank" rel="noopener noreferrer"><span>🇯🇵 日本 · ${escapeHtml(item.jpBasis || '不明')}</span><strong>${escapeHtml(formatDate(item.jpDate))}</strong></a></div><div class="gap-match-score">自動照合一致度 ${Math.round(Number(item.score || 0) * 100)}%</div></article>`;
    }).join('');
  }

  async function load() {
    try {
      const response = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache:'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('データ形式エラー');
      payload = data;
      renderStats();
      renderFilters();
      renderForecasts();
      renderMatches();
      els.status.textContent = `${Number(payload.sourceCount || 0)}件を分析 · 一致 ${Number(payload.matchedCount || 0)}組 · 先行情報 ${Number(payload.earlyCount || 0)}件 · ${formatGenerated(payload.generatedAt)}更新`;
    } catch (error) {
      els.status.textContent = `分析データを取得できませんでした (${error.message})`;
      els.stats.innerHTML = '<div class="gap-empty">次回の日次分析が完了すると表示されます。</div>';
      els.forecasts.innerHTML = '';
      els.matches.innerHTML = '';
    }
  }

  els.theme?.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'));
  initTheme();
  load();
})();
