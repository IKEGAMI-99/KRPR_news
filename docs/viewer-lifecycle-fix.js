(() => {
  // The image viewer used to rely only on the hidden attribute when closing.
  // On Android/PWA an older cached viewer stylesheet could still keep that
  // element painted, leaving the backdrop, arrows and a broken image behind.
  // Physically removing a closed viewer avoids any CSS/cache ambiguity; app.js
  // will recreate it on the next image open.

  function removeClosedViewer() {
    const viewer = document.querySelector('#imageViewer');
    if (!viewer || !viewer.hidden) return;
    viewer.querySelector('.viewer-image')?.removeAttribute('src');
    viewer.remove();
    document.body.classList.remove('viewer-open');
  }

  function finishCloseSoon() {
    // Let app.js and back-navigation.js finish their normal click/history work
    // first, then make the closed state unambiguous by removing the overlay.
    setTimeout(() => {
      const viewer = document.querySelector('#imageViewer');
      if (!viewer) {
        document.body.classList.remove('viewer-open');
        return;
      }
      viewer.hidden = true;
      viewer.querySelector('.viewer-image')?.removeAttribute('src');
      viewer.remove();
      document.body.classList.remove('viewer-open');
    }, 0);
  }

  document.addEventListener('click', (event) => {
    const viewer = document.querySelector('#imageViewer');
    if (!viewer) return;
    const target = event.target;
    if (target?.closest?.('.viewer-close') || target === viewer) {
      finishCloseSoon();
    }
  }, true);

  const observer = new MutationObserver(removeClosedViewer);
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['hidden'],
  });

  window.addEventListener('popstate', () => setTimeout(removeClosedViewer, 0));
})();
