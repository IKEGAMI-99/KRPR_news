(() => {
  const body = document.querySelector('.link-menu-body');
  if (!body) return;

  const nativeInstall = document.querySelector('#installButton');
  const devSection = body.querySelector('.developer-section');

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
  body.prepend(section);

  // Developer tools belong at the very bottom, after links and notes.
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
