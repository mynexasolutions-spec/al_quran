/* 
   Al-Qur'an Global Institute — Main JavaScript Entry Point
   Imports and initialises all component modules.
    */

import { initNavbar }      from './components/navbar.js';
import { initFaq }         from './components/faq.js';
import { initContactForm } from './components/contact.js';
import { initReviews }     from './components/reviews.js';

document.addEventListener('DOMContentLoaded', () => {
  initNavbar();
  initFaq();
  initContactForm();
  initReviews();
});
