(() => {
  // Viewer-specific Android/PWA fixes live here so app.js can stay simple.
  // 1) Position normal images against the real visual viewport center.
  // 2) Treat very tall images as scrollable long images.
  // 3) Fully tear down the viewer and restore page scrolling after close.

  const EMPTY_IMAGE = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';
  let savedScrollY = 0;

  try { history.scrollRestoration = 'manual'; } catch {}

  function viewportSize() {
    return {
      width: window.visualViewport?.width || window.innerWidth,
      height: window.visualViewport?.height || window.innerHeight,
    };
  }

  function classifyViewer(viewer) {
    if (!viewer || viewer.hidden || !viewer.isConnected) return;
    const image = viewer.querySelector('.viewer-image');
    if (!image?.naturalWidth || !image?.naturalHeight) return;

    const { width, height } = viewportSize();
    const displayWidth = Math.min(width, 1100);
    const projectedImageHeight = displayWidth * (image.naturalHeight / image.naturalWidth);
    const projectedGroupHeight = projectedImageHeight + 42; // count + gap
    const centered = projectedGroupHeight <= Math.max(240, height - 120);

    viewer.classList.toggle('viewer-centered', centered);
    viewer.classList.toggle('viewer-tall', !centered);
    if (centered) viewer.scrollTop = 0;
  }

  function bindViewer(viewer) {
    if (!viewer || viewer.dataset.viewerFixBound === '1') return;
    viewer.dataset.viewerFixBound = '1';
    savedScrollY = window.scrollY;

    const image = viewer.querySelector('.viewer-image');
    image?.addEventListener('load', () => requestAnimationFrame(() => classifyViewer(viewer)));
    if (image?.complete && image.naturalWidth) requestAnimationFrame(() => classifyViewer(viewer));
  }

  function restorePageScroll() {
    document.body.classList.remove('viewer-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('touch-action');
    document.documentElement.style.removeProperty('overflow');

    const active = document.activeElement;
    if (active?.matches?.('.card-image-link, .inline-image-slide')) active.blur();

    const root = document.documentElement;
    const previousBehavior = root.style.scrollBehavior;
    root.style.scrollBehavior = 'auto';
    if (Number.isFinite(savedScrollY)) window.scrollTo(0, savedScrollY);
    requestAnimationFrame(() => {
      if (previousBehavior) root.style.scrollBehavior = previousBehavior;
      else root.style.removeProperty('scroll-behavior');
    });
  }

  function destroyViewer(viewer) {
    if (viewer?.isConnected) {
      const image = viewer.querySelector('.viewer-image');
      if (image) {
        image.onload = null;
        image.onerror = null;
        // Replace the decoded large bitmap before removing the node. This helps
        // Chromium/WebAPK release memory sooner after opening very large images.
        try { image.src = EMPTY_IMAGE; } catch {}
      }
      viewer.remove();
    }
    restorePageScroll();
  }

  function finishCloseSoon() {
    setTimeout(() => destroyViewer(document.querySelector('#imageViewer')), 0);
  }

  document.addEventListener('click', (event) => {
    const viewer = document.querySelector('#imageViewer');
    if (!viewer) return;
    const target = event.target;
    if (target?.closest?.('.viewer-close') || target === viewer) finishCloseSoon();
  }, true);

  const observer = new MutationObserver(() => {
    const viewer = document.querySelector('#imageViewer');
    if (!viewer) return;
    if (viewer.hidden) {
      destroyViewer(viewer);
      return;
    }
    bindViewer(viewer);
    classifyViewer(viewer);
  });

  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['hidden', 'src'],
  });

  const reclassify = () => classifyViewer(document.querySelector('#imageViewer'));
  window.addEventListener('resize', reclassify, { passive: true });
  window.visualViewport?.addEventListener('resize', reclassify, { passive: true });
  window.addEventListener('popstate', () => setTimeout(() => {
    const viewer = document.querySelector('#imageViewer');
    if (viewer?.hidden) destroyViewer(viewer);
    else if (!viewer) restorePageScroll();
  }, 0));
})();
