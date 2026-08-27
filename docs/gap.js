(() => {
  const DATA_URL = 'https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/data/news.json';
  const THEME_KEY = 'kirapara-news-theme';
  const DAY = 86400000;
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

  let rows = [];
  let matches = [];
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

  function searchable(row) {
    return [row?.titleJa, row?.summaryJa, row?.bodyJa, row?.title, row?.body].filter(Boolean).join(' ');
  }

  function categoryOf(row) {
    const t = searchable(row).toLowerCase();
    if (/(ガチャ|追光|lightchase|招募|召喚|限定ガチャ|祈願)/i.test(t)) return 'GACHA';
    if (/(星\s*[456]|[456]\s*星|★\s*[456]|セット|衣装|コーデ|ファッション|outfit|fashion|套装|时装|의상|코디)/i.test(t)) return 'OUTFIT';
    if (/(大型アップデート|アップデート|update|更新|バージョン|版本|업데이트)/i.test(t)) return 'UPDATE';
    if (/(新機能|機能追加|システム|撮影機能|ホーム機能|feature|function|新功能|系统|기능)/i.test(t)) return 'FEATURE';
    if (/(イベント|event|開催|活動|活动|이벤트)/i.test(t)) return 'EVENT';
    return 'OTHER';
  }

  function normalize(value) {
    return String(value || '')
      .normalize('NFKC')
      .toLowerCase()
      .replace(/https?:\/\/\S+/g, ' ')
      .replace(/#[^\s#]+/g, ' ')
      .replace(/20\d{2}[年./-]\d{1,2}[月./-]\d{1,2}日?/g, ' ')
      .replace(/\d{1,2}月\d{1,2}日/g, ' ')
      .replace(/\d{1,2}:\d{2}/g, ' ')
      .replace(/(きらめきパラダイス|キラパラ|life\s*makeover|以闪亮之名|스타일라잇|公式|official|お知らせ|予告|preview|登場|開催|イベント|event|更新|アップデート|update)/g, ' ')
      .replace(/[^0-9a-zぁ-ゖァ-ヺー一-龯가-힣]+/g, '');
  }

  function gramSet(value, n = 2) {
    const text = normalize(value);
    if (!text) return new Set();
    if (text.length <= n) return new Set([text]);
    const out = new Set();
    for (let i = 0; i <= text.length - n; i++) out.add(text.slice(i, i + n));
    return out;
  }

  function dice(a, b) {
    if (!a.size || !b.size) return 0;
    let common = 0;
    for (const x of a) if (b.has(x)) common++;
    return (2 * common) / (a.size + b.size);
  }

  function namedPieces(value) {
    const text = String(value || '').normalize('NFKC');
    const pieces = [];
    const re = /[「『【\[\(]([^」』】\]\)]{2,28})[」』】\]\)]/g;
    let m;
    while ((m = re.exec(text))) {
      const n = normalize(m[1]);
      if (n.length >= 2) pieces.push(n);
    }
    return new Set(pieces.slice(0, 12));
  }

  function sharedNamedScore(a, b) {
    const aa = namedPieces(a), bb = namedPieces(b);
    if (!aa.size || !bb.size) return 0;
    for (const x of aa) {
      for (const y of bb) {
        if (x === y || (Math.min(x.length, y.length) >= 4 && (x.includes(y) || y.includes(x)))) return 1;
      }
    }
    return 0;
  }

  function similarity(a, b) {
    const aTitle = String(a?.titleJa || a?.title || '');
    const bTitle = String(b?.titleJa || b?.title || '');
    const aBody = String(a?.summaryJa || a?.bodyJa || a?.body || '').slice(0, 360);
    const bBody = String(b?.summaryJa || b?.bodyJa || b?.body || '').slice(0, 360);
    const title = Math.max(dice(gramSet(aTitle, 2), gramSet(bTitle, 2)), dice(gramSet(aTitle, 3), gramSet(bTitle, 3)));
    const body = dice(gramSet(aBody, 2), gramSet(bBody, 2));
    const named = Math.max(sharedNamedScore(aTitle, bTitle), sharedNamedScore(aBody, bBody));
    const sameCategory = categoryOf(a) === categoryOf(b) ? 1 : 0;
    return Math.min(1, title * 0.68 + body * 0.18 + named * 0.10 + sameCategory * 0.04);
  }

  function publishedMs(row) {
    const epoch = Number(row?.publishedAtEpoch || 0);
    return Number.isFinite(epoch) && epoch > 0 ? epoch * 1000 : 0;
  }

  function candidateDates(text, referenceMs) {
    const out = [];
    const ref = new Date(referenceMs || Date.now());
    const refYear = ref.getUTCFullYear();
    const source = String(text || '').normalize('NFKC');
    const patterns = [
      /(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日/g,
      /(?:(20\d{2})[\/.\-])(\d{1,2})[\/.\-](\d{1,2})/g,
    ];
    for (const re of patterns) {
      let m;
      while ((m = re.exec(source))) {
        const explicitYear = Number(m[1] || 0);
        const month = Number(m[2]), day = Number(m[3]);
        if (!(month >= 1 && month <= 12 && day >= 1 && day <= 31)) continue;
        const years = explicitYear ? [explicitYear] : [refYear - 1, refYear, refYear + 1];
        for (const year of years) {
          const ms = Date.UTC(year, month - 1, day, 0, 0, 0);
          if (Number.isFinite(ms)) out.push(ms);
        }
      }
    }
    return [...new Set(out)];
  }

  function implementationDate(row) {
    const published = publishedMs(row);
    if (!published) return { ms:0, basis:'不明' };
    const dates = candidateDates([row?.summaryJa, row?.bodyJa, row?.body, row?.titleJa].filter(Boolean).join(' '), published)
      .filter((ms) => ms >= published - 3 * DAY && ms <= published + 180 * DAY)
      .sort((a, b) => a - b);
    if (dates.length) return { ms:dates[0], basis:'開始日' };
    return { ms:published, basis:'記事日' };
  }

  function buildMatches(data) {
    const japan = data.filter((r) => r?.region === 'JAPAN');
    const foreign = data.filter((r) => ['CHINA','GLOBAL','KOREA'].includes(r?.region));
    const candidates = [];

    for (const source of foreign) {
      const sourceDate = implementationDate(source);
      if (!sourceDate.ms) continue;
      const sourceCategory = categoryOf(source);
      for (const jp of japan) {
        const jpDate = implementationDate(jp);
        if (!jpDate.ms) continue;
        const gap = Math.round((jpDate.ms - sourceDate.ms) / DAY);
        if (gap < -21 || gap > 240) continue;
        const jpCategory = categoryOf(jp);
        if (sourceCategory !== jpCategory && sourceCategory !== 'OTHER' && jpCategory !== 'OTHER') continue;
        const score = similarity(source, jp);
        if (score < 0.36) continue;
        candidates.push({ source, jp, sourceDate, jpDate, gap, score, category: sourceCategory === 'OTHER' ? jpCategory : sourceCategory });
      }
    }

    candidates.sort((a, b) => b.score - a.score);
    const usedSource = new Set(), usedJpByRegion = new Set(), chosen = [];
    for (const item of candidates) {
      const sourceKey = String(item.source.id || item.source.sourceUrl || '');
      const jpKey = `${item.source.region}:${String(item.jp.id || item.jp.sourceUrl || '')}`;
      if (!sourceKey || usedSource.has(sourceKey) || usedJpByRegion.has(jpKey)) continue;
      usedSource.add(sourceKey);
      usedJpByRegion.add(jpKey);
      chosen.push(item);
    }
    return chosen;
  }

  function median(values) {
    const a = values.filter(Number.isFinite).slice().sort((x,y) => x-y);
    if (!a.length) return null;
    const m = Math.floor(a.length / 2);
    return a.length % 2 ? a[m] : (a[m-1] + a[m]) / 2;
  }

  function average(values) {
    const a = values.filter(Number.isFinite);
    return a.length ? a.reduce((s,v) => s+v,0) / a.length : null;
  }

  function mad(values, med) {
    if (!Number.isFinite(med)) return null;
    return median(values.filter(Number.isFinite).map((v) => Math.abs(v - med)));
  }

  function plausible(items) {
    return items.filter((m) => m.gap >= -7 && m.gap <= 180 && m.score >= 0.40);
  }

  function statsFor(region, category = null) {
    const subset = plausible(matches).filter((m) => m.source.region === region && (!category || m.category === category));
    const gaps = subset.map((m) => m.gap);
    const med = median(gaps), avg = average(gaps), spread = mad(gaps, med);
    return { n:subset.length, median:med, average:avg, mad:spread, subset };
  }

  function allStats(category = null) {
    const subset = plausible(matches).filter((m) => !category || m.category === category);
    const gaps = subset.map((m) => m.gap);
    const med = median(gaps);
    return { n:subset.length, median:med, average:average(gaps), mad:mad(gaps, med), subset };
  }

  function modelFor(region, category) {
    const specific = statsFor(region, category);
    if (specific.n >= 2) return { ...specific, source:'地域×カテゴリ' };
    const regional = statsFor(region);
    if (regional.n >= 2) return { ...regional, source:'地域全体' };
    const categoryAll = allStats(category);
    if (categoryAll.n >= 2) return { ...categoryAll, source:'カテゴリ全体' };
    const overall = allStats();
    if (overall.n >= 1) return { ...overall, source:'全地域' };
    return null;
  }

  function formatDate(ms) {
    if (!ms) return '不明';
    try { return new Intl.DateTimeFormat('ja-JP', { year:'numeric', month:'numeric', day:'numeric', timeZone:'Asia/Tokyo' }).format(new Date(ms)); }
    catch { return '不明'; }
  }

  function formatGap(days) {
    if (!Number.isFinite(days)) return '—';
    const d = Math.round(days);
    if (d === 0) return '同日';
    if (d > 0) return `${d}日後`;
    return `日本が${Math.abs(d)}日先行`;
  }

  function shortTitle(row) {
    const value = String(row?.titleJa || row?.title || '名称不明').replace(/\s+/g, ' ').trim();
    return value.length > 68 ? `${value.slice(0,67)}…` : value;
  }

  function renderStats() {
    const regions = ['CHINA','GLOBAL','KOREA'];
    els.stats.innerHTML = regions.map((region) => {
      const s = statsFor(region);
      const meta = REGION[region];
      if (!s.n || !Number.isFinite(s.median)) {
        return `<article class="gap-stat-card is-empty"><div class="gap-stat-top"><span class="gap-stat-route">${meta.flag} ${meta.label} → 🇯🇵 日本</span><span class="gap-stat-samples">0件</span></div><div class="gap-stat-value">データ不足</div><div class="gap-stat-meta">一致する実装記事が増えると自動更新されます</div></article>`;
      }
      return `<article class="gap-stat-card"><div class="gap-stat-top"><span class="gap-stat-route">${meta.flag} ${meta.label} → 🇯🇵 日本</span><span class="gap-stat-samples">${s.n}件</span></div><div class="gap-stat-value">${escapeHtml(formatGap(s.median).replace('後',''))}<small>${s.median > 0 ? '遅れ中央値' : '中央値'}</small></div><div class="gap-stat-meta">平均 ${escapeHtml(formatGap(s.average))}${Number.isFinite(s.mad) ? ` · ばらつき ±${Math.max(1,Math.round(s.mad))}日` : ''}</div></article>`;
    }).join('');
  }

  function renderFilters() {
    const available = new Set(rows.filter((r) => r?.earlyInfo && r?.region !== 'JAPAN').map(categoryOf));
    const keys = ['ALL','GACHA','OUTFIT','EVENT','UPDATE','FEATURE','OTHER'].filter((k) => k === 'ALL' || available.has(k));
    els.filters.replaceChildren();
    for (const key of keys) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `gap-filter${selectedCategory === key ? ' is-active' : ''}`;
      button.textContent = CATEGORY[key];
      button.addEventListener('click', () => { selectedCategory = key; renderFilters(); renderForecasts(); });
      els.filters.appendChild(button);
    }
  }

  function renderForecasts() {
    let pending = rows.filter((r) => r?.earlyInfo === true && ['CHINA','GLOBAL','KOREA'].includes(r?.region));
    if (selectedCategory !== 'ALL') pending = pending.filter((r) => categoryOf(r) === selectedCategory);
    pending.sort((a,b) => publishedMs(b) - publishedMs(a));
    pending = pending.slice(0, 18);

    if (!pending.length) {
      els.forecasts.innerHTML = '<div class="gap-empty">このカテゴリには現在、予測対象の先行情報がありません。</div>';
      return;
    }

    els.forecasts.innerHTML = pending.map((row) => {
      const category = categoryOf(row);
      const model = modelFor(row.region, category);
      const sourceDate = implementationDate(row);
      const region = REGION[row.region] || { flag:'🌐', label:row.region || '海外' };
      const title = escapeHtml(shortTitle(row));
      const href = escapeHtml(row.sourceUrl || '#');
      if (!model || !Number.isFinite(model.median)) {
        return `<article class="gap-forecast"><div class="gap-forecast-head"><div class="gap-forecast-title"><a class="gap-source-link" href="${href}" target="_blank" rel="noopener noreferrer"><strong>${title}</strong></a><small>${region.flag} ${escapeHtml(region.label)} · ${escapeHtml(sourceDate.basis)}</small></div><span class="gap-category">${escapeHtml(CATEGORY[category])}</span></div><div class="gap-forecast-note">日本版予測: まだ比較サンプルが足りません。</div></article>`;
      }
      const lag = Math.round(model.median);
      const predicted = sourceDate.ms + lag * DAY;
      const spread = Math.max(7, Math.round((Number.isFinite(model.mad) ? model.mad * 1.5 : 14)), model.n < 3 ? 14 : 0);
      const confidence = model.n >= 6 ? '高め' : model.n >= 3 ? '中' : '低め';
      return `<article class="gap-forecast"><div class="gap-forecast-head"><div class="gap-forecast-title"><a class="gap-source-link" href="${href}" target="_blank" rel="noopener noreferrer"><strong>${title}</strong></a><small>${region.flag} ${escapeHtml(region.label)} · ${escapeHtml(sourceDate.basis)}</small></div><span class="gap-category">${escapeHtml(CATEGORY[category])}</span></div><div class="gap-forecast-grid"><div class="gap-date-box"><span>${region.flag} ${escapeHtml(region.label)}</span><strong>${escapeHtml(formatDate(sourceDate.ms))}</strong></div><div class="gap-date-arrow">→</div><div class="gap-date-box"><span>🇯🇵 日本版予想</span><strong>${escapeHtml(formatDate(predicted))}</strong></div></div><div class="gap-forecast-note">予想範囲 ${escapeHtml(formatDate(predicted - spread * DAY))}〜${escapeHtml(formatDate(predicted + spread * DAY))} · ${escapeHtml(model.source)} ${model.n}件から推定<span class="gap-confidence">確度 ${confidence}</span></div></article>`;
    }).join('');
  }

  function renderMatches() {
    const shown = matches
      .filter((m) => m.score >= 0.40)
      .sort((a,b) => Math.max(b.sourceDate.ms,b.jpDate.ms) - Math.max(a.sourceDate.ms,a.jpDate.ms))
      .slice(0, 36);
    if (!shown.length) {
      els.matches.innerHTML = '<div class="gap-empty">高一致と判断できるコンテンツがまだありません。ニュース履歴が増えるほど比較精度が上がります。</div>';
      return;
    }
    els.matches.innerHTML = shown.map((m) => {
      const region = REGION[m.source.region] || { flag:'🌐', label:m.source.region || '海外' };
      const title = escapeHtml(shortTitle(m.jp));
      const srcHref = escapeHtml(m.source.sourceUrl || '#');
      const jpHref = escapeHtml(m.jp.sourceUrl || '#');
      return `<article class="gap-match"><div class="gap-match-head"><div class="gap-match-title"><strong>${title}</strong><small>${region.flag} ${escapeHtml(region.label)} → 🇯🇵 日本</small></div><span class="gap-category">${escapeHtml(CATEGORY[m.category] || CATEGORY.OTHER)}</span></div><div class="gap-match-timeline"><a class="gap-date-box gap-source-link" href="${srcHref}" target="_blank" rel="noopener noreferrer"><span>${region.flag} ${escapeHtml(region.label)} · ${escapeHtml(m.sourceDate.basis)}</span><strong>${escapeHtml(formatDate(m.sourceDate.ms))}</strong></a><div class="gap-match-gap">${escapeHtml(formatGap(m.gap))}</div><a class="gap-date-box gap-source-link" href="${jpHref}" target="_blank" rel="noopener noreferrer"><span>🇯🇵 日本 · ${escapeHtml(m.jpDate.basis)}</span><strong>${escapeHtml(formatDate(m.jpDate.ms))}</strong></a></div><div class="gap-match-score">自動照合一致度 ${Math.round(m.score * 100)}%</div></article>`;
    }).join('');
  }

  async function load() {
    try {
      const response = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache:'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      if (!Array.isArray(payload)) throw new Error('データ形式エラー');
      rows = payload.filter((r) => r && typeof r === 'object');
      matches = buildMatches(rows);
      renderStats();
      renderFilters();
      renderForecasts();
      renderMatches();
      const early = rows.filter((r) => r?.earlyInfo === true).length;
      els.status.textContent = `${rows.length}件を分析 · 一致 ${matches.filter((m)=>m.score>=0.40).length}組 · 先行情報 ${early}件`;
    } catch (error) {
      els.status.textContent = `分析データを取得できませんでした (${error.message})`;
      els.stats.innerHTML = '<div class="gap-empty">データを読み込めませんでした。</div>';
      els.forecasts.innerHTML = '';
      els.matches.innerHTML = '';
    }
  }

  els.theme?.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'));
  initTheme();
  load();
})();
