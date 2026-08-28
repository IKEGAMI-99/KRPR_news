(() => {
  const trigger = document.querySelector('#menuButton');
  if (!trigger) return;

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

  const operations = document.createElement('section');
  operations.className = 'menu-region developer-section developer-section-featured';
  operations.innerHTML = `
    <button class="developer-toggle" type="button" aria-expanded="false">
      <span><span class="developer-toggle-icon">⚙</span><span><strong>運用情報</strong><small>AI処理件数 / GitHub Actions</small></span></span>
      <span class="developer-chevron">›</span>
    </button>
    <div class="developer-panel" hidden>
      <div class="dev-topline"><div><div class="dev-kicker">LOCAL AI</div><div class="dev-model">Gemma 4 E4B · LiteRT-LM</div></div></div>
      <div class="dev-status-card dev-success"><span class="dev-status-dot"></span><div><strong>公開データの処理状況</strong><small>一覧に読み込んだデータから集計</small></div></div>
      <div class="dev-metrics"></div>
      <p class="menu-note">実行中・失敗などのリアルタイム状態はGitHub Actionsで確認できます。</p>
      <a class="dev-actions-link" href="https://github.com/IKEGAMI-99/KRPR_news/actions" target="_blank" rel="noopener noreferrer">GitHub Actionsで確認する ↗</a>
    </div>`;
  body.appendChild(operations);

  const linksHeading = document.createElement('div');
  linksHeading.className = 'menu-section-heading';
  linksHeading.textContent = '公式リンク';
  body.appendChild(linksHeading);

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
    body.appendChild(section);
  }

  const note = document.createElement('p');
  note.className = 'menu-note';
  note.textContent = 'Wikiは運営公式ではなく、コミュニティ運営の攻略Wikiです。WeChatは公開Webプロフィールがないため、公式公众号「以闪亮之名」の検索ページを開きます。';
  body.appendChild(note);
  document.body.append(backdrop, menu);

  const toggle = operations.querySelector('.developer-toggle');
  const panel = operations.querySelector('.developer-panel');

  function renderOperations() {
    const items = (typeof state !== 'undefined' && Array.isArray(state.items)) ? state.items : [];
    const ai = items.filter((item) => item?.aiProcessed && item?.summaryJa).length;
    const facts = items.filter((item) => item?.aiSummaryFormat === 'facts-v2').length;
    const metrics = operations.querySelector('.dev-metrics');
    metrics.replaceChildren();
    for (const [label, value] of [
      ['AI処理済み', `${ai} / ${items.length || '—'}`],
      ['箇条書き要約', `${facts} / ${items.length || '—'}`],
      ['翻訳モデル', 'Gemma 4 E4B'],
    ]) {
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

  toggle.addEventListener('click', () => {
    const open = panel.hidden;
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    operations.classList.toggle('is-open', open);
    if (open) renderOperations();
  });
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
