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
})();
