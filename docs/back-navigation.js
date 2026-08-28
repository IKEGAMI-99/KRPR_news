(() => {
  // Android/PWA の戻る操作は、ページを閉じる前に開いているUIを閉じる。
  // 各オーバーレイを開いた時だけ履歴を1段積み、戻るでその履歴を消費する。
  const TOKEN = 'kiraparaOverlay';
  let active = null;
  let closingFromPopstate = false;

  const isMenuOpen = () => document.querySelector('.link-menu')?.classList.contains('is-open');
  const isViewerOpen = () => {
    const viewer = document.querySelector('#imageViewer');
    return Boolean(viewer && !viewer.hidden);
  };

  function currentOverlay() {
    if (isViewerOpen()) return 'viewer';
    if (isMenuOpen()) return 'menu';
    return null;
  }

  function pushOverlay(kind) {
    if (!kind || active === kind || history.state?.[TOKEN] === kind) {
      active = kind || active;
      return;
    }
    history.pushState({ ...(history.state || {}), [TOKEN]: kind }, '', location.href);
    active = kind;
  }

  function closeOverlay(kind) {
    closingFromPopstate = true;
    try {
      if (kind === 'viewer' && isViewerOpen()) {
        document.querySelector('#imageViewer .viewer-close')?.click();
      } else if (kind === 'menu' && isMenuOpen()) {
        document.querySelector('.link-menu-close')?.click();
      }
    } finally {
      closingFromPopstate = false;
      active = currentOverlay();
    }
  }

  // app.js / menu.js が動的にUIを開くため、状態変化を監視して履歴を積む。
  const observer = new MutationObserver(() => {
    if (closingFromPopstate) return;
    const kind = currentOverlay();
    if (kind && active !== kind) pushOverlay(kind);
    if (!kind) active = null;
  });
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['class', 'hidden'],
  });

  // ×、背景タップなど「画面内で閉じる」操作では、まず通常のクリック処理で
  // UIを即座に閉じる。その後にオーバーレイ用の履歴だけを消費する。
  // capture + stopImmediatePropagation で先回りすると app.js 側の closeViewer()
  // まで止めてしまうため、document の bubble フェーズで後処理する。
  document.addEventListener('click', (event) => {
    if (closingFromPopstate || !history.state?.[TOKEN]) return;
    const target = event.target;
    const viewer = document.querySelector('#imageViewer');
    const closesViewer = Boolean(
      target?.closest?.('.viewer-close') || target === viewer
    );
    const closesMenu = Boolean(
      target?.closest?.('.link-menu-close') || target?.classList?.contains('menu-backdrop')
    );
    if (!closesViewer && !closesMenu) return;

    // The component's own click handler has already run by the time this bubbles
    // to document, so this only removes the synthetic same-URL history entry.
    if (history.state?.[TOKEN]) history.back();
  });

  window.addEventListener('popstate', () => {
    const kind = currentOverlay();
    if (kind) closeOverlay(kind);
    else active = null;
  });
})();
