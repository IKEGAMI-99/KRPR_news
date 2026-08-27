(() => {
  const grid = document.querySelector('#newsGrid');
  if (!grid) return;

  const TIME_ZONE = 'Asia/Tokyo';
  const dateParts = new Intl.DateTimeFormat('ja-JP', {
    timeZone: TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
  const dateLabel = new Intl.DateTimeFormat('ja-JP', {
    timeZone: TIME_ZONE,
    month: 'long',
    day: 'numeric',
    weekday: 'short'
  });
  const yearLabel = new Intl.DateTimeFormat('ja-JP', {
    timeZone: TIME_ZONE,
    year: 'numeric'
  });
  const currentYear = yearLabel.format(new Date());

  let scheduled = false;

  function dateFromCard(card) {
    const time = card.querySelector('.published');
    const raw = time?.dateTime || '';
    const date = raw ? new Date(raw) : null;
    return date && !Number.isNaN(date.getTime()) ? date : null;
  }

  function dayKeyFromCard(card) {
    const date = dateFromCard(card);
    if (!date) return 'unknown';
    const parts = Object.fromEntries(
      dateParts.formatToParts(date)
        .filter((part) => part.type !== 'literal')
        .map((part) => [part.type, part.value])
    );
    return `${parts.year}-${parts.month}-${parts.day}`;
  }

  function dayLabel(card, key) {
    if (key === 'unknown') return '日時不明';
    const date = dateFromCard(card);
    if (!date) return '日時不明';
    const year = yearLabel.format(date);
    const base = dateLabel.format(date);
    return year === currentYear ? base : `${year}${base}`;
  }

  function decorate() {
    scheduled = false;
    grid.querySelectorAll('.day-divider, .month-divider').forEach((node) => node.remove());

    let previous = null;
    const cards = [...grid.querySelectorAll(':scope > .news-card')].filter((card) => !card.hidden);
    for (const card of cards) {
      const key = dayKeyFromCard(card);
      if (key === previous) continue;
      previous = key;
      const label = dayLabel(card, key);

      const divider = document.createElement('div');
      divider.className = 'day-divider';
      divider.dataset.day = key;
      divider.setAttribute('role', 'separator');
      divider.setAttribute('aria-label', label);
      divider.innerHTML = `
        <span class="day-sparkle" aria-hidden="true">✦</span>
        <span class="day-ribbon">${label}</span>
        <span class="day-sparkle day-sparkle-right" aria-hidden="true">✧</span>`;
      grid.insertBefore(divider, card);
    }
  }

  function scheduleDecorate(records = []) {
    if (records.length && records.every((record) =>
      [...record.addedNodes, ...record.removedNodes].every((node) =>
        node.nodeType !== 1 || node.classList?.contains('day-divider') || node.classList?.contains('month-divider')
      )
    )) return;
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(decorate);
  }

  const observer = new MutationObserver(scheduleDecorate);
  observer.observe(grid, { childList: true });
  window.addEventListener('kirapara:filters-changed', () => scheduleDecorate());
  scheduleDecorate();
})();
