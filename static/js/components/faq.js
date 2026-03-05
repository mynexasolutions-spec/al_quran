/* ══════════════════════════════════════════════════════════
   Al-Qur'an Global Institute — FAQ Accordion JS
   ══════════════════════════════════════════════════════════ */

export function initFaq() {
  document.querySelectorAll('.faq-q').forEach(q => {
    q.addEventListener('click', () => {
      const item   = q.closest('.faq-item');
      const isOpen = item.classList.contains('open');

      // Close all other items
      document.querySelectorAll('.faq-item.open').forEach(openItem => {
        if (openItem !== item) openItem.classList.remove('open');
      });

      item.classList.toggle('open', !isOpen);
    });
  });
}
