/* ══════════════════════════════════════════════════════════
   Al-Qur'an Global Institute — Contact Form JS
   Handles async form submission to /contact endpoint
   ══════════════════════════════════════════════════════════ */

export function initContactForm() {
  const form = document.getElementById('contactForm');
  if (!form) return;

  form.addEventListener('submit', async function (e) {
    e.preventDefault();

    const submitBtn  = form.querySelector('button[type="submit"]');
    const successMsg = document.getElementById('formSuccess');
    const originalText = submitBtn.textContent;

    submitBtn.textContent = 'Sending…';
    submitBtn.disabled = true;

    const payload = {
      name:    form.querySelector('[name="name"]')?.value    || '',
      phone:   form.querySelector('[name="phone"]')?.value   || '',
      email:   form.querySelector('[name="email"]')?.value   || '',
      course:  form.querySelector('[name="course"]')?.value  || '',
      age:     form.querySelector('[name="age"]')?.value     || '',
      message: form.querySelector('[name="message"]')?.value || '',
    };

    try {
      const res  = await fetch('/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (data.status === 'ok') {
        form.reset();
        if (successMsg) {
          successMsg.textContent = data.message;
          successMsg.style.display = 'block';
          setTimeout(() => { successMsg.style.display = 'none'; }, 6000);
        }
      }
    } catch (err) {
      console.error('Form error:', err);
    } finally {
      submitBtn.textContent = originalText;
      submitBtn.disabled = false;
    }
  });
}
