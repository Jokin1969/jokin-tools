// ─── Hub nav: hide links to apps the user can't access ──────────────────────────
// The top nav in each app lists every app statically. This trims it to the
// apps the logged-in user is actually allowed into, so nobody sees a link that
// would only land them on a 403. The hub ("/") and brand links always stay.
(function () {
  function slug(id) { return String(id).replace(/-/g, ''); }

  async function trimNav() {
    const links = document.querySelectorAll('.hub-nav-link[data-app], .pharma-link[data-app]');
    if (!links.length) return;
    let data;
    try {
      const r = await fetch('/auth/api/me', { headers: { Accept: 'application/json' } });
      if (!r.ok) return;                 // not logged in / error → leave nav untouched
      data = await r.json();
    } catch { return; }

    const allowed = new Set((data.apps || []).map(a => slug(a.id)));
    links.forEach(link => {
      const app = link.getAttribute('data-app');
      if (app === 'hub') return;         // hub link is always available
      if (!allowed.has(slug(app))) link.style.display = 'none';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', trimNav);
  } else {
    trimNav();
  }

  // ─── Clear "✕" for every search box (.qt-search) ──────────────────────────────
  // Adds a discreet clear button to each search field, shown only when it has
  // text. Clicking it empties the field and fires an `input` event so the app
  // re-filters. Applied to all current and future .qt-search inputs.
  function addClear(input) {
    if (!input || input.dataset.hasClear) return;
    const wrap = input.closest('.qt-search');
    if (!wrap) return;
    input.dataset.hasClear = '1';
    wrap.classList.add('has-clear');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'qt-search-x';
    btn.title = 'Limpiar búsqueda';
    btn.setAttribute('aria-label', 'Limpiar búsqueda');
    btn.tabIndex = -1;
    btn.textContent = '✕';
    const sync = () => { btn.style.display = input.value ? 'flex' : 'none'; };
    btn.addEventListener('mousedown', e => e.preventDefault()); // don't steal focus
    btn.addEventListener('click', () => {
      input.value = '';
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      try { input.focus(); } catch (e) { /* */ }
      sync();
    });
    input.addEventListener('input', sync);
    wrap.appendChild(btn);
    sync();
  }
  function scanSearches() { document.querySelectorAll('.qt-search input').forEach(addClear); }
  let raf = 0;
  function scheduleScan() { if (raf) return; raf = requestAnimationFrame(() => { raf = 0; scanSearches(); }); }

  function initSearchClears() {
    scanSearches();
    try { new MutationObserver(scheduleScan).observe(document.body, { childList: true, subtree: true }); } catch (e) { /* */ }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initSearchClears);
  else initSearchClears();
})();
