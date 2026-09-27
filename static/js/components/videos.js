/* ══════════════════════════════════════════════════════════
   Al-Qur'an Global Institute — Video Showcase Carousel
   Same behaviour as the reviews carousel: 3 cards on desktop
   + ← → arrows, 1 card + swipe on mobile.
   ══════════════════════════════════════════════════════════ */

export function initVideoShowcase() {
  const outer   = document.getElementById('vid-track-outer');
  const track   = document.getElementById('vid-track');
  const prevBtn = document.getElementById('vid-prev');
  const nextBtn = document.getElementById('vid-next');
  const dotsEl  = document.getElementById('vid-dots');

  if (!outer || !track) return;

  const cards = Array.from(track.children);
  const total = cards.length;
  let current = 0;

  function isMobile()  { return window.innerWidth <= 660; }
  function getVisible(){ return isMobile() ? 1 : 3; }
  function maxIdx()    { return Math.max(0, total - getVisible()); }

  function getStep() {
    const cardW = cards[0].offsetWidth;
    if (total < 2) return cardW;
    const gap = parseFloat(getComputedStyle(track).gap) || 0;
    return cardW + gap;
  }

  function buildDots() {
    if (!dotsEl) return;
    dotsEl.innerHTML = '';
    for (let i = 0; i <= maxIdx(); i++) {
      const d = document.createElement('button');
      d.type = 'button';
      d.className = 'video-dot' + (i === current ? ' active' : '');
      d.setAttribute('aria-label', 'Video ' + (i + 1));
      d.addEventListener('click', () => goTo(i));
      dotsEl.appendChild(d);
    }
  }

  function updateUI() {
    if (prevBtn) prevBtn.disabled = (current <= 0);
    if (nextBtn) nextBtn.disabled = (current >= maxIdx());
    dotsEl && dotsEl.querySelectorAll('.video-dot')
      .forEach((d, i) => d.classList.toggle('active', i === current));
  }

  function goTo(i) {
    current = Math.max(0, Math.min(i, maxIdx()));
    const step = getStep();
    track.style.transform = 'translateX(-' + (current * step) + 'px)';
    updateUI();
  }

  function refresh() {
    current = Math.min(current, maxIdx());
    buildDots();
    goTo(current);
  }

  requestAnimationFrame(() => requestAnimationFrame(refresh));

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

  /* ── Lightbox modal — click/tap a card to play it large ────── */
  const modalOverlay = document.getElementById('videoModalOverlay');
  const modalPlayer   = document.getElementById('videoModalPlayer');
  const modalTitleEl  = document.getElementById('videoModalTitleText');
  const modalCloseBtn = document.getElementById('videoModalClose');

  function openVideoModal(src, title) {
    if (!modalOverlay || !modalPlayer || !src) return;
    modalPlayer.src = src;
    if (modalTitleEl) modalTitleEl.textContent = title || '';
    modalOverlay.classList.add('open');
    document.body.style.overflow = 'hidden';
    modalPlayer.play().catch(() => {});
  }

  function closeVideoModal() {
    if (!modalOverlay || !modalPlayer) return;
    modalOverlay.classList.remove('open');
    document.body.style.overflow = '';
    modalPlayer.pause();
    modalPlayer.removeAttribute('src');
    modalPlayer.load();
  }

  cards.forEach(card => {
    card.addEventListener('click', () => {
      if (swiping) return; // a swipe just ended on this card — don't also open it
      openVideoModal(card.dataset.videoSrc, card.dataset.videoTitle);
    });
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openVideoModal(card.dataset.videoSrc, card.dataset.videoTitle);
      }
    });
  });

  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeVideoModal);
  if (modalOverlay) {
    modalOverlay.addEventListener('click', e => {
      if (e.target === modalOverlay) closeVideoModal();
    });
  }
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && modalOverlay && modalOverlay.classList.contains('open')) closeVideoModal();
  });
}
