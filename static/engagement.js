/* The mirror has its own participation counts. No WordPress synchronization. */
(() => {
  const widgets = [...document.querySelectorAll('.engagement[data-post]')];
  if (!widgets.length) return;
  const API = 'https://comments.humanstoriesforaibots.com/api/engagement/';
  const online = location.protocol === 'https:' && location.hostname === 'zy-gitcoder.github.io';
  if (!online) {
    widgets.forEach(w => w.querySelector('.engagement-status').textContent = 'Counts available on the live mirror.');
    return;
  }
  const memory = new Map();
  function token(storeName, key) {
    try {
      const store = window[storeName];
      const saved = store.getItem(key);
      if (/^[a-f0-9]{64}$/.test(saved || '')) return saved;
      const value = fresh();
      store.setItem(key, value);
      return value;
    } catch {
      if (!memory.has(key)) memory.set(key, fresh());
      return memory.get(key);
    }
  }
  function fresh() { return [...crypto.getRandomValues(new Uint8Array(32))].map(b => b.toString(16).padStart(2, '0')).join(''); }
  const likeToken = token('localStorage', 'hsfab-mirror-like-v1');
  const viewToken = token('sessionStorage', 'hsfab-mirror-view-v1');
  const states = new Map();
  async function request(route, data) {
    const response = await fetch(API + route, {
      method: 'POST', credentials: 'omit', cache: 'no-store',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data),
      signal: AbortSignal.timeout(10000)
    });
    if (!response.ok) throw new Error('Unavailable');
    return response.json();
  }
  function render(post, incoming) {
    const previous = states.get(post) || {revision:-1, liked:false};
    if (incoming.revision < previous.revision) return;
    const state = {...previous, ...incoming};
    states.set(post, state);
    widgets.filter(w => w.dataset.post === post).forEach(w => {
      w.querySelector('.view-count').textContent = `${state.views.toLocaleString()} ${state.views === 1 ? 'view' : 'views'}`;
      w.querySelector('.like-count').textContent = state.likes.toLocaleString();
      w.querySelector('.like-label').textContent = state.liked ? 'Liked' : 'Like';
      w.querySelector('.essay-like').setAttribute('aria-pressed', String(state.liked));
      w.querySelector('.essay-like [aria-hidden]').textContent = state.liked ? '♥' : '♡';
    });
  }
  widgets.forEach(w => {
    const button = w.querySelector('.essay-like');
    button.addEventListener('click', async () => {
      button.disabled = true;
      const status = w.querySelector('.engagement-status');
      status.textContent = '';
      const desired = !(states.get(w.dataset.post)?.liked ?? false);
      try {
        // Set a desired state, never increment: retrying an uncertain response is safe.
        const result = await request('like', {post:w.dataset.post, token:likeToken, liked:desired});
        render(w.dataset.post, result);
        status.textContent = result.liked ? 'Thank you.' : 'Like removed.';
      } catch { status.textContent = 'Could not save your like. Please try again.'; }
      finally { button.disabled = false; }
    });
  });
  const viewed = new Set();
  const queue = [];
  let processing = false;
  async function drain() {
    if (processing || document.visibilityState !== 'visible') return;
    processing = true;
    while (queue.length && document.visibilityState === 'visible') {
      const post = queue.shift();
      try { render(post, await request('view', {post, token:viewToken})); }
      catch { /* Reading always works, even if the counter service does not. */ }
    }
    processing = false;
  }
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting || document.visibilityState !== 'visible') return;
      const post = entry.target.closest('.essay').querySelector('.engagement').dataset.post;
      if (!viewed.has(post)) { viewed.add(post); queue.push(post); }
    });
    drain();
  }, {threshold:0.1});
  async function start() {
    try {
      const data = await request('state', {token:likeToken});
      widgets.forEach(w => {
        if (data.posts[w.dataset.post]) render(w.dataset.post, data.posts[w.dataset.post]);
        w.querySelector('.essay-like').disabled = false;
      });
    } catch {
      widgets.forEach(w => {
        w.querySelector('.engagement-status').textContent = 'Counts temporarily unavailable.';
        w.querySelector('.essay-like').disabled = false;
      });
    }
    // On the long homepage, only essays that actually enter the viewport count.
    widgets.forEach(w => observer.observe(w.closest('.essay').querySelector('.essay-header')));
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      widgets.forEach(w => {
        const header = w.closest('.essay').querySelector('.essay-header');
        observer.unobserve(header); observer.observe(header);
      });
      drain();
    }
  });
  start();
})();
