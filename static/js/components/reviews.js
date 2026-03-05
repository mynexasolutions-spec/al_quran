/* ══════════════════════════════════════════════════════════
   Al-Qur'an Global Institute — Reviews Carousel
   Desktop  :  3 cards visible  +  ← → arrows
   Mobile   :  1 card visible   +  swipe left/right

   Card widths are set purely in CSS via calc().
   JS only handles transform, arrows, dots, and swipe.
   ══════════════════════════════════════════════════════════ */

export function initReviews() {
  const outer   = document.getElementById('rev-track-outer');
  const track   = document.getElementById('rev-track');
  const prevBtn = document.getElementById('rev-prev');
  const nextBtn = document.getElementById('rev-next');
  const dotsEl  = document.getElementById('rev-dots');

  if (!outer || !track) return;

  const cards = Array.from(track.children);
  const total = cards.length;
  let current = 0;

  /* helpers */
  function isMobile()   { return window.innerWidth <= 660; }
  function getVisible()  { return isMobile() ? 1 : 3; }
  function maxIdx()      { return Math.max(0, total - getVisible()); }

  /* Read the actual rendered card width + gap from the DOM.
     Uses offsetWidth + computed gap so the result is correct
     regardless of any transforms already applied to the track. */
  function getStep() {
    const cardW = cards[0].offsetWidth;
    if (total < 2) return cardW;
    const gap = parseFloat(getComputedStyle(track).gap) || 0;
    return cardW + gap;
  }

  /* ── Dots ───────────────────────────────────────── */
  function buildDots() {
    if (!dotsEl) return;
    dotsEl.innerHTML = '';
    for (let i = 0; i <= maxIdx(); i++) {
      const d = document.createElement('button');
      d.type = 'button';
      d.className = 'rev-dot' + (i === current ? ' active' : '');
      d.setAttribute('aria-label', 'Review ' + (i + 1));
      d.addEventListener('click', () => goTo(i));
      dotsEl.appendChild(d);
    }
  }

  /* ── UI state ───────────────────────────────────── */
  function updateUI() {
    if (prevBtn) prevBtn.disabled = (current <= 0);
    if (nextBtn) nextBtn.disabled = (current >= maxIdx());
    dotsEl && dotsEl.querySelectorAll('.rev-dot')
      .forEach((d, i) => d.classList.toggle('active', i === current));
  }

  /* ── Navigate ───────────────────────────────────── */
  function goTo(i) {
    current = Math.max(0, Math.min(i, maxIdx()));
    const step = getStep();
    track.style.transform = 'translateX(-' + (current * step) + 'px)';
    updateUI();
  }

  /* ── Full layout refresh ─────────────────────────── */
  function refresh() {
    current = Math.min(current, maxIdx());
    buildDots();
    goTo(current);
  }

  /* first paint — wait until the browser has laid out CSS calc sizes */
  requestAnimationFrame(() => requestAnimationFrame(refresh));

  /* ── Arrow clicks ───────────────────────────────── */
  if (prevBtn) prevBtn.addEventListener('click', () => goTo(current - 1));
  if (nextBtn) nextBtn.addEventListener('click', () => goTo(current + 1));

  /* ── Touch / swipe ───────────────────────────────── */
  let startX = 0, startY = 0, swiping = false;

  outer.addEventListener('touchstart', e => {
    startX  = e.touches[0].clientX;
    startY  = e.touches[0].clientY;
    swiping = false;
  }, { passive: true });

  outer.addEventListener('touchmove', e => {
    const dx = Math.abs(e.touches[0].clientX - startX);
    const dy = Math.abs(e.touches[0].clientY - startY);
    if (dx > dy && dx > 10) swiping = true;
  }, { passive: true });

  outer.addEventListener('touchend', e => {
    if (!swiping) return;
    const dx = e.changedTouches[0].clientX - startX;
    if      (dx < -40) goTo(current + 1);
    else if (dx >  40) goTo(current - 1);
  }, { passive: true });

  /* ── Resize ──────────────────────────────────────── */
  let rTimer;
  window.addEventListener('resize', () => {
    clearTimeout(rTimer);
    rTimer = setTimeout(refresh, 200);
  });
}
