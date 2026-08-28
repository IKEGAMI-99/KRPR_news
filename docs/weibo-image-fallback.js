(() => {
  const originalCandidates = window.imageCandidates;
  if (typeof originalCandidates !== 'function') return;

  function isSinaImage(url) {
    try {
      return /(^|\.)sinaimg\.(?:cn|com)$/i.test(new URL(url, location.href).hostname);
    } catch {
      return false;
    }
  }

  function weservUrl(source) {
    try {
      const parsed = new URL(source, location.href);
      if (!isSinaImage(parsed.href)) return '';
      const remote = `${parsed.hostname}${parsed.pathname}${parsed.search}`;
      return `https://images.weserv.nl/?url=${encodeURIComponent(remote)}&output=webp`;
    } catch {
      return '';
    }
  }

  // app.js already tries several equivalent Sina CDN aliases directly. Append a
  // neutral image proxy only after those direct candidates, so normal traffic
  // stays on the original CDN while anti-hotlink failures still have a way out.
  window.imageCandidates = function imageCandidatesWithWeiboProxy(urls) {
    const direct = originalCandidates(urls);
    const result = [...direct];
    const seen = new Set(result);
    for (const source of direct) {
      if (!isSinaImage(source)) continue;
      const proxy = weservUrl(source);
      if (proxy && !seen.has(proxy)) {
        seen.add(proxy);
        result.push(proxy);
      }
    }
    return result;
  };

  window.kiraparaWeiboProxyUrl = weservUrl;
})();
