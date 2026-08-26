(() => {
  const grid = document.querySelector('#newsGrid');
  if (!grid) return;

  let scheduled = false;

  function monthKeyFromCard(card) {
    const time = card.querySelector('.published');
    const raw = time?.dateTime || '';
    const date = raw ? new Date(raw) : null;
    if (!date || Number.isNaN(date.getTime())) return 'unknown';
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  }

  function monthLabel(key) {
    if (key === 'unknown') return '日時不明';
    const [year, month] = key.split('-').map(Number);
    return `${year}年 ${month}月`;
  }

  function decorate() {
    scheduled = false;
    grid.querySelectorAll('.month-divider').forEach((node) => node.remove());

    let previous = null;
    const cards = [...grid.querySelectorAll(':scope > .news-card')];
    for (const card of cards) {
      const key = monthKeyFromCard(card);
      if (key === previous) continue;
      previous = key;

      const divider = document.createElement('div');
      divider.className = 'month-divider';
      divider.dataset.month = key;
      divider.setAttribute('role', 'separator');
      divider.setAttribute('aria-label', monthLabel(key));
      divider.innerHTML = `
        <span class="month-sparkle" aria-hidden="true">✦</span>
        <span class="month-ribbon">${monthLabel(key)}</span>
        <span class="month-sparkle month-sparkle-right" aria-hidden="true">✧</span>`;
      grid.insertBefore(divider, card);
    }
  }

  function scheduleDecorate(records = []) {
    if (records.length && records.every((record) =>
      [...record.addedNodes, ...record.removedNodes].every((node) => node.nodeType !== 1 || node.classList?.contains('month-divider'))
    )) return;
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(decorate);
  }

  const observer = new MutationObserver(scheduleDecorate);
  observer.observe(grid, { childList: true });
  scheduleDecorate();
})();
