(() => {
  const grid = document.querySelector('#newsGrid');
  if (!grid) return;

  function repairCard(card) {
    const body = card.querySelector('.card-body');
    const button = card.querySelector('.more-button');
    if (!body || !button || !button.hidden || button.dataset.overflowFix === '1') return;

    requestAnimationFrame(() => {
      if (!button.hidden || button.dataset.overflowFix === '1') return;
      const clipped = body.scrollHeight > body.clientHeight + 2;
      if (!clipped) return;

      button.hidden = false;
      button.dataset.overflowFix = '1';
      button.addEventListener('click', () => {
        const expanded = card.classList.toggle('is-expanded');
        button.textContent = expanded ? '閉じる' : '続きを読む';
      });
    });
  }

  function repairAll() {
    grid.querySelectorAll('.news-card').forEach(repairCard);
  }

  const observer = new MutationObserver(repairAll);
  observer.observe(grid, { childList: true, subtree: false });
  window.addEventListener('resize', repairAll, { passive: true });
  repairAll();
})();
