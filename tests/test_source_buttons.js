const fs = require('fs');
const vm = require('vm');

const listeners = {};
const appended = [];

function button() {
  return {
    dataset: {},
    classList: { remove() {} },
    removeAttribute() {},
    setAttribute() {},
  };
}

const original = button();
const actions = {
  querySelector() { return original; },
  querySelectorAll() { return []; },
  appendChild(value) { appended.push(value); },
};
const card = {
  dataset: { articleId: 'test' },
  querySelector() { return actions; },
  classList: { toggle() {} },
};
const document = {
  readyState: 'loading',
  addEventListener(name, callback) { listeners[name] = callback; },
  querySelectorAll() { return [card]; },
  createElement() { return button(); },
};
const state = {
  items: [{
    id: 'test',
    sources: [
      {
        platform: '公式Bilibili · 記事',
        url: 'https://www.bilibili.com/opus/1241465453027524644',
      },
      {
        platform: '公式Bilibili · 動態',
        url: 'https://t.bilibili.com/1241465453027524644',
      },
    ],
  }],
};

const source = fs.readFileSync('docs/source-buttons.js', 'utf8');
vm.runInNewContext(`const state = globalState;\n${source}`, {
  globalState: state,
  document,
  location: { href: 'https://ikegami-99.github.io/KRPR_news/' },
  URL,
});
listeners['kirapara:rendered']();

const buttonCount = 1 + appended.length;
if (buttonCount !== 1) {
  throw new Error(`expected one Bilibili button, got ${buttonCount}`);
}
if (original.href !== 'https://www.bilibili.com/opus/1241465453027524644') {
  throw new Error(`unexpected retained Bilibili URL: ${original.href}`);
}
