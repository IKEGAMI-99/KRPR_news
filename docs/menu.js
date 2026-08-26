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
      ['攻略Wiki','https://gamerch.com/kirapara/']
    ]},
    { title:'🇨🇳 中国', links:[
      ['公式サイト','https://mystyle.archosaur.com/'],
      ['Weibo','https://weibo.com/u/7521830234'],
      ['Bilibili','https://space.bilibili.com/676200579']
    ]},
    { title:'🌐 Global', links:[
      ['公式サイト','https://lifemakeover.archosaur.com/'],
      ['公式X','https://x.com/LifeMakeover510'],
      ['Instagram','https://www.instagram.com/lifemakeover_global/'],
      ['YouTube','https://www.youtube.com/@LifeMakeover'],
      ['TikTok','https://www.tiktok.com/@lifemakeoverofficial'],
      ['Wiki','https://lifemakeover.wiki.gg/']
    ]},
    { title:'🇰🇷 韓国', links:[
      ['公式サイト','https://stylight.nex2fun.com/'],
      ['公式X','https://x.com/stylight_kr'],
      ['Instagram','https://www.instagram.com/stylight_kr/'],
      ['YouTube','https://www.youtube.com/@stylight_official'],
      ['TikTok','https://www.tiktok.com/@stylightofficial'],
      ['Naver Cafe','https://cafe.naver.com/stylightofficial'],
      ['Naver Lounge','https://game.naver.com/lounge/stylight/home']
    ]}
  ];

  const API = 'https://api.github.com/repos/IKEGAMI-99/KRPR_news';
  const WORKFLOW_RUNS = `${API}/actions/workflows/news-refresh.yml/runs?per_page=5`;
  const DEV_CACHE_KEY = 'kirapara-dev-status-v2';
  const DEV_CACHE_MS = 3 * 60 * 1000;

  const backdrop = document.createElement('div');
  backdrop.className = 'menu-backdrop';
  const menu = document.createElement('aside');
  menu.className = 'link-menu';
  menu.setAttribute('role','dialog');
  menu.setAttribute('aria-modal','true');
  menu.setAttribute('aria-label','メニュー');
  menu.innerHTML = `<div class="link-menu-header"><div class="link-menu-title">メニュー ✦</div><button class="link-menu-close" type="button" aria-label="閉じる">×</button></div><div class="link-menu-body"></div>`;
  const body = menu.querySelector('.link-menu-body');

  const devSection = document.createElement('section');
  devSection.className = 'menu-region developer-section developer-section-featured';
  devSection.innerHTML = `
    <button class="developer-toggle" type="button" aria-expanded="false">
      <span><span class="developer-toggle-icon">⚙</span><span><strong>開発者メニュー</strong><small>AI / GitHub Actions の状態</small></span></span>
      <span class="developer-chevron">›</span>
    </button>
    <div class="developer-panel" hidden>
      <div class="dev-topline">
        <div>
          <div class="dev-kicker">LOCAL AI / GITHUB ACTIONS</div>
          <div class="dev-model">Qwen2.5 3B · Q4_K_M</div>
        </div>
        <button class="dev-refresh" type="button" title="状態を更新" aria-label="AI状態を更新">↻</button>
      </div>
      <div class="dev-status-card dev-loading">
        <span class="dev-status-dot"></span>
        <div><strong>取得中…</strong><small>GitHub Actionsを確認しています</small></div>
      </div>
      <div class="dev-metrics"></div>
      <div class="dev-steps"></div>
      <div class="dev-runs"></div>
      <a class="dev-actions-link" href="https://github.com/IKEGAMI-99/KRPR_news/actions/workflows/news-refresh.yml" target="_blank" rel="noopener noreferrer">GitHub Actionsで詳細を見る ↗</a>
    </div>`;
  body.appendChild(devSection);

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
    for (const [label,url] of group.links) {
      const a = document.createElement('a');
      a.className = 'menu-link';
      a.href = url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.textContent = label;
      links.appendChild(a);
    }
    section.append(heading,links);
    body.appendChild(section);
  }

  const note = document.createElement('p');
  note.className = 'menu-note';
  note.textContent = 'Wikiは運営公式ではなく、コミュニティ運営の攻略Wikiです。';
  body.appendChild(note);
  document.body.append(backdrop,menu);

  const devToggle = devSection.querySelector('.developer-toggle');
  const devPanel = devSection.querySelector('.developer-panel');
  const devRefresh = devSection.querySelector('.dev-refresh');

  function statusLabel(status, conclusion) {
    if (status === 'queued' || status === 'waiting' || status === 'pending') return ['待機中','waiting'];
    if (status === 'in_progress') return ['動作中','running'];
    if (status === 'completed') {
      if (conclusion === 'success') return ['正常終了','success'];
      if (conclusion === 'cancelled') return ['キャンセル','cancelled'];
      if (conclusion === 'skipped') return ['スキップ','skipped'];
      return ['エラー','failure'];
    }
    return ['不明','unknown'];
  }

  function formatTime(value) {
    if (!value) return '不明';
    try {
      return new Intl.DateTimeFormat('ja-JP', { month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit' }).format(new Date(value));
    } catch { return value; }
  }

  function elapsed(start, end) {
    if (!start) return '';
    const a = new Date(start).getTime();
    const b = end ? new Date(end).getTime() : Date.now();
    if (!Number.isFinite(a) || !Number.isFinite(b)) return '';
    const sec = Math.max(0, Math.round((b-a)/1000));
    if (sec < 60) return `${sec}秒`;
    const min = Math.floor(sec/60), rem = sec%60;
    return `${min}分${rem ? `${rem}秒` : ''}`;
  }

  function processedCount() {
    try {
      if (typeof state === 'undefined' || !Array.isArray(state.items)) return null;
      const total = state.items.length;
      const ai = state.items.filter((item) => item?.aiProcessed && item?.summaryJa).length;
      const facts = state.items.filter((item) => item?.aiSummaryFormat === 'facts-v2').length;
      return { ai, facts, total };
    } catch { return null; }
  }

  async function apiJson(url) {
    const response = await fetch(url, {
      headers: { 'Accept':'application/vnd.github+json', 'X-GitHub-Api-Version':'2022-11-28' },
      cache: 'no-store'
    });
    if (!response.ok) throw new Error(`GitHub API ${response.status}`);
    return response.json();
  }

  function readCached() {
    try {
      const value = JSON.parse(sessionStorage.getItem(DEV_CACHE_KEY) || 'null');
      if (value && Date.now() - Number(value.savedAt || 0) < DEV_CACHE_MS) return value.data;
    } catch {}
    return null;
  }

  function saveCached(data) {
    try { sessionStorage.setItem(DEV_CACHE_KEY, JSON.stringify({ savedAt:Date.now(), data })); } catch {}
  }

  async function fetchStatus(force = false) {
    if (!force) {
      const cached = readCached();
      if (cached) return cached;
    }
    const runsPayload = await apiJson(WORKFLOW_RUNS);
    const runs = Array.isArray(runsPayload?.workflow_runs) ? runsPayload.workflow_runs : [];
    const latest = runs[0] || null;
    let job = null;
    if (latest?.jobs_url) {
      const jobsPayload = await apiJson(latest.jobs_url);
      job = Array.isArray(jobsPayload?.jobs) ? jobsPayload.jobs[0] || null : null;
    }
    const data = { runs, latest, job };
    saveCached(data);
    return data;
  }

  function stepByName(job, fragment) {
    return Array.isArray(job?.steps) ? job.steps.find((step) => String(step?.name || '').includes(fragment)) : null;
  }

  function renderStatus(data) {
    const latest = data.latest;
    const job = data.job;
    const aiStep = stepByName(job, 'Translate and summarize');
    const planStep = stepByName(job, 'Apply cached translations');
    const advanceStep = stepByName(job, 'Compare overseas previews');
    const [mainLabel, mainClass] = statusLabel(aiStep?.status || latest?.status, aiStep?.conclusion || latest?.conclusion);
    const card = devSection.querySelector('.dev-status-card');
    card.className = `dev-status-card dev-${mainClass}`;
    card.innerHTML = `<span class="dev-status-dot"></span><div><strong>AI ${mainLabel}</strong><small>${aiStep?.name || 'Refresh News Cache'}${aiStep?.started_at ? ` · ${elapsed(aiStep.started_at, aiStep.completed_at)}` : ''}</small></div>`;

    const counts = processedCount();
    const metrics = devSection.querySelector('.dev-metrics');
    metrics.innerHTML = `
      <div class="dev-metric"><span>最新Run</span><strong>#${latest?.run_number ?? '—'}</strong></div>
      <div class="dev-metric"><span>開始</span><strong>${formatTime(latest?.run_started_at || latest?.created_at)}</strong></div>
      <div class="dev-metric"><span>AI処理済み</span><strong>${counts ? `${counts.ai} / ${counts.total}` : '—'}</strong></div>
      <div class="dev-metric"><span>箇条書き要約</span><strong>${counts ? `${counts.facts} / ${counts.total}` : '—'}</strong></div>`;

    const steps = [
      ['翻訳計画', planStep],
      ['翻訳・要約AI', aiStep],
      ['先行情報比較', advanceStep]
    ];
    devSection.querySelector('.dev-steps').innerHTML = `<div class="dev-section-label">現在の処理</div>${steps.map(([label,step]) => {
      const [text, cls] = statusLabel(step?.status, step?.conclusion);
      return `<div class="dev-step"><span>${label}</span><span class="dev-pill dev-${cls}">${text}</span></div>`;
    }).join('')}`;

    const recent = (data.runs || []).slice(0,3);
    devSection.querySelector('.dev-runs').innerHTML = `<div class="dev-section-label">最近の実行</div>${recent.map((run) => {
      const [text, cls] = statusLabel(run.status, run.conclusion);
      return `<a class="dev-run" href="${run.html_url}" target="_blank" rel="noopener noreferrer"><span><strong>#${run.run_number}</strong><small>${formatTime(run.run_started_at || run.created_at)}</small></span><span class="dev-pill dev-${cls}">${text}</span></a>`;
    }).join('')}`;
  }

  function renderError(error) {
    const card = devSection.querySelector('.dev-status-card');
    card.className = 'dev-status-card dev-failure';
    card.innerHTML = `<span class="dev-status-dot"></span><div><strong>状態を取得できません</strong><small>${String(error?.message || error)}</small></div>`;
    devSection.querySelector('.dev-steps').innerHTML = '';
    devSection.querySelector('.dev-runs').innerHTML = '';
  }

  async function refreshDeveloper(force = false) {
    devRefresh.classList.add('is-loading');
    try { renderStatus(await fetchStatus(force)); }
    catch (error) { renderError(error); }
    finally { devRefresh.classList.remove('is-loading'); }
  }

  devToggle.addEventListener('click', () => {
    const open = devPanel.hidden;
    devPanel.hidden = !open;
    devToggle.setAttribute('aria-expanded', String(open));
    devSection.classList.toggle('is-open', open);
    if (open) refreshDeveloper(false);
  });
  devRefresh.addEventListener('click', () => refreshDeveloper(true));

  const close = () => {
    menu.classList.remove('is-open');
    backdrop.classList.remove('is-open');
    document.body.classList.remove('menu-open');
    trigger.setAttribute('aria-expanded','false');
  };
  const open = () => {
    menu.classList.add('is-open');
    backdrop.classList.add('is-open');
    document.body.classList.add('menu-open');
    trigger.setAttribute('aria-expanded','true');
  };
  trigger.setAttribute('aria-expanded','false');
  trigger.addEventListener('click', () => menu.classList.contains('is-open') ? close() : open());
  backdrop.addEventListener('click', close);
  menu.querySelector('.link-menu-close').addEventListener('click', close);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && menu.classList.contains('is-open')) close(); });
})();
