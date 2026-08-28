(() => {
  const trigger = document.querySelector('#menuButton');
  if (!trigger) return;

  const IS_LOCAL_PREVIEW = ['localhost', '127.0.0.1'].includes(location.hostname);
  const TRANSLATIONS_URL = IS_LOCAL_PREVIEW
    ? '../data/translations.json'
    : 'https://raw.githubusercontent.com/IKEGAMI-99/KRPR_news/main/data/translations.json';
  const CURRENT_MODEL = 'litert-community/gemma-4-E4B-it-litert-lm:LiteRT-LM';
  const CURRENT_REVISION = 'gemma-4-e4b-it-litertlm-summary-facts-region-titles-strict-ja-v2';
  const RUN_MINUTES = [7, 22, 37, 52];
  const tokyoDateTime = new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
  const tokyoClock = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Tokyo',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });

  let translationCache = null;
  let translationLoading = null;

  const groups = [
    { title:'🇯🇵 日本', links:[
      ['公式サイト','https://kirapara.archosaur.com/'],
      ['公式X','https://x.com/kirapara_JP'],
      ['Instagram','https://www.instagram.com/kiramekiparadise_jp/'],
      ['YouTube','https://www.youtube.com/channel/UC9MO21fNvt0F4-UK28kc_VQ'],
      ['TikTok','https://www.tiktok.com/@kiramekiparadise_jp'],
      ['公式LINE','https://openchat.line.me/jp/cover/kMSwiIddYL1bwpCK-ftv2QKCyCARSVIyV0fo1ou7trbLtA5_RrN71OtwWWk'],
      ['攻略Wiki','https://gamerch.com/kirapara/'],
    ]},
    { title:'🇨🇳 中国', links:[
      ['公式サイト','https://mystyle.archosaur.com/'],
      ['Weibo','https://weibo.com/u/7521830234'],
      ['Bilibili','https://space.bilibili.com/676200579'],
      ['TapTap','https://www.taptap.cn/app/218210/topic?type=official'],
      ['好游快爆','https://m.3839.com/a/137078.htm'],
      ['抖音','https://www.douyin.com/user/MS4wLjABAAAAkoSoF-ocsviTaKo31fSAT3f6sWROggvyk8kgt-mdQ07AZ6gSi8skQ1aPHu2moL17'],
      ['小紅書','https://www.xiaohongshu.com/search_result?keyword=%E4%BB%A5%E9%97%AA%E4%BA%AE%E4%B9%8B%E5%90%8DVVANNA%20Studio'],
      ['百度贴吧','https://tieba.baidu.com/f?kw=%E4%BB%A5%E9%97%AA%E4%BA%AE%E4%B9%8B%E5%90%8D'],
      ['WeChat','https://weixin.sogou.com/weixin?type=1&query=%E4%BB%A5%E9%97%AA%E4%BA%AE%E4%B9%8B%E5%90%8D'],
    ]},
    { title:'🌐 Global', links:[
      ['公式サイト','https://lifemakeover.archosaur.com/'],
      ['公式X','https://x.com/LifeMakeover510'],
      ['Instagram','https://www.instagram.com/lifemakeover_global/'],
      ['YouTube','https://www.youtube.com/@LifeMakeover'],
      ['TikTok','https://www.tiktok.com/@lifemakeoverofficial'],
      ['Wiki','https://lifemakeover.wiki.gg/'],
    ]},
    { title:'🇰🇷 韓国', links:[
      ['公式サイト','https://stylight.nex2fun.com/'],
      ['公式X','https://x.com/stylight_kr'],
      ['Instagram','https://www.instagram.com/stylight_kr/'],
      ['YouTube','https://www.youtube.com/@stylight_official'],
      ['TikTok','https://www.tiktok.com/@stylightofficial'],
      ['Naver Cafe','https://cafe.naver.com/stylightofficial'],
      ['Naver Lounge','https://game.naver.com/lounge/stylight/home'],
    ]},
  ];

  const backdrop = document.createElement('div');
  backdrop.className = 'menu-backdrop';
  const menu = document.createElement('aside');
  menu.className = 'link-menu';
  menu.setAttribute('role', 'dialog');
  menu.setAttribute('aria-modal', 'true');
  menu.setAttribute('aria-label', 'メニュー');
  menu.innerHTML = `<div class="link-menu-header"><div class="link-menu-title">メニュー ✦</div><button class="link-menu-close" type="button" aria-label="閉じる">×</button></div><div class="link-menu-body"></div>`;
  const body = menu.querySelector('.link-menu-body');

  const officialLinks = document.createElement('div');
  officialLinks.className = 'official-links-block';

  const linksHeading = document.createElement('div');
  linksHeading.className = 'menu-section-heading';
  linksHeading.textContent = '公式リンク';
  officialLinks.appendChild(linksHeading);

  for (const group of groups) {
    const section = document.createElement('section');
    section.className = 'menu-region';
    const heading = document.createElement('h3');
    heading.textContent = group.title;
    const links = document.createElement('div');
    links.className = 'menu-links';
    for (const [label, url] of group.links) {
      const anchor = document.createElement('a');
      anchor.className = 'menu-link';
      anchor.href = url;
      anchor.target = '_blank';
      anchor.rel = 'noopener noreferrer';
      anchor.textContent = label;
      links.appendChild(anchor);
    }
    section.append(heading, links);
    officialLinks.appendChild(section);
  }

  const note = document.createElement('p');
  note.className = 'menu-note';
  note.textContent = 'Wikiは運営公式ではなく、コミュニティ運営の攻略Wikiです。WeChatは公式公众号「以闪亮之名」、小紅書は公式アカウント「以闪亮之名VVANNA Studio」の検索ページを開きます。';
  officialLinks.appendChild(note);
  body.appendChild(officialLinks);

  const operations = document.createElement('section');
  operations.className = 'menu-region developer-section developer-section-featured';
  operations.innerHTML = `
    <button class="developer-toggle" type="button" aria-expanded="false">
      <span><span class="developer-toggle-icon">⚙</span><span><strong>運用情報</strong><small>翻訳進捗 / 15分おき・3記事ずつ</small></span></span>
      <span class="developer-chevron">›</span>
    </button>
    <div class="developer-panel" hidden>
      <div class="dev-topline"><div><div class="dev-kicker">LOCAL AI</div><div class="dev-model">Gemma 4 E4B · LiteRT-LM</div></div><button class="dev-refresh" type="button" aria-label="翻訳状況を更新" title="翻訳状況を更新">↻</button></div>
      <div class="dev-status-card dev-waiting"><span class="dev-status-dot"></span><div><strong>翻訳状況を取得中</strong><small>公開中のニュースと翻訳キャッシュを照合します</small></div></div>
      <div class="dev-metrics"></div>
      <p class="menu-note">翻訳は毎時07・22・37・52分に最大3記事ずつ処理し、ニュース収集完了時にも補助起動します。GitHub Actionsの開始時刻は混雑時に少し遅れる場合があります。</p>
      <a class="dev-actions-link" href="https://github.com/IKEGAMI-99/KRPR_news/actions" target="_blank" rel="noopener noreferrer">GitHub Actionsで確認する ↗</a>
    </div>`;
  body.appendChild(operations);
  document.body.append(backdrop, menu);

  const toggle = operations.querySelector('.developer-toggle');
  const panel = operations.querySelector('.developer-panel');
  const refresh = operations.querySelector('.dev-refresh');
  const statusCard = operations.querySelector('.dev-status-card');
  const statusTitle = statusCard.querySelector('strong');
  const statusDetail = statusCard.querySelector('small');

  function itemKey(item) {
    return String(item?.sourceUrl || item?.id || '');
  }

  function isCurrentTranslation(entry) {
    if (!entry || typeof entry !== 'object') return false;
    const hasText = ['titleJa', 'bodyJa', 'summaryJa'].every((field) => typeof entry[field] === 'string' && entry[field].trim());
    if (!hasText) return false;
    const model = String(entry.model || '');
    if (entry.managedBySol || model.includes('GPT-5.6 Sol')) return true;
    return model === CURRENT_MODEL
      && String(entry.modelRevision || '') === CURRENT_REVISION
      && Number(entry.summaryFormatVersion || 0) === 4;
  }

  function nextRunLabel() {
    const [hourText, minuteText] = tokyoClock.format(new Date()).split(':');
    let hour = Number(hourText);
    const minute = Number(minuteText);
    let nextMinute = RUN_MINUTES.find((value) => value > minute);
    if (nextMinute === undefined) {
      nextMinute = RUN_MINUTES[0];
      hour = (hour + 1) % 24;
    }
    return `${String(hour).padStart(2, '0')}:${String(nextMinute).padStart(2, '0')}ごろ`;
  }

  function renderOperations() {
    const items = (typeof state !== 'undefined' && Array.isArray(state.items)) ? state.items : [];
    const candidates = items.filter((item) => item?.title || item?.body);
    const entries = translationCache?.items && typeof translationCache.items === 'object' ? translationCache.items : null;

    let translated;
    let pending;
    let lastEpoch = 0;

    if (entries) {
      translated = 0;
      for (const item of candidates) {
        const entry = entries[itemKey(item)];
        if (!isCurrentTranslation(entry)) continue;
        translated += 1;
        lastEpoch = Math.max(lastEpoch, Number(entry.updatedAtEpoch || 0));
      }
      pending = Math.max(0, candidates.length - translated);
    } else {
      translated = candidates.filter((item) => item?.aiProcessed && item?.summaryJa).length;
      pending = null;
    }

    statusCard.classList.remove('dev-success', 'dev-waiting', 'dev-failure');
    if (!entries) {
      statusCard.classList.add('dev-waiting');
      statusTitle.textContent = '翻訳状況を取得中';
      statusDetail.textContent = 'ニュース一覧の暫定値を表示しています';
    } else if (pending === 0) {
      statusCard.classList.add('dev-success');
      statusTitle.textContent = '翻訳バックログなし';
      statusDetail.textContent = '現在の公開記事はすべて処理済みです';
    } else {
      statusCard.classList.add('dev-waiting');
      statusTitle.textContent = `未翻訳 ${pending}件`;
      statusDetail.textContent = '15分ごとに最大3記事ずつ処理します';
    }

    const metrics = operations.querySelector('.dev-metrics');
    metrics.replaceChildren();
    const rows = [
      ['翻訳済み', `${translated} / ${candidates.length || '—'}`],
      ['未翻訳', pending === null ? '取得中…' : `${pending}件`],
      ['1回の処理', '最大3記事'],
      ['実行間隔', '15分'],
      ['最終翻訳', lastEpoch ? tokyoDateTime.format(new Date(lastEpoch * 1000)) : '—'],
      ['次回定期', nextRunLabel()],
    ];
    for (const [label, value] of rows) {
      const metric = document.createElement('div');
      metric.className = 'dev-metric';
      const name = document.createElement('span');
      name.textContent = label;
      const result = document.createElement('strong');
      result.textContent = value;
      metric.append(name, result);
      metrics.appendChild(metric);
    }
  }

  async function loadTranslationCache({ force = false } = {}) {
    if (translationLoading && !force) return translationLoading;
    refresh.classList.add('is-loading');
    refresh.disabled = true;
    translationLoading = (async () => {
      try {
        const separator = TRANSLATIONS_URL.includes('?') ? '&' : '?';
        const response = await fetch(`${TRANSLATIONS_URL}${separator}t=${Date.now()}`, { cache: 'no-store' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const value = await response.json();
        if (!value || typeof value !== 'object' || !value.items || typeof value.items !== 'object') throw new Error('invalid translations cache');
        translationCache = value;
      } catch {
        translationCache = null;
        statusCard.classList.remove('dev-success', 'dev-waiting');
        statusCard.classList.add('dev-failure');
        statusTitle.textContent = '翻訳状況の取得に失敗';
        statusDetail.textContent = 'ニュース一覧の暫定値のみ表示しています';
      } finally {
        refresh.classList.remove('is-loading');
        refresh.disabled = false;
        translationLoading = null;
        renderOperations();
      }
    })();
    return translationLoading;
  }

  toggle.addEventListener('click', () => {
    const open = panel.hidden;
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    operations.classList.toggle('is-open', open);
    if (open) {
      renderOperations();
      loadTranslationCache();
    }
  });
  refresh.addEventListener('click', () => loadTranslationCache({ force: true }));
  document.addEventListener('kirapara:rendered', () => { if (!panel.hidden) renderOperations(); });

  const close = () => {
    menu.classList.remove('is-open');
    backdrop.classList.remove('is-open');
    document.body.classList.remove('menu-open');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.focus();
  };
  const open = () => {
    menu.classList.add('is-open');
    backdrop.classList.add('is-open');
    document.body.classList.add('menu-open');
    trigger.setAttribute('aria-expanded', 'true');
    menu.querySelector('.link-menu-close').focus();
  };
  trigger.setAttribute('aria-expanded', 'false');
  trigger.addEventListener('click', () => menu.classList.contains('is-open') ? close() : open());
  backdrop.addEventListener('click', close);
  menu.querySelector('.link-menu-close').addEventListener('click', close);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && menu.classList.contains('is-open')) close();
  });
})();
