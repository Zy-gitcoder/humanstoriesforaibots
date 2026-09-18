/* One independent Isso discussion per mirror essay; the offline edition is inert. */
(() => {
  const thread = document.querySelector('#isso-thread');
  const status = document.querySelector('#discussion-status');
  if (!thread || !status) return;
  if (location.protocol !== 'https:' || location.hostname !== 'zy-gitcoder.github.io') {
    status.textContent = 'Live comments are available on the online GitHub mirror.';
    return;
  }
  const endpoint = 'https://comments.humanstoriesforaibots.com/api/';
  function update(box) {
    const text = box.querySelector('textarea');
    const name = box.querySelector('input[name="author"]');
    const email = box.querySelector('input[name="email"]');
    if (email) email.value = '';
    if (!text) return true;
    text.removeAttribute('maxlength'); // Count code points, not UTF-16 units.
    if (name) name.removeAttribute('maxlength');
    let size = box.querySelector('.comment-size');
    if (!size) {
      size = document.createElement('p');
      size.className = 'comment-size';
      size.setAttribute('role', 'status');
      text.parentElement.append(size);
    }
    const count = Array.from(text.value).length;
    const nameCount = Array.from(name?.value || '').length;
    const valid = count <= 2000 && nameCount <= 64;
    const message = `${count} / 2,000 characters` + (nameCount > 64 ? ' · Name exceeds 64 characters' : '');
    if (size.textContent !== message) size.textContent = message;
    size.classList.toggle('over-limit', !valid);
    return valid;
  }
  thread.addEventListener('input', e => {
    const box = e.target.closest('.isso-postbox');
    if (box) update(box);
  });
  thread.addEventListener('click', e => {
    if (!e.target.matches('input[type="submit"],input[name="preview"]')) return;
    const box = e.target.closest('.isso-postbox');
    if (box && !update(box)) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, true);
  const observer = new MutationObserver(() => {
    thread.querySelectorAll('.isso-postbox').forEach(update);
    const heading = thread.querySelector('.isso-thread-heading');
    if (heading?.textContent === 'No Comments Yet' && thread.querySelector('.isso-comment[id]')) {
      heading.textContent = 'Comments';
    }
    // The heading only contains text once Isso has fetched the actual thread.
    if (heading?.textContent) {
      status.hidden = true;
      clearTimeout(timeout);
    }
  });
  observer.observe(thread, {childList:true, subtree:true});
  const timeout = setTimeout(() => {
    status.textContent = 'The discussion could not load. Please reload to retry, or use the comment archive above.';
  }, 15000);
  const script = document.createElement('script');
  script.src = endpoint + 'js/embed.min.js';
  script.setAttribute('data-isso', endpoint);
  script.setAttribute('data-isso-avatar', 'false');
  script.setAttribute('data-isso-gravatar', 'false');
  script.setAttribute('data-isso-vote', 'false'); // Essay likes are a separate control.
  script.setAttribute('data-isso-max-comments-top', '20');
  script.setAttribute('data-isso-max-comments-nested', '5');
  script.onerror = () => {
    clearTimeout(timeout);
    status.textContent = 'The discussion is temporarily unavailable. Please reload to retry, or use the comment archive above.';
  };
  document.body.append(script);
})();
