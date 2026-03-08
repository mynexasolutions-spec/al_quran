/* 
   Al-Qur'an Global Institute — Main JavaScript Entry Point
   Imports and initialises all component modules.
    */

import { initNavbar }      from './components/navbar.js';
import { initFaq }         from './components/faq.js';
import { initContactForm } from './components/contact.js';
import { initReviews }     from './components/reviews.js';
import { translations }    from './i18n.js';

/* ── Language Toggle ── */
function applyLang(lang) {
  const t = translations[lang];
  if (!t) return;

  // RTL support for Urdu
  document.documentElement.lang = lang === 'ur' ? 'ur' : 'en';
  document.documentElement.dir  = lang === 'ur' ? 'rtl' : 'ltr';
  document.body.classList.toggle('lang-ur', lang === 'ur');

  // Swap every element that has data-i18n attribute
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (t[key] !== undefined) {
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = t[key];
      } else if (el.tagName === 'OPTION' && el.dataset.i18nOpt) {
        el.textContent = t[key];
      } else {
        el.innerHTML = t[key];
      }
    }
  });

  // Toggle button active state
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('lang-btn--active', btn.dataset.lang === lang);
  });

  // Persist choice
  localStorage.setItem('aqgi-lang', lang);
}

function initLangToggle() {
  const saved = localStorage.getItem('aqgi-lang') || 'en';
  applyLang(saved);

  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => applyLang(btn.dataset.lang));
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initNavbar();
  initFaq();
  initContactForm();
  initReviews();
  initLangToggle();
});
