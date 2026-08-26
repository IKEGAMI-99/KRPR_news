(() => {
  const trigger = document.querySelector('#menuButton');
  if (!trigger) return;

  const groups = [
    { title:'🇯🇵 日本', links:[
      ['公式サイト','https://kirapara.archosaur.com/'],
      ['公式X','https://x.com/kirapara_JP'],
      ['Instagram','https://www.instagram.com/kiramekiparadise_jp/'],
      ['YouTube','https://www.youtube.com/channel/UC9MO21fNvt0F4-UK28kc_VQ'],
      ['TikTok','https://www.tiktok.com/@kiramekiparadise_jp'],
      ['公式LINE','https://openchat.line.me/jp/cover/kMSwiIddYL1bwpCK-ftv2QKCyCARSVIyV0fo1ou7trbLtA5_RrN71OtwWWk'],
      ['攻略Wiki','https://gamerch.com/kirapara/']
    ]},
    { title:'🇨🇳 中国', links:[
      ['公式サイト','https://mystyle.archosaur.com/'],
      ['Weibo','https://weibo.com/u/7521830234'],
      ['Bilibili','https://space.bilibili.com/676200579']
    ]},
    { title:'🌐 Global', links:[
      ['公式サイト','https://lifemakeover.archosaur.com/'],
      ['公式X','https://x.com/LifeMakeover510'],
      ['Instagram','https://www.instagram.com/lifemakeover_global/'],
      ['YouTube','https://www.youtube.com/@LifeMakeover'],
      ['TikTok','https://www.tiktok.com/@lifemakeoverofficial'],
      ['Wiki','https://lifemakeover.wiki.gg/']
    ]},
    { title:'🇰🇷 韓国', links:[
      ['公式サイト','https://stylight.nex2fun.com/'],
      ['公式X','https://x.com/stylight_kr'],
      ['Instagram','https://www.instagram.com/stylight_kr/'],
      ['YouTube','https://www.youtube.com/@stylight_official'],
      ['TikTok','https://www.tiktok.com/@stylightofficial'],
      ['Naver Cafe','https://cafe.naver.com/stylightofficial'],
      ['Naver Lounge','https://game.naver.com/lounge/stylight/home']
    ]}
  ];

  const backdrop = document.createElement('div');
  backdrop.className = 'menu-backdrop';
  const menu = document.createElement('aside');
  menu.className = 'link-menu';
  menu.setAttribute('role','dialog');
  menu.setAttribute('aria-modal','true');
  menu.setAttribute('aria-label','公式リンクメニュー');
  menu.innerHTML = `<div class="link-menu-header"><div class="link-menu-title">リンク集 ✦</div><button class="link-menu-close" type="button" aria-label="閉じる">×</button></div><div class="link-menu-body"></div>`;
  const body = menu.querySelector('.link-menu-body');

  for (const group of groups) {
    const section = document.createElement('section');
    section.className = 'menu-region';
    const heading = document.createElement('h3');
    heading.textContent = group.title;
    const links = document.createElement('div');
    links.className = 'menu-links';
    for (const [label,url] of group.links) {
      const a = document.createElement('a');
      a.className = 'menu-link';
      a.href = url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.textContent = label;
      links.appendChild(a);
    }
    section.append(heading,links);
    body.appendChild(section);
  }

  const note = document.createElement('p');
  note.className = 'menu-note';
  note.textContent = 'Wikiは運営公式ではなく、コミュニティ運営の攻略Wikiです。';
  body.appendChild(note);
  document.body.append(backdrop,menu);

  const close = () => {
    menu.classList.remove('is-open');
    backdrop.classList.remove('is-open');
    document.body.classList.remove('menu-open');
    trigger.setAttribute('aria-expanded','false');
  };
  const open = () => {
    menu.classList.add('is-open');
    backdrop.classList.add('is-open');
    document.body.classList.add('menu-open');
    trigger.setAttribute('aria-expanded','true');
    menu.querySelector('.link-menu-close')?.focus();
  };
  trigger.setAttribute('aria-expanded','false');
  trigger.addEventListener('click', () => menu.classList.contains('is-open') ? close() : open());
  backdrop.addEventListener('click', close);
  menu.querySelector('.link-menu-close').addEventListener('click', close);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && menu.classList.contains('is-open')) close(); });
})();