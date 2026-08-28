(() => {
  // Android/PWA back should close an open overlay before leaving the app.
  const TOKEN = 'kiraparaOverlay';
  let active = null;
  let closingFromPopstate = false;
  let overlayScrollY = 0;

  try { history.scrollRestoration = 'manual'; } catch {}

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
    overlayScrollY = window.scrollY;
    history.pushState({ ...(history.state || {}), [TOKEN]: kind }, '', location.href);
    active = kind;
  }

  function restoreOverlayScroll() {
    const root = document.documentElement;
    const previous = root.style.scrollBehavior;
    root.style.scrollBehavior = 'auto';
    window.scrollTo(0, overlayScrollY);
    requestAnimationFrame(() => {
      if (previous) root.style.scrollBehavior = previous;
      else root.style.removeProperty('scroll-behavior');
    });
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

  // Let each component close itself first, then consume only the synthetic
  // same-URL history entry. Manual scroll restoration prevents Chromium from
  // animating/restoring the page and making touch scrolling feel heavy after it.
  document.addEventListener('click', (event) => {
    if (closingFromPopstate || !history.state?.[TOKEN]) return;
    const target = event.target;
    const viewer = document.querySelector('#imageViewer');
    const closesViewer = Boolean(target?.closest?.('.viewer-close') || target === viewer);
    const closesMenu = Boolean(
      target?.closest?.('.link-menu-close') || target?.classList?.contains('menu-backdrop')
    );
    if (!closesViewer && !closesMenu) return;
    history.back();
  });

  window.addEventListener('popstate', () => {
    const kind = currentOverlay();
    if (kind) closeOverlay(kind);
    else active = null;
    requestAnimationFrame(restoreOverlayScroll);
  });
})();
