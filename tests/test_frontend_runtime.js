const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

function element() {
  const classes = new Set();
  return {
    hidden: false,
    classList: {
      add: (name) => classes.add(name), remove: (name) => classes.delete(name),
      contains: (name) => classes.has(name),
      toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); },
    },
    setAttribute() {}, removeAttribute() {}, replaceChildren() {}, appendChild() {},
    addEventListener() {}, focus() {},
  };
}

function appHarness() {
  const nodes = new Map();
  const keys = [];
  const document = {
    body: element(),
    querySelector(selector) { return nodes.get(selector) || null; },
    addEventListener(name, listener) { if (name === 'keydown') keys.push(listener); },
    createElement() {
      const node = element();
      const children = new Map();
      node.querySelector = (selector) => {
        if (!children.has(selector)) children.set(selector, element());
        return children.get(selector);
      };
      return node;
    },
  };
  document.body.appendChild = (node) => nodes.set('#imageViewer', node);
  const context = vm.createContext({
    document, URL, URLSearchParams, Intl, HTMLElement: Object,
    location: { hostname: 'localhost', href: 'http://localhost/docs/' },
    KiraparaPagination: require('../docs/pagination.js'),
    localStorage: { getItem() { return null; }, setItem() { throw Error('quota exceeded'); } },
    fetch: async () => { throw Error('offline'); },
  });
  const source = fs.readFileSync(path.join(root, 'docs/app.js'), 'utf8');
  // Run the production declarations without the page bootstrap. Rendering is
  // stubbed so requests/storage and viewer lifecycle can be tested in isolation.
  vm.runInContext(source.slice(0, source.indexOf("els.tabs.addEventListener('click'")), context);
  vm.runInContext(`
    for (const key of Object.keys(els)) els[key] = document.createElement('div');
    render = () => {}; renderSkeletons = () => {}; writeNavigationUrl = () => {};
    latestUpdateLabel = (items) => String(items.length);
  `, context);
  return { context, document, nodes, keys, run: (code) => vm.runInContext(code, context) };
}

test('refresh failure preserves current news when persistent storage is unavailable', async () => {
  const h = appHarness();
  h.run("state.items = [{id: 'current'}]");
  await h.run('loadNews({force: true})');
  assert.equal(h.run('state.items[0]?.id'), 'current');
  assert.equal(h.run('els.error.hidden'), true);
});

test('refresh failure never replaces newer displayed news with an older disk cache', async () => {
  const h = appHarness();
  h.context.localStorage.getItem = () => JSON.stringify({items: [{id: 'old'}]});
  h.run("state.items = [{id: 'new'}]");
  await h.run('loadNews()');
  assert.equal(h.run('state.items[0]?.id'), 'new');
});

test('cold offline start still uses the saved cache', async () => {
  const h = appHarness();
  h.context.localStorage.getItem = () => JSON.stringify({items: [{id: 'saved'}]});
  await h.run('loadNews()');
  assert.equal(h.run('state.items[0]?.id'), 'saved');
});

test('a late older request cannot overwrite a newer refresh or clear its indicator', async () => {
  const h = appHarness();
  const requests = [];
  h.context.fetch = () => new Promise((resolve, reject) => requests.push({resolve, reject}));
  const older = h.run('loadNews({force: true})');
  const newer = h.run('loadNews({force: true})');
  requests[0].reject(Error('old request failed'));
  await older;
  assert.equal(h.document.body.classList.contains('refreshing'), true);
  requests[1].resolve({ok: true, json: async () => [{id: 'new'}]});
  await newer;
  const slow = h.run('loadNews()');
  const fast = h.run('loadNews({force: true})');
  requests[3].resolve({ok: true, json: async () => [{id: 'newest'}]});
  await fast;
  requests[2].resolve({ok: true, json: async () => [{id: 'stale'}]});
  await slow;
  assert.equal(h.run('state.items[0]?.id'), 'newest');
});

test('reopening the viewer does not retain keyboard handlers for removed viewers', () => {
  const h = appHarness();
  for (let index = 0; index < 5; index++) {
    h.run("openViewer(['https://example.com/1.jpg', 'https://example.com/2.jpg'])");
    assert.equal(h.keys.length, 1);
    h.keys.forEach((listener) => listener({key: 'ArrowRight'}));
    assert.equal(h.run('viewerIndex'), 1);
    h.run('closeViewer()');
    h.nodes.delete('#imageViewer'); // viewer-lifecycle-fix.js removes closed nodes
  }
});

function swHarness() {
  const scope = 'https://ikegami-99.github.io/KRPR_news/';
  const handlers = {};
  const entries = new Map();
  const deleted = [];
  const cache = {
    async put(request, response) { entries.set(new URL(request.url || request, scope).href, response); },
    async match(request, options = {}) {
      const url = new URL(request.url || request, scope);
      for (const [key, response] of entries) {
        const candidate = new URL(key);
        if (options.ignoreSearch) { url.search = ''; candidate.search = ''; }
        if (url.href === candidate.href) return response.clone();
      }
    },
  };
  const caches = {
    open: async () => cache, match: cache.match,
    keys: async () => ['another-app-cache', 'kirapara-pwa-shell-v1'],
    delete: async (key) => { deleted.push(key); return true; },
  };
  const context = vm.createContext({
    URL, Response, caches,
    fetch: async () => { throw Error('offline'); },
    self: {
      registration: {scope}, location: {origin: new URL(scope).origin},
      clients: {claim: async () => {}},
      addEventListener: (name, handler) => { handlers[name] = handler; },
    },
  });
  vm.runInContext(fs.readFileSync(path.join(root, 'docs/sw.js'), 'utf8'), context);
  return {context, cache, deleted, handlers, run: (code) => vm.runInContext(code, context)};
}

test('HTTP errors fall back to cached shell assets and navigation pages', async () => {
  const h = swHarness();
  h.context.fetch = async () => new Response('outage', {status: 503});
  await h.cache.put('./app.js', new Response('cached script'));
  await h.cache.put('./index.html', new Response('cached page'));
  assert.equal(await (await h.run("shellResponse({url: 'https://ikegami-99.github.io/KRPR_news/app.js'})")).text(), 'cached script');
  assert.equal(await (await h.run("navigationResponse({url: 'https://ikegami-99.github.io/KRPR_news/index.html'})")).text(), 'cached page');
});

test('cache write failures cannot discard successful network responses', async () => {
  const h = swHarness();
  h.cache.put = async () => { throw Error('quota exceeded'); };
  h.context.fetch = async () => new Response('fresh content');
  for (const fn of ['shellResponse', 'navigationResponse']) {
    const response = await h.run(`${fn}({url: 'https://ikegami-99.github.io/KRPR_news/index.html'})`);
    assert.equal(await response?.text(), 'fresh content');
  }
});

test('offline navigation with a query retains the requested cached page', async () => {
  const h = swHarness();
  await h.cache.put('./terms.html', new Response('terms'));
  await h.cache.put('./index.html', new Response('home'));
  const response = await h.run("navigationResponse({url: 'https://ikegami-99.github.io/KRPR_news/terms.html?source=menu'})");
  assert.equal(await response.text(), 'terms');
});

test('service worker activation preserves caches belonging to other apps', async () => {
  const h = swHarness();
  let completion;
  h.handlers.activate({waitUntil(promise) { completion = promise; }});
  await completion;
  assert.deepEqual(h.deleted, ['kirapara-pwa-shell-v1']);
});
