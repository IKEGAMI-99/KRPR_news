(() => {
  // Swipe navigation for the full-screen image viewer.
  // Horizontal gestures change images; vertical gestures remain available for
  // scrolling tall images. Using the existing nav buttons keeps swipe behavior
  // identical to keyboard/button navigation, including wrap-around.
  const SWIPE_DISTANCE = 52;
  const DIRECTION_RATIO = 1.2;
  const SWIPE_COOLDOWN_MS = 180;

  let activePointerId = null;
  let startX = 0;
  let startY = 0;
  let lastX = 0;
  let lastY = 0;
  let lastSwipeAt = 0;

  function openViewer() {
    const viewer = document.querySelector('#imageViewer');
    return viewer && !viewer.hidden ? viewer : null;
  }

  function resetGesture() {
    activePointerId = null;
    startX = 0;
    startY = 0;
    lastX = 0;
    lastY = 0;
  }

  function canStart(event, viewer) {
    if (!viewer || activePointerId !== null) return false;
    if (event.pointerType === 'mouse' && event.button !== 0) return false;
    if (event.target?.closest?.('.viewer-close, .viewer-nav, .viewer-count')) return false;
    return Boolean(event.target?.closest?.('.viewer-image, .viewer-figure'));
  }

  document.addEventListener('pointerdown', (event) => {
    const viewer = openViewer();
    if (!canStart(event, viewer)) return;

    activePointerId = event.pointerId;
    startX = lastX = event.clientX;
    startY = lastY = event.clientY;
  }, { passive: true });

  document.addEventListener('pointermove', (event) => {
    if (event.pointerId !== activePointerId) return;
    lastX = event.clientX;
    lastY = event.clientY;
  }, { passive: true });

  document.addEventListener('pointerup', (event) => {
    if (event.pointerId !== activePointerId) return;

    const viewer = openViewer();
    const endX = Number.isFinite(event.clientX) ? event.clientX : lastX;
    const endY = Number.isFinite(event.clientY) ? event.clientY : lastY;
    const dx = endX - startX;
    const dy = endY - startY;
    const absX = Math.abs(dx);
    const absY = Math.abs(dy);

    resetGesture();

    if (!viewer) return;
    if (absX < SWIPE_DISTANCE || absX <= absY * DIRECTION_RATIO) return;

    const previous = viewer.querySelector('.viewer-prev');
    const next = viewer.querySelector('.viewer-next');
    if ((!previous || previous.hidden) && (!next || next.hidden)) return;

    const now = performance.now();
    if (now - lastSwipeAt < SWIPE_COOLDOWN_MS) return;
    lastSwipeAt = now;

    if (dx < 0) next?.click();
    else previous?.click();
  }, { passive: true });

  document.addEventListener('pointercancel', (event) => {
    if (event.pointerId === activePointerId) resetGesture();
  }, { passive: true });
})();
