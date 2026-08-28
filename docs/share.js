(() => {
  const grid = document.querySelector('#newsGrid');
  if (!grid) return;

  const SHARE_LABEL = '共有';

  function canonicalUrl(value) {
    try {
      const url = new URL(value, location.href);
      return /^https?:$/.test(url.protocol) ? url.href : '';
    } catch {
      return '';
    }
  }

  function findItem(sourceUrl) {
    try {
      if (typeof state === 'undefined' || !Array.isArray(state.items)) return null;
      return state.items.find((item) => canonicalUrl(item?.sourceUrl) === sourceUrl) || null;
    } catch {
      return null;
    }
  }

  function japaneseTitle(card, item) {
    return String(item?.titleJa || item?.title || card.querySelector('.card-title')?.textContent || 'Kirapara News').trim();
  }

  function thumbnailUrl(card, item) {
    const candidates = [
      ...(Array.isArray(item?.imageUrls) ? item.imageUrls : []),
      item?.imageUrl,
      card.querySelector('.card-image')?.currentSrc,
      card.querySelector('.card-image')?.src,
    ];
    return candidates.map(canonicalUrl).find(Boolean) || '';
  }

  function fileExtension(type, url) {
    if (type === 'image/png') return 'png';
    if (type === 'image/webp') return 'webp';
    if (type === 'image/gif') return 'gif';
    if (type === 'image/avif') return 'avif';
    if (type === 'image/jpeg') return 'jpg';
    const match = String(url).match(/\.([a-z0-9]{2,5})(?:[?#]|$)/i);
    return match?.[1]?.toLowerCase() || 'jpg';
  }

  async function fetchThumbnailFile(url) {
    if (!url || typeof File === 'undefined') return null;
    try {
      const response = await fetch(url, {
        mode: 'cors',
        credentials: 'omit',
        referrerPolicy: 'no-referrer',
        cache: 'force-cache',
      });
      if (!response.ok) return null;
      const blob = await response.blob();
      if (!blob.type.startsWith('image/') || blob.size === 0 || blob.size > 15 * 1024 * 1024) return null;
      return new File([blob], `kirapara-news.${fileExtension(blob.type, url)}`, { type: blob.type });
    } catch {
      return null;
    }
  }

  async function copyFallback(title, sourceUrl) {
    const text = `${title}\n${sourceUrl}`;
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand('copy');
    area.remove();
    return copied;
  }

  function setTemporaryLabel(button, label) {
    const labelNode = button.querySelector('.share-button-label');
    if (!labelNode) return;
    labelNode.textContent = label;
    clearTimeout(button._shareLabelTimer);
    button._shareLabelTimer = setTimeout(() => {
      labelNode.textContent = SHARE_LABEL;
    }, 1600);
  }

  async function shareCard(card, button) {
    const sourceUrl = canonicalUrl(card.querySelector('.source-button')?.href);
    if (!sourceUrl) return;

    const item = findItem(sourceUrl);
    const title = japaneseTitle(card, item);
    const thumbnail = thumbnailUrl(card, item);

    button.disabled = true;
    button.classList.add('is-sharing');

    try {
      if (navigator.share) {
        const file = await fetchThumbnailFile(thumbnail);
        const canShareFile = file && navigator.canShare?.({ files: [file] });

        if (canShareFile) {
          try {
            await navigator.share({
              title,
              text: title,
              url: sourceUrl,
              files: [file],
            });
          } catch (error) {
            if (error?.name === 'AbortError') return;
            await navigator.share({
              title,
              text: `${title}\n${sourceUrl}`,
              files: [file],
            });
          }
        } else {
          await navigator.share({ title, text: title, url: sourceUrl });
        }
        setTemporaryLabel(button, '共有済み');
        return;
      }

      if (await copyFallback(title, sourceUrl)) setTemporaryLabel(button, 'コピー済み');
    } catch (error) {
      if (error?.name !== 'AbortError') {
        try {
          if (await copyFallback(title, sourceUrl)) setTemporaryLabel(button, 'コピー済み');
        } catch {
          setTemporaryLabel(button, '共有失敗');
        }
      }
    } finally {
      button.disabled = false;
      button.classList.remove('is-sharing');
    }
  }

  function makeShareButton() {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'share-button';
    button.setAttribute('aria-label', 'SNSで共有');
    button.title = 'SNSで共有';
    button.innerHTML = `
      <svg class="share-button-icon" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="18" cy="5" r="2.6"></circle>
        <circle cx="6" cy="12" r="2.6"></circle>
        <circle cx="18" cy="19" r="2.6"></circle>
        <path d="M8.4 10.8 15.7 6.4M8.4 13.2l7.3 4.4"></path>
      </svg>
      <span class="share-button-label">${SHARE_LABEL}</span>`;
    return button;
  }

  function attachShareButton(card) {
    if (card.querySelector('.share-button')) return;
    const actions = card.querySelector('.card-actions');
    const source = card.querySelector('.source-button');
    if (!actions || !source) return;

    const button = makeShareButton();
    button.addEventListener('click', () => shareCard(card, button));
    actions.insertBefore(button, source);
  }

  function attachAll() {
    grid.querySelectorAll('.news-card').forEach(attachShareButton);
  }

  document.addEventListener('kirapara:rendered', attachAll);
  attachAll();
})();
