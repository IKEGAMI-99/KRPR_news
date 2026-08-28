(() => {
  const SHARE_STATUS_IDLE = '文章＋紹介画像を共有します';
  const SHARE_IMAGE_PARTS = Array.from(
    { length: 6 },
    (_, index) => `./media/share/kirapara-news-share.b64.${index}`
  );
  const SHARE_TEXT = [
    'きらめきパラダイスの最新情報を、これひとつで ✨',
    '🇯🇵日本・🇨🇳中国・🇰🇷韓国・🌐グローバルのニュースをまとめてチェック。',
    'AI翻訳＆要約で海外情報もサクッと読める「Kirapara News」💫',
    '#きらめきパラダイス #KiraparaNews',
  ].join('\n');

  const installSection = document.querySelector('.menu-install-section');
  if (installSection && !document.querySelector('.menu-discord-section')) {
    const discord = document.createElement('section');
    discord.className = 'menu-analysis-section menu-discord-section';
    discord.innerHTML = `
      <a class="menu-analysis-action" href="https://discord.gg/wDNNqt3H4" target="_blank" rel="noopener noreferrer" aria-label="Discordに参加する">
        <span class="menu-analysis-icon" aria-hidden="true">💬</span>
        <span class="menu-analysis-copy">
          <span><strong>Discordに参加する</strong></span>
          <small>Kirapara NewsのDiscordを開く</small>
        </span>
        <span class="menu-analysis-arrow" aria-hidden="true">↗</span>
      </a>`;
    installSection.insertAdjacentElement('afterend', discord);
  }

  let statusResetTimer = null;
  let shareImageFile = null;

  function appShareUrl() {
    const url = new URL('./', window.location.href);
    url.search = '';
    url.hash = '';
    return url.href;
  }

  function setShareStatus(text, success = false) {
    const status = document.querySelector('.menu-share-status');
    const arrow = document.querySelector('.menu-share-arrow');
    if (!status || !arrow) return;

    clearTimeout(statusResetTimer);
    status.textContent = text;
    arrow.textContent = success ? '✓' : '›';
    statusResetTimer = setTimeout(() => {
      status.textContent = SHARE_STATUS_IDLE;
      arrow.textContent = '›';
    }, 2200);
  }

  function decodeBase64(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }

  async function buildShareImageFile() {
    const responses = await Promise.all(
      SHARE_IMAGE_PARTS.map(async (path) => {
        const response = await fetch(path, { cache: 'force-cache' });
        if (!response.ok) throw new Error(`share image fetch failed: ${response.status}`);
        return response.text();
      })
    );

    const base64 = responses.map((part) => part.trim()).join('');
    const bytes = decodeBase64(base64);
    return new File([bytes], 'kirapara-news.jpg', { type: 'image/jpeg' });
  }

  // Preload before the user taps Share. Calling navigator.share directly from
  // the click keeps the browser's transient user activation alive.
  buildShareImageFile()
    .then((file) => {
      shareImageFile = file;
    })
    .catch(() => {
      shareImageFile = null;
    });

  async function copyShareText(text) {
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

  async function handleShare(action) {
    const url = appShareUrl();
    const fullText = `${SHARE_TEXT}\n${url}`;

    action.disabled = true;
    try {
      if (navigator.share) {
        let canShareImage = false;
        if (shareImageFile && navigator.canShare) {
          try {
            canShareImage = navigator.canShare({ files: [shareImageFile] });
          } catch {
            canShareImage = false;
          }
        }

        if (canShareImage) {
          await navigator.share({
            title: 'Kirapara News',
            text: fullText,
            files: [shareImageFile],
          });
          setShareStatus('文章と画像を共有しました', true);
          return;
        }

        await navigator.share({
          title: 'Kirapara News',
          text: SHARE_TEXT,
          url,
        });
        setShareStatus('文章とURLを共有しました', true);
        return;
      }

      if (await copyShareText(fullText)) {
        setShareStatus('投稿文とURLをコピーしました', true);
      } else {
        setShareStatus('共有できませんでした');
      }
    } catch (error) {
      if (error?.name === 'AbortError') return;
      try {
        if (await copyShareText(fullText)) {
          setShareStatus('投稿文とURLをコピーしました', true);
        } else {
          setShareStatus('共有できませんでした');
        }
      } catch {
        setShareStatus('共有できませんでした');
      }
    } finally {
      action.disabled = false;
    }
  }

  const status = document.querySelector('.menu-share-status');
  if (status) status.textContent = SHARE_STATUS_IDLE;

  // menu-install.js already owns this button. Capture the click before its
  // URL-only handler, then provide the richer text + image share flow here.
  document.addEventListener('click', (event) => {
    const action = event.target.closest?.('.menu-share-action');
    if (!action) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    handleShare(action);
  }, true);
})();
