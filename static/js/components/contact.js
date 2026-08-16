/* ══════════════════════════════════════════════════════════
   Al-Qur'an Global Institute — Contact Form JS
   Handles async form submission to /contact endpoint
   ══════════════════════════════════════════════════════════ */

export function initContactForm() {
  const form = document.getElementById('contactForm');
  if (!form || form.dataset.initialized) return;
  form.dataset.initialized = 'true';

  form.addEventListener('submit', async function (e) {
    e.preventDefault();

    const submitBtn  = form.querySelector('button[type="submit"]');
    const successMsg = document.getElementById('formSuccess');
    const originalText = submitBtn ? submitBtn.innerHTML : 'Submit';

    if (submitBtn) {
      if (submitBtn.disabled) return;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '⏳ Submitting enquiry...';
    }

    const payload = {
      name:    form.querySelector('[name="name"]')?.value?.trim()    || '',
      phone:   form.querySelector('[name="phone"]')?.value?.trim()   || '',
      email:   form.querySelector('[name="email"]')?.value?.trim()   || '',
      course:  form.querySelector('[name="course"]')?.value?.trim()  || '',
      age:     form.querySelector('[name="age"]')?.value?.trim()     || '',
      address: form.querySelector('[name="address"]')?.value?.trim() || '',
      message: form.querySelector('[name="message"]')?.value?.trim() || '',
    };

    try {
      const res  = await fetch('/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (data && data.status === 'ok') {
        form.reset();
        if (successMsg) {
          successMsg.innerHTML = '✨ ' + (data.message || 'JazakAllah Khair! Your enquiry has been received.');
          successMsg.style.display = 'block';
          setTimeout(() => { successMsg.style.display = 'none'; }, 8000);
        }
      }
    } catch (err) {
      console.error('Form error:', err);
      if (successMsg) {
        successMsg.innerHTML = '❌ An error occurred. Please try again.';
        successMsg.style.display = 'block';
      }
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
      }
    }
  });
}
