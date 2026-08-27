(() => {
  const panel = document.querySelector('.developer-panel');
  if (!panel || panel.querySelector('.dev-release-card')) return;

  const API = 'https://api.github.com/repos/IKEGAMI-99/KRPR_news';
  const RELEASE_URL = `${API}/releases/latest`;
  const BRANCH_URL = `${API}/branches/main`;
  const RELEASE_NOTES = [
    'ニュース一覧の区切りを月単位からJST基準の日付単位へ変更',
    'Qwen翻訳・要約を専用workflowへ分離し、日本語出力の検証と再試行を強化',
    'Sol監査による誤訳修正と、修正結果をQwen辞書へフィードバックする仕組みを追加',
    '翻訳辞書を将来のKRPR特化LoRA学習に使える構造化形式へ移行',
    '先行情報のAI推定注意文、自動更新スケジュール、PWAキャッシュ更新を改善'
  ];

  const card = document.createElement('section');
  card.className = 'dev-release-card';
  card.innerHTML = `
    <div class="dev-release-head">
      <div>
        <span class="dev-release-kicker">CURRENT VERSION</span>
        <strong class="dev-release-version">取得中…</strong>
      </div>
      <span class="dev-release-channel">PWA MAIN</span>
    </div>
    <div class="dev-release-build">
      <span>Release <b class="dev-release-tag">—</b></span>
      <span>Build <code class="dev-release-sha">—</code></span>
    </div>
    <div class="dev-release-updated">mainの状態を確認しています</div>
    <div class="dev-release-notes-title">リリースノート</div>
    <ul class="dev-release-notes">${RELEASE_NOTES.map((note) => `<li>${note}</li>`).join('')}</ul>
    <p class="dev-release-note">PWA版は最新GitHub Release以降のmain更新も含みます。</p>`;

  panel.prepend(card);

  function fmt(value) {
    if (!value) return '';
    try {
      return new Intl.DateTimeFormat('ja-JP', {
        year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'
      }).format(new Date(value));
    } catch { return String(value); }
  }

  async function apiJson(url) {
    const response = await fetch(url, {
      headers: { 'Accept':'application/vnd.github+json', 'X-GitHub-Api-Version':'2022-11-28' },
      cache: 'no-store'
    });
    if (!response.ok) throw new Error(`GitHub API ${response.status}`);
    return response.json();
  }

  async function loadVersion() {
    const version = card.querySelector('.dev-release-version');
    const tag = card.querySelector('.dev-release-tag');
    const sha = card.querySelector('.dev-release-sha');
    const updated = card.querySelector('.dev-release-updated');

    try {
      const [release, branch] = await Promise.all([
        apiJson(RELEASE_URL).catch(() => null),
        apiJson(BRANCH_URL).catch(() => null)
      ]);
      const releaseTag = String(release?.tag_name || 'unreleased');
      const fullSha = String(branch?.commit?.sha || '');
      const shortSha = fullSha ? fullSha.slice(0, 7) : '—';
      const mainDate = branch?.commit?.commit?.committer?.date || branch?.commit?.commit?.author?.date;

      version.textContent = releaseTag === 'unreleased' ? 'Kirapara News · main' : `Kirapara News ${releaseTag}`;
      tag.textContent = releaseTag;
      sha.textContent = shortSha;
      updated.textContent = mainDate ? `PWA build更新: ${fmt(mainDate)}` : 'PWA build: main';
    } catch (error) {
      version.textContent = 'Kirapara News · main';
      tag.textContent = '取得失敗';
      sha.textContent = '—';
      updated.textContent = 'バージョン情報を取得できませんでした';
    }
  }

  loadVersion();
})();
