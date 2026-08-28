(() => {
  const body = document.querySelector('.link-menu-body');
  if (!body) return;

  const nativeInstall = document.querySelector('#installButton');
  const devSection = body.querySelector('.developer-section');
  const officialLinks = body.querySelector('.official-links-block');

  const section = document.createElement('section');
  section.className = 'menu-install-section';
  section.innerHTML = `
    <button class="menu-install-action" type="button">
      <span class="menu-install-icon" aria-hidden="true"><img src="./icon.svg" alt=""></span>
      <span class="menu-install-copy">
        <strong>アプリとしてホームに追加</strong>
        <small>ホーム画面からすぐ起動できます</small>
      </span>
      <span class="menu-install-arrow" aria-hidden="true">＋</span>
    </button>
    <p class="menu-install-message" aria-live="polite"></p>`;
  if (officialLinks) officialLinks.insertAdjacentElement('afterend', section);
  else body.prepend(section);

  const analysis = document.createElement('section');
  analysis.className = 'menu-analysis-section';
  analysis.innerHTML = `
    <a class="menu-analysis-action" href="./gap.html">
      <span class="menu-analysis-icon" aria-hidden="true">📊</span>
      <span class="menu-analysis-copy">
        <span><strong>実装差分析</strong><b>BETA</b></span>
        <small>各国の実装差・コンテンツ比較</small>
      </span>
      <span class="menu-analysis-arrow" aria-hidden="true">›</span>
    </a>`;
  section.insertAdjacentElement('afterend', analysis);

  const terms = document.createElement('section');
  terms.className = 'menu-analysis-section';
  terms.innerHTML = `
    <a class="menu-analysis-action" href="./terms.html">
      <span class="menu-analysis-icon" aria-hidden="true">⚖️</span>
      <span class="menu-analysis-copy">
        <span><strong>利用規約</strong></span>
        <small>自動運営・免責・利用条件について</small>
      </span>
      <span class="menu-analysis-arrow" aria-hidden="true">›</span>
    </a>`;
  analysis.insertAdjacentElement('afterend', terms);

  const repository = document.createElement('section');
  repository.className = 'menu-analysis-section';
  repository.innerHTML = `
    <a class="menu-analysis-action" href="https://github.com/IKEGAMI-99/KRPR_news" target="_blank" rel="noopener noreferrer">
      <span class="menu-analysis-icon" aria-hidden="true">⌘</span>
      <span class="menu-analysis-copy">
        <span><strong>GitHubリポジトリ</strong></span>
        <small>ソースコード・README・更新履歴</small>
      </span>
      <span class="menu-analysis-arrow" aria-hidden="true">↗</span>
    </a>`;
  terms.insertAdjacentElement('afterend', repository);

  const analytics = document.createElement('section');
  analytics.className = 'menu-analysis-section';
  analytics.innerHTML = `
    <a class="menu-analysis-action" href="./analytics/">
      <span class="menu-analysis-icon" aria-hidden="true">📈</span>
      <span class="menu-analysis-copy">
        <span><strong>アクセス解析</strong></span>
        <small>公開中の集計値（個人を特定する情報は表示しません）</small>
      </span>
      <span class="menu-analysis-arrow" aria-hidden="true">›</span>
    </a>`;
  repository.insertAdjacentElement('afterend', analytics);

  const privacy = document.createElement('section');
  privacy.className = 'menu-analysis-section';
  privacy.innerHTML = `
    <a class="menu-analysis-action" href="./privacy.html">
      <span class="menu-analysis-icon" aria-hidden="true">🔒</span>
      <span class="menu-analysis-copy">
        <span><strong>プライバシーポリシー</strong></span>
        <small>GA4・Cookie・データ取扱いについて</small>
      </span>
      <span class="menu-analysis-arrow" aria-hidden="true">›</span>
    </a>`;
  analytics.insertAdjacentElement('afterend', privacy);

  const schedule = document.createElement('section');
  schedule.className = 'menu-schedule-section';
  schedule.innerHTML = `
    <div class="menu-schedule-heading">
      <span>⏱</span>
      <div><strong>自動更新スケジュール</strong><small>時刻はすべて日本時間（JST）</small></div>
    </div>
    <div class="menu-schedule-list">
      <div class="menu-schedule-row">
        <span class="menu-schedule-icon">↻</span>
        <div><strong>ニュース収集</strong><small>毎時 :00</small></div>
        <b>1時間ごと</b>
      </div>
      <div class="menu-schedule-row">
        <span class="menu-schedule-icon">✦</span>
        <div><strong>Gemma 4 E4B 翻訳・要約</strong><small>毎時 :07から15分おき・最大3記事</small></div>
        <b>15分ごと</b>
      </div>
      <div class="menu-schedule-row">
        <span class="menu-schedule-icon">◇</span>
        <div><strong>Sol 監査</strong><small>08:00 / 14:00 / 20:00</small></div>
        <b>1日3回</b>
      </div>
      <div class="menu-schedule-row">
        <span class="menu-schedule-icon">⚡</span>
        <div><strong>更新監視</strong><small>毎時 :30・異常時のみ再起動</small></div>
        <b>1時間ごと</b>
      </div>
    </div>
    <p class="menu-schedule-note">GitHub Actionsの混雑状況により、実際の開始時刻は数分以上遅れる場合があります。</p>`;
  body.appendChild(schedule);

  // Developer tools belong at the very bottom, after links, notes, schedule, and legal pages.
  if (devSection) body.appendChild(devSection);

  const action = section.querySelector('.menu-install-action');
  const copy = section.querySelector('.menu-install-copy');
  const arrow = section.querySelector('.menu-install-arrow');
  const message = section.querySelector('.menu-install-message');

  function isStandalone() {
    return window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true;
  }

  function syncState() {
    if (isStandalone()) {
      action.disabled = true;
      action.classList.add('is-installed');
      copy.innerHTML = '<strong>ホーム画面に追加済み</strong><small>アプリとして起動しています</small>';
      arrow.textContent = '✓';
      message.textContent = '';
      return;
    }

    action.disabled = false;
    action.classList.remove('is-installed');
    copy.innerHTML = '<strong>アプリとしてホームに追加</strong><small>ホーム画面からすぐ起動できます</small>';
    arrow.textContent = '＋';
  }

  action.addEventListener('click', () => {
    if (isStandalone()) return;
    message.textContent = '';

    // app.js owns the native beforeinstallprompt event. Reuse that path so we do
    // not duplicate browser-specific installation state here.
    if (nativeInstall && !nativeInstall.hidden) {
      nativeInstall.click();
      setTimeout(syncState, 500);
      return;
    }

    message.textContent = 'このブラウザでは自動表示できません。Chromeの︙メニューから「アプリをインストール」または「ホーム画面に追加」を選んでください。';
  });

  if (nativeInstall) {
    new MutationObserver(syncState).observe(nativeInstall, { attributes: true, attributeFilter: ['hidden'] });
  }
  window.addEventListener('beforeinstallprompt', () => setTimeout(syncState, 0));
  window.addEventListener('appinstalled', syncState);
  window.matchMedia?.('(display-mode: standalone)').addEventListener?.('change', syncState);
  syncState();
})();