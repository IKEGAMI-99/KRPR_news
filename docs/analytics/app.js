const byId = (id) => document.getElementById(id);
const formatNumber = (value) => new Intl.NumberFormat('ja-JP').format(Number(value || 0));
const safeItems = (items) => Array.isArray(items) ? items : [];

function showEmpty(root) {
  const message = document.createElement('p');
  message.className = 'muted';
  message.textContent = 'データなし';
  root.replaceChildren(message);
}

function renderBars(id, items) {
  const root = byId(id);
  const values = safeItems(items).slice(0, 10);
  if (!values.length) { showEmpty(root); return; }
  root.replaceChildren();
  const max = Math.max(...values.map((item) => Number(item?.value || 0)), 1);
  for (const item of values) {
    const labelText = String(item?.label || '—');
    const value = Math.max(0, Number(item?.value || 0));
    const row = document.createElement('div');
    row.className = 'bar-row';
    const label = document.createElement('span');
    label.title = labelText;
    label.textContent = labelText;
    const track = document.createElement('div');
    track.className = 'bar-track';
    const fill = document.createElement('div');
    fill.className = 'bar-fill';
    fill.style.width = `${Math.min(100, Math.max(2, value / max * 100))}%`;
    track.appendChild(fill);
    const amount = document.createElement('span');
    amount.className = 'bar-value';
    amount.textContent = formatNumber(value);
    row.append(label, track, amount);
    root.appendChild(row);
  }
}

function renderPages(items) {
  const root = byId('pages');
  const values = safeItems(items).slice(0, 10);
  if (!values.length) { showEmpty(root); return; }
  root.replaceChildren();
  values.forEach((item, index) => {
    const labelText = String(item?.label || '—');
    const row = document.createElement('div');
    row.className = 'rank-row';
    const rank = document.createElement('span');
    rank.className = 'rank-num';
    rank.textContent = String(index + 1);
    const label = document.createElement('span');
    label.className = 'rank-title';
    label.title = labelText;
    label.textContent = labelText;
    const value = document.createElement('span');
    value.className = 'rank-value';
    value.textContent = formatNumber(item?.value);
    row.append(rank, label, value);
    root.appendChild(row);
  });
}

function renderTrend(items) {
  const root = byId('trendChart');
  const values = safeItems(items);
  if (!values.length) { showEmpty(root); return; }
  root.replaceChildren();
  const max = Math.max(...values.map((item) => Number(item?.value || 0)), 1);
  for (const item of values) {
    const value = Math.max(0, Number(item?.value || 0));
    const bar = document.createElement('div');
    bar.className = 'trend-bar';
    bar.style.height = `${Math.min(100, Math.max(3, value / max * 100))}%`;
    const tooltip = document.createElement('span');
    tooltip.textContent = `${String(item?.label || '—')}: ${formatNumber(value)}`;
    bar.appendChild(tooltip);
    root.appendChild(bar);
  }
}

async function load() {
  try {
    const response = await fetch(`./data.json?ts=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const ready = Boolean(data?.ready);
    byId('todayViews').textContent = ready ? formatNumber(data.summary?.todayViews) : '—';
    byId('weekViews').textContent = ready ? formatNumber(data.summary?.weekViews) : '—';
    byId('monthViews').textContent = ready ? formatNumber(data.summary?.monthViews) : '—';
    byId('monthUsers').textContent = ready ? formatNumber(data.summary?.monthUsers) : '—';
    byId('updatedAt').textContent = data?.updatedAt
      ? `最終更新 ${new Date(data.updatedAt).toLocaleString('ja-JP')}`
      : 'データ取得中…';
    renderTrend(data?.trend);
    renderPages(data?.pages);
    renderBars('referrers', data?.referrers);
    renderBars('regions', data?.regions);
    renderBars('devices', data?.devices);
  } catch {
    byId('updatedAt').textContent = 'データを読み込めませんでした';
  }
}

load();
