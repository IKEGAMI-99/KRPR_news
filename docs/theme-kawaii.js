(() => {
  const meta = document.querySelector('meta[name="theme-color"]');
  if (!meta) return;

  const syncThemeColor = () => {
    const light = document.documentElement.dataset.theme === 'light';
    meta.setAttribute('content', light ? '#fff7fc' : '#120913');
  };

  new MutationObserver(syncThemeColor).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  });

  syncThemeColor();
})();
