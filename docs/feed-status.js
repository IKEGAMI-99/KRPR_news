(() => {
  const status = document.querySelector('#statusText');
  if (!status) return;

  const API = 'https://api.github.com/repos/IKEGAMI-99/KRPR_news/actions/workflows/news-refresh.yml/runs?per_page=1';
  const CACHE_KEY = 'kirapara-feed-run-status-v1';
  let displayValue = '';
  let applying = false;

  function formatJst(value) {
    if (!value) return '';
    try {
      return new Intl.DateTimeFormat('ja-JP', {
        timeZone: 'Asia/Tokyo', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'
      }).format(new Date(value));
    } catch { return ''; }
  }

  function apply(value) {
    displayValue = value || displayValue;
    if (!displayValue || status.textContent === displayValue) return;
    applying = true;
    status.textContent = displayValue;
    applying = false;
  }

  function cached() {
    try { return JSON.parse(localStorage.getItem(CACHE_KEY) || 'null'); } catch { return null; }
  }

  function save(run) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(run)); } catch {}
  }

  function labelFor(run) {
    if (!run) return '';
    const started = formatJst(run.run_started_at || run.created_at);
    if (['queued', 'waiting', 'pending', 'in_progress'].includes(run.status)) {
      return started ? `ニュース収集中… · ${started}開始` : 'ニュース収集中…';
    }
    if (run.status === 'completed' && run.conclusion === 'success') {
      return started ? `最終取得 ${started}` : '取得待機中';
    }
    if (run.status === 'completed') {
      return started ? `取得エラー · ${started}` : '取得エラー';
    }
    return started ? `最終取得 ${started}` : '取得状況を確認中…';
  }

  async function refresh() {
    try {
      const response = await fetch(API, {
        headers: { 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' },
        cache: 'no-store'
      });
      if (!response.ok) throw new Error(String(response.status));
      const payload = await response.json();
      const run = Array.isArray(payload?.workflow_runs) ? payload.workflow_runs[0] : null;
      if (run) save(run);
      apply(labelFor(run) || '取得待機中');
    } catch {
      const old = cached();
      apply(labelFor(old) || '取得状況を確認できません');
    }
  }

  // app.js updates this same line after loading articles. Keep this line dedicated
  // to the crawler itself, not the newest article timestamp.
  new MutationObserver(() => {
    if (!applying && displayValue && status.textContent !== displayValue) apply(displayValue);
  }).observe(status, { childList: true, characterData: true, subtree: true });

  refresh();
  setInterval(refresh, 90 * 1000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
})();
