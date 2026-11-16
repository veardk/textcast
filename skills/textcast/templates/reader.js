(function () {
  const DATA = JSON.parse(document.getElementById('textcast-data').textContent);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ---------- expand / collapse
  const expand = document.getElementById('btn-expand-all');
  const collapse = document.getElementById('btn-collapse-all');
  if (expand) expand.addEventListener('click', () => $$('.topic').forEach(t => (t.open = true)));
  if (collapse) collapse.addEventListener('click', () => $$('.topic').forEach(t => (t.open = false)));

  // ---------- theme (light / dark / sepia); the initial value is applied by theme-init.js in <head>
  const THEME_KEY = 'textcast_theme';
  // Lucide icons (ISC licence, https://lucide.dev), picked via notionicons.so: sun / moon / book-open-text
  const THEME_ICONS = {
    light: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    dark: '<path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/>',
    sepia: '<path d="M12 7v14m4-9h2m-2-4h2M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3zm3-6h2M6 8h2"/>',
  };
  // <div class="theme-switch" data-labels="浅色|暗色|护眼"> → three icon buttons
  $$('.theme-switch[data-labels]').forEach(box => {
    const names = box.dataset.labels.split('|');
    ['light', 'dark', 'sepia'].forEach((th, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'theme-btn';
      b.dataset.theme = th;
      b.title = names[i] || th;
      b.innerHTML = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        + 'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + THEME_ICONS[th] + '</svg>'
        + '<span class="theme-name"></span>';
      b.querySelector('.theme-name').textContent = names[i] || th;
      box.appendChild(b);
    });
  });
  function syncTheme() {
    const cur = document.documentElement.getAttribute('data-theme');
    $$('.theme-btn').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.theme === cur)));
  }
  $$('.theme-btn').forEach(b => b.addEventListener('click', () => {
    document.documentElement.setAttribute('data-theme', b.dataset.theme);
    try { localStorage.setItem(THEME_KEY, b.dataset.theme); } catch (e) {}
    syncTheme();
  }));
  // 未手动选择时继续跟随系统切换
  if (window.matchMedia) {
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
      let saved = null;
      try { saved = localStorage.getItem(THEME_KEY); } catch (err) {}
      if (!saved && !/[?&]textcast_theme=/.test(location.search)) { document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light'); syncTheme(); }
    });
  }
  syncTheme();

  // ---------- reading mode (src / tgt / bi)，切换时保持阅读位置
  const MODES = DATA.modes || ['src'];
  const BAR_OFFSET = 80;
  const KEY = 'textcast_mode';

  function anchor() {
    for (const seg of $$('.seg')) {
      if (!seg.offsetParent) continue;
      const r = seg.getBoundingClientRect();
      if (r.bottom > BAR_OFFSET) return { id: seg.dataset.seg, top: r.top };
    }
    return null;
  }

  function setMode(mode, keep) {
    if (!MODES.includes(mode)) mode = DATA.defaultMode || MODES[0];
    const a = keep ? anchor() : null;
    ['src', 'tgt', 'bi'].forEach(m => document.body.classList.toggle('mode-' + m, m === mode));
    $$('.mode-btn').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === mode)));
    if (keep) { try { localStorage.setItem(KEY, mode); } catch (e) {} } // 只记住用户主动的选择
    if (a) {
      const t = document.querySelector(`.flow-${mode} .seg[data-seg="${a.id}"]`);
      if (t && t.offsetParent) window.scrollBy(0, t.getBoundingClientRect().top - Math.max(a.top, BAR_OFFSET));
    }
  }
  $$('.mode-btn').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode, true)));
  let saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  setMode(saved, false);

  // ---------- hover: highlight the paired sentence, show its time in the gutter
  function hover(seg, on) {
    const para = seg.closest('.para');
    if (!para) return;
    $$(`.seg[data-seg="${seg.dataset.seg}"]`, para).forEach(s => s.classList.toggle('hl', on));
    const label = para.querySelector('.ts-seg');
    if (label) label.textContent = on && seg.dataset.t ? seg.dataset.t : '';
  }
  document.addEventListener('mouseover', e => { const s = e.target.closest('.seg'); if (s) hover(s, true); });
  document.addEventListener('mouseout', e => {
    const s = e.target.closest('.seg');
    if (s && !s.contains(e.relatedTarget)) hover(s, false);
  });

  // ---------- player: local <video>/<audio> seeks in place; embeds reload at the start second
  const P = DATA.player;
  if (!P) return;
  const dock = document.getElementById('player-dock');
  const slot = document.getElementById('player-slot');
  let media = null;

  function embedUrl(sec) {
    if (P.kind === 'youtube') return `https://www.youtube.com/embed/${P.id}?start=${sec}&autoplay=1&rel=0`;
    if (P.kind === 'bilibili') return `https://player.bilibili.com/player.html?bvid=${P.id}&p=${P.page || 1}&t=${sec}&autoplay=1&high_quality=1&danmaku=0`;
    return null;
  }

  // Highlight the sentence being played (local media reports time; embeds mark the clicked one)
  let lastPlaying = null;
  function mark(sec) {
    const times = DATA.times;
    let lo = 0, hi = times.length - 1, hit = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (times[mid][0] <= sec) { hit = mid; lo = mid + 1; } else hi = mid - 1;
    }
    if (hit === lastPlaying) return;
    $$('.seg.playing').forEach(s => s.classList.remove('playing'));
    lastPlaying = hit;
    if (hit >= 0) $$(`.seg[data-seg="${hit}"]`).forEach(s => s.classList.add('playing'));
  }

  // A sandboxed page (opaque origin, e.g. inside a review tool's iframe) passes its sandbox on to
  // nested iframes, so YouTube/Bilibili players load blank there — open the video page instead.
  const SANDBOXED = window.origin === 'null' && location.protocol !== 'file:';
  function watchUrl(sec) {
    if (P.kind === 'youtube') return `https://www.youtube.com/watch?v=${P.id}&t=${sec}s`;
    if (P.kind === 'bilibili') return `https://www.bilibili.com/video/${P.id}?p=${P.page || 1}&t=${sec}`;
    return null;
  }

  function seek(sec) {
    const whole = Math.floor(sec);
    // YouTube refuses embeds without a Referer (file:// pages) — open the watch page instead
    // Inside textcast-chat-axi the review page around this one plays it in its own floating window.
    if (SANDBOXED && embedUrl(whole) && typeof window.textcastHostPlayer === 'function') {
      window.textcastHostPlayer({ kind: P.kind, id: P.id, page: P.page || 1, start: whole });
      mark(sec);
      return;
    }
    if ((P.kind === 'youtube' && location.protocol === 'file:') || (SANDBOXED && watchUrl(whole))) {
      window.open(watchUrl(whole), 'textcast-player');
      mark(sec);
      return;
    }
    dock.hidden = false;
    if (P.kind === 'video' || P.kind === 'audio') {
      if (!media) {
        media = document.createElement(P.kind);
        media.src = P.src;
        media.controls = true;
        media.preload = 'metadata';
        if (P.kind === 'video') media.className = 'player-frame';
        media.addEventListener('timeupdate', () => mark(media.currentTime));
        slot.appendChild(media);
      }
      media.currentTime = sec;
      media.play().catch(() => {});
      return;
    }
    let frame = slot.querySelector('iframe');
    if (!frame) {
      frame = document.createElement('iframe');
      frame.className = 'player-frame';
      frame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      frame.allowFullscreen = true;
      slot.appendChild(frame);
    }
    frame.src = embedUrl(whole);
    mark(sec);
  }

  document.getElementById('player-close').addEventListener('click', () => {
    dock.hidden = true;
    if (media) media.pause();
    const f = slot.querySelector('iframe');
    if (f) f.remove();
    $$('.seg.playing').forEach(s => s.classList.remove('playing'));
    lastPlaying = null;
  });

  // Drag the player by its title bar so it never sits on the line being read. The spot is kept
  // for the next page; phones keep the full-width bottom bar.
  const POS_KEY = 'textcast_player_pos';
  const bar = dock.querySelector('.player-bar');
  const narrow = () => window.matchMedia('(max-width: 640px)').matches;
  function placeDock(x, y) {
    const w = dock.offsetWidth, h = dock.offsetHeight, m = 8;
    x = Math.min(Math.max(m, x), Math.max(m, innerWidth - w - m));
    y = Math.min(Math.max(m, y), Math.max(m, innerHeight - h - m));
    Object.assign(dock.style, { left: x + 'px', top: y + 'px', right: 'auto', bottom: 'auto', insetInlineEnd: 'auto' });
    return { x, y };
  }
  function restoreDock() {
    if (dock.hidden) return;
    if (narrow()) { dock.removeAttribute('style'); return; }
    let pos = null;
    try { pos = JSON.parse(localStorage.getItem(POS_KEY) || 'null'); } catch (e) {}
    if (pos && isFinite(pos.x) && isFinite(pos.y)) placeDock(pos.x, pos.y);
  }
  let drag = null;
  bar.addEventListener('pointerdown', e => {
    if (e.button || e.target.closest('button') || narrow()) return;
    const r = dock.getBoundingClientRect();
    drag = { id: e.pointerId, dx: e.clientX - r.left, dy: e.clientY - r.top };
    bar.setPointerCapture(e.pointerId);
    dock.classList.add('dragging');
    e.preventDefault();
  });
  bar.addEventListener('pointermove', e => {
    if (drag && e.pointerId === drag.id) placeDock(e.clientX - drag.dx, e.clientY - drag.dy);
  });
  const endDrag = e => {
    if (!drag || e.pointerId !== drag.id) return;
    drag = null;
    dock.classList.remove('dragging');
    const r = dock.getBoundingClientRect();
    try { localStorage.setItem(POS_KEY, JSON.stringify({ x: Math.round(r.left), y: Math.round(r.top) })); } catch (err) {}
  };
  bar.addEventListener('pointerup', endDrag);
  bar.addEventListener('pointercancel', endDrag);
  window.addEventListener('resize', restoreDock);
  new MutationObserver(restoreDock).observe(dock, { attributes: true, attributeFilter: ['hidden'] });

  document.addEventListener('click', e => {
    const ts = e.target.closest('[data-seek]');
    if (ts) { e.preventDefault(); seek(+ts.dataset.seek); return; }
    const seg = e.target.closest('.seg');
    if (!seg || e.target.closest('a')) return;
    const sel = window.getSelection();
    if (sel && !sel.isCollapsed) return; // 选中文字时不跳播
    const t = DATA.times[+seg.dataset.seg];
    if (t) seek(t[0]);
  });
})();
