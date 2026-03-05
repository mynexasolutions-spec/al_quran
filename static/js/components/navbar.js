/* ══════════════════════════════════════════════════════════
   Al-Qur'an Global Institute — Navbar Component JS
   Hamburger + drawer toggle handled by inline <script>
   in navbar.html (guaranteed to run on all browsers).
   This module only handles scroll-based nav highlighting.
   ══════════════════════════════════════════════════════════ */

export function initNavbar() {
  const sections = document.querySelectorAll('section[id]');
  const navLinks = document.querySelectorAll('.nav-links a');

  window.addEventListener('scroll', () => {
    let current = '';
    sections.forEach(sec => {
      if (window.scrollY >= sec.offsetTop - 100) current = sec.id;
    });
    navLinks.forEach(a => {
      a.style.color = '';
      if (a.getAttribute('href') === '#' + current) a.style.color = 'var(--gold)';
    });
  });
}
