(() => {
  const PRESETS = [
    { key: 'preset:cute', emoji: '💖', label: 'かわいい' },
    { key: 'preset:god', emoji: '🔥', label: '神' },
    { key: 'preset:watch', emoji: '👀', label: '気になる' },
    { key: 'preset:helpful', emoji: '🙏', label: '助かる' },
  ];
  const CUSTOM_EMOJIS = [
    '👍', '❤️', '😂', '🤣', '😍', '🥰', '😊', '😭', '😢', '😮', '😱', '🤯',
    '🤔', '🫡', '👏', '🙌', '🙏', '✨', '⭐', '🌟', '💫', '🔥', '💯', '🎉',
    '🎀', '💎', '👗', '👑', '🫶', '💖', '💕', '💜', '🩷', '🩵', '🤍', '🖤',
    '👀', '📌', '📰', '⚠️', '✅', '❓', '💡', '🚀', '🌈', '🍬', '🦋', '🌸',
  ];
  const STORAGE_KEY = 'kirapara-article-reactions-v1';
  const CLIENT_KEY = 'kirapara-reaction-client-v1';
  const stateByArticle = new Map();
  let renderGeneration = 0;

  function storageGet(key) {
    try { return localStorage.getItem(key); } catch { return null; }
  }

  function storageSet(key, value) {
    try { localStorage.setItem(key, value); return true; } catch { return false; }
  }

  function getClientId() {
    const saved = storageGet(CLIENT_KEY);
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(saved || '')) return saved;
    const id = globalThis.crypto?.randomUUID?.() || `00000000-0000-4000-8000-${Math.random().toString(16).slice(2).padEnd(12, '0').slice(0, 12)}`;
    storageSet(CLIENT_KEY, id);
    return id;
  }

  function supabaseConfig() {
    const raw = globalThis.KIRAPARA_SUPABASE || {};
    const url = String(raw.url || '').trim().replace(/\/+$/, '');
    const key = String(raw.key || raw.anonKey || raw.publishableKey || '').trim();
    return /^https:\/\//.test(url) && key ? { url, key } : null;
  }

  function emptyArticleState() {
    const map = new Map();
    for (const preset of PRESETS) map.set(preset.key, { ...preset, count: 0, mine: false });
    return map;
  }

  function ensureArticleState(articleId) {
    if (!stateByArticle.has(articleId)) stateByArticle.set(articleId, emptyArticleState());
    return stateByArticle.get(articleId);
  }

  function localData() {
    try {
      const parsed = JSON.parse(storageGet(STORAGE_KEY) || '{}');
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch { return {}; }
  }

  function saveLocalData(data) {
    storageSet(STORAGE_KEY, JSON.stringify(data));
  }

  function loadLocal(articleIds) {
    const data = localData();
    for (const articleId of articleIds) {
      const map = emptyArticleState();
      const saved = data[articleId] && typeof data[articleId] === 'object' ? data[articleId] : {};
      for (const [key, value] of Object.entries(saved)) {
        if (!value || typeof value !== 'object') continue;
        const emoji = String(value.emoji || '').slice(0, 32);
        const label = String(value.label || '').slice(0, 32);
        if (!emoji) continue;
        map.set(key, { key, emoji, label, count: 1, mine: true });
      }
      stateByArticle.set(articleId, map);
    }
  }

  async function apiFetch(path, options = {}) {
    const config = supabaseConfig();
    if (!config) throw new Error('Supabase is not configured');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 7000);
    try {
      const response = await fetch(`${config.url}/rest/v1/${path}`, {
        ...options,
        signal: controller.signal,
        headers: {
          apikey: config.key,
          Authorization: `Bearer ${config.key}`,
          'X-Client-ID': getClientId(),
          ...(options.body ? { 'Content-Type': 'application/json' } : {}),
          ...(options.headers || {}),
        },
      });
      if (!response.ok) throw new Error(`Supabase HTTP ${response.status}`);
      if (response.status === 204 || response.headers.get('content-length') === '0') return null;
      const text = await response.text();
      return text ? JSON.parse(text) : null;
    } finally {
      clearTimeout(timeout);
    }
  }

  function inFilter(values) {
    return `in.(${values.map((value) => JSON.stringify(String(value))).join(',')})`;
  }

  async function loadShared(articleIds) {
    if (!articleIds.length) return;
    const ids = inFilter(articleIds);
    const clientId = getClientId();
    const countsQuery = new URLSearchParams({
      select: 'article_id,reaction_key,emoji,label,count',
      article_id: ids,
    });
    const mineQuery = new URLSearchParams({
      select: 'article_id,reaction_key,emoji,label',
      article_id: ids,
      client_id: `eq.${clientId}`,
    });
    const [counts, mine] = await Promise.all([
      apiFetch(`article_reaction_counts?${countsQuery}`),
      apiFetch(`article_reactions?${mineQuery}`),
    ]);

    for (const articleId of articleIds) stateByArticle.set(articleId, emptyArticleState());
    for (const row of Array.isArray(counts) ? counts : []) {
      const articleId = String(row.article_id || '');
      const key = String(row.reaction_key || '');
      const emoji = String(row.emoji || '');
      if (!articleId || !key || !emoji || !stateByArticle.has(articleId)) continue;
      stateByArticle.get(articleId).set(key, {
        key,
        emoji,
        label: String(row.label || ''),
        count: Math.max(0, Number(row.count) || 0),
        mine: false,
      });
    }
    for (const row of Array.isArray(mine) ? mine : []) {
      const articleId = String(row.article_id || '');
      const key = String(row.reaction_key || '');
      if (!articleId || !key || !stateByArticle.has(articleId)) continue;
      const map = stateByArticle.get(articleId);
      const existing = map.get(key) || {
        key,
        emoji: String(row.emoji || ''),
        label: String(row.label || ''),
        count: 1,
        mine: false,
      };
      existing.mine = true;
      if (!existing.count) existing.count = 1;
      map.set(key, existing);
    }
  }

  function reactionFromEmoji(emoji) {
    return { key: `emoji:${emoji}`, emoji, label: '' };
  }

  function firstGrapheme(value) {
    const input = String(value || '').trim();
    if (!input) return '';
    try {
      if (Intl.Segmenter) {
        const segmenter = new Intl.Segmenter('ja', { granularity: 'grapheme' });
        return segmenter.segment(input)[Symbol.iterator]().next().value?.segment || '';
      }
    } catch {}
    return Array.from(input).slice(0, 4).join('');
  }

  function looksLikeEmoji(value) {
    if (!value || value.length > 32) return false;
    try { return /\p{Extended_Pictographic}|\p{Regional_Indicator}/u.test(value); }
    catch { return value.codePointAt(0) > 0x2000; }
  }

  async function sharedToggle(articleId, reaction, currentlyMine) {
    const clientId = getClientId();
    if (currentlyMine) {
      const query = new URLSearchParams({
        article_id: `eq.${articleId}`,
        reaction_key: `eq.${reaction.key}`,
        client_id: `eq.${clientId}`,
      });
      await apiFetch(`article_reactions?${query}`, { method: 'DELETE' });
      return;
    }
    await apiFetch('article_reactions', {
      method: 'POST',
      headers: { Prefer: 'resolution=ignore-duplicates,return=minimal' },
      body: JSON.stringify({
        article_id: articleId,
        reaction_key: reaction.key,
        emoji: reaction.emoji,
        label: reaction.label || '',
        client_id: clientId,
      }),
    });
  }

  function localToggle(articleId, reaction, currentlyMine) {
    const data = localData();
    const article = data[articleId] && typeof data[articleId] === 'object' ? data[articleId] : {};
    if (currentlyMine) delete article[reaction.key];
    else article[reaction.key] = { emoji: reaction.emoji, label: reaction.label || '' };
    if (Object.keys(article).length) data[articleId] = article;
    else delete data[articleId];
    saveLocalData(data);
  }

  function currentReaction(articleId, reaction) {
    return ensureArticleState(articleId).get(reaction.key) || {
      ...reaction,
      count: 0,
      mine: false,
    };
  }

  function updateOptimistically(articleId, reaction, nextMine) {
    const map = ensureArticleState(articleId);
    const current = currentReaction(articleId, reaction);
    map.set(reaction.key, {
      ...current,
      ...reaction,
      mine: nextMine,
      count: Math.max(0, (Number(current.count) || 0) + (nextMine ? 1 : -1)),
    });
  }

  function showTransientError(card) {
    const bar = card.querySelector('.article-reactions');
    if (!bar) return;
    bar.classList.add('has-error');
    bar.dataset.status = '保存できませんでした';
    setTimeout(() => {
      bar.classList.remove('has-error');
      delete bar.dataset.status;
    }, 2400);
  }

  async function toggleReaction(card, articleId, reaction) {
    const bar = card.querySelector('.article-reactions');
    if (!bar || bar.dataset.busy === 'true') return;
    const before = currentReaction(articleId, reaction);
    const nextMine = !before.mine;
    updateOptimistically(articleId, reaction, nextMine);
    renderReactionBar(card, articleId);
    bar.dataset.busy = 'true';
    try {
      if (supabaseConfig()) {
        await sharedToggle(articleId, reaction, before.mine);
        await loadShared([articleId]);
      } else {
        localToggle(articleId, reaction, before.mine);
        loadLocal([articleId]);
      }
    } catch {
      const map = ensureArticleState(articleId);
      map.set(reaction.key, before);
      showTransientError(card);
    } finally {
      const liveBar = card.querySelector('.article-reactions');
      if (liveBar) liveBar.dataset.busy = 'false';
      renderReactionBar(card, articleId);
    }
  }

  function createReactionButton(card, articleId, reaction) {
    const state = currentReaction(articleId, reaction);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `reaction-chip${state.mine ? ' is-selected' : ''}`;
    button.dataset.reactionKey = reaction.key;
    button.setAttribute('aria-pressed', state.mine ? 'true' : 'false');
    const name = reaction.label ? `${reaction.emoji} ${reaction.label}` : reaction.emoji;
    button.setAttribute('aria-label', `${name}${state.count ? ` ${state.count}件` : ''}`);

    const emoji = document.createElement('span');
    emoji.className = 'reaction-emoji';
    emoji.textContent = reaction.emoji;
    button.appendChild(emoji);
    if (reaction.label) {
      const label = document.createElement('span');
      label.className = 'reaction-label';
      label.textContent = reaction.label;
      button.appendChild(label);
    }
    if (state.count > 0) {
      const count = document.createElement('span');
      count.className = 'reaction-count';
      count.textContent = String(state.count);
      button.appendChild(count);
    }
    button.addEventListener('click', () => toggleReaction(card, articleId, reaction));
    return button;
  }

  function closeAllPickers(except = null) {
    document.querySelectorAll('.reaction-picker.is-open').forEach((picker) => {
      if (picker === except) return;
      picker.classList.remove('is-open');
      picker.hidden = true;
      picker.closest('.article-reactions')?.querySelector('.reaction-add')?.setAttribute('aria-expanded', 'false');
    });
  }

  function createPicker(card, articleId) {
    const picker = document.createElement('div');
    picker.className = 'reaction-picker';
    picker.hidden = true;
    picker.setAttribute('role', 'dialog');
    picker.setAttribute('aria-label', '絵文字リアクションを追加');

    const title = document.createElement('div');
    title.className = 'reaction-picker-title';
    title.textContent = '絵文字を追加';

    const grid = document.createElement('div');
    grid.className = 'reaction-emoji-grid';
    for (const emojiValue of CUSTOM_EMOJIS) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'reaction-emoji-choice';
      button.textContent = emojiValue;
      button.setAttribute('aria-label', `${emojiValue} を追加`);
      button.addEventListener('click', () => {
        toggleReaction(card, articleId, reactionFromEmoji(emojiValue));
        closeAllPickers();
      });
      grid.appendChild(button);
    }

    const custom = document.createElement('form');
    custom.className = 'reaction-custom-form';
    const input = document.createElement('input');
    input.type = 'text';
    input.inputMode = 'text';
    input.autocomplete = 'off';
    input.maxLength = 32;
    input.placeholder = '好きな絵文字を入力';
    input.setAttribute('aria-label', '好きな絵文字を入力');
    const submit = document.createElement('button');
    submit.type = 'submit';
    submit.textContent = '追加';
    const hint = document.createElement('span');
    hint.className = 'reaction-custom-hint';
    hint.textContent = 'スマホの絵文字キーボードやコピペでもOK';
    custom.append(input, submit, hint);
    custom.addEventListener('submit', (event) => {
      event.preventDefault();
      const emoji = firstGrapheme(input.value);
      if (!looksLikeEmoji(emoji)) {
        hint.textContent = '絵文字を1つ入力してください';
        custom.classList.add('is-invalid');
        return;
      }
      custom.classList.remove('is-invalid');
      toggleReaction(card, articleId, reactionFromEmoji(emoji));
      input.value = '';
      closeAllPickers();
    });

    picker.append(title, grid, custom);
    return picker;
  }

  function renderReactionBar(card, articleId) {
    let bar = card.querySelector('.article-reactions');
    if (!bar) {
      bar = document.createElement('div');
      bar.className = 'article-reactions';
      bar.dataset.articleId = articleId;
      const actions = card.querySelector('.card-actions');
      if (actions) actions.insertAdjacentElement('beforebegin', bar);
      else card.querySelector('.card-content')?.appendChild(bar);
    }
    const wasBusy = bar.dataset.busy === 'true';
    const map = ensureArticleState(articleId);
    bar.replaceChildren();
    bar.dataset.busy = wasBusy ? 'true' : 'false';

    const chips = document.createElement('div');
    chips.className = 'reaction-chips';
    for (const preset of PRESETS) chips.appendChild(createReactionButton(card, articleId, preset));
    for (const reaction of [...map.values()].filter((item) => !item.key.startsWith('preset:') && item.count > 0)) {
      chips.appendChild(createReactionButton(card, articleId, reaction));
    }

    const add = document.createElement('button');
    add.type = 'button';
    add.className = 'reaction-add';
    add.textContent = '＋';
    add.title = '絵文字を追加';
    add.setAttribute('aria-label', '絵文字を追加');
    add.setAttribute('aria-expanded', 'false');
    const picker = createPicker(card, articleId);
    add.addEventListener('click', (event) => {
      event.stopPropagation();
      const opening = picker.hidden;
      closeAllPickers(opening ? picker : null);
      picker.hidden = !opening;
      picker.classList.toggle('is-open', opening);
      add.setAttribute('aria-expanded', opening ? 'true' : 'false');
      if (opening) picker.querySelector('.reaction-emoji-choice')?.focus();
    });

    const mode = document.createElement('span');
    mode.className = 'reaction-mode';
    mode.textContent = supabaseConfig() ? 'みんなのリアクション' : 'この端末のみ';
    mode.title = supabaseConfig()
      ? 'リアクション数はKirapara News利用者間で共有されます'
      : 'Supabase接続前のため、この端末だけに保存されます';

    bar.append(chips, add, picker, mode);
  }

  async function attachAll() {
    const generation = ++renderGeneration;
    const cards = [...document.querySelectorAll('#newsGrid .news-card')];
    const articleIds = [...new Set(cards.map((card) => card.dataset.articleId || card.dataset.sourceUrl || '').filter(Boolean))];
    for (const card of cards) {
      const articleId = card.dataset.articleId || card.dataset.sourceUrl || '';
      if (!articleId) continue;
      ensureArticleState(articleId);
      renderReactionBar(card, articleId);
    }
    if (!articleIds.length) return;

    try {
      if (supabaseConfig()) await loadShared(articleIds);
      else loadLocal(articleIds);
    } catch {
      loadLocal(articleIds);
    }
    if (generation !== renderGeneration) return;
    for (const card of cards) {
      const articleId = card.dataset.articleId || card.dataset.sourceUrl || '';
      if (articleId && card.isConnected) renderReactionBar(card, articleId);
    }
  }

  document.addEventListener('kirapara:rendered', attachAll);
  document.addEventListener('click', (event) => {
    if (!event.target.closest('.article-reactions')) closeAllPickers();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeAllPickers();
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attachAll, { once: true });
  else attachAll();
})();
