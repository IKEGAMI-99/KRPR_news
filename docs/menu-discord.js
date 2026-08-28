(() => {
  const DISCORD_URL = 'https://discord.gg/wDNNqt3H4';

  function ensureDiscordLink() {
    if (document.querySelector('.menu-discord-section')) return true;

    const installSection = document.querySelector('.menu-install-section');
    if (!installSection) return false;

    const discord = document.createElement('section');
    discord.className = 'menu-analysis-section menu-discord-section';
    discord.innerHTML = `
      <a class="menu-analysis-action" href="${DISCORD_URL}" target="_blank" rel="noopener noreferrer" aria-label="Discordに参加する">
        <span class="menu-analysis-icon" aria-hidden="true">💬</span>
        <span class="menu-analysis-copy">
          <span><strong>Discordに参加する</strong></span>
        </span>
        <span class="menu-analysis-arrow" aria-hidden="true">↗</span>
      </a>`;

    installSection.insertAdjacentElement('afterend', discord);
    return true;
  }

  if (ensureDiscordLink()) return;

  const observer = new MutationObserver(() => {
    if (!ensureDiscordLink()) return;
    observer.disconnect();
  });

  observer.observe(document.body, { childList: true, subtree: true });
})();
