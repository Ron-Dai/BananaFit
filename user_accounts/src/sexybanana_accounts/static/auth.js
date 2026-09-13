(() => {
  'use strict';

  const form = document.querySelector('[data-auth-form]');
  if (!form) return;

  const message = form.querySelector('[data-form-message]');
  const button = form.querySelector('button[type="submit"]');
  let csrfToken = null;

  const showError = (text) => {
    message.textContent = text || 'The request could not be completed.';
    message.classList.add('visible');
  };

  const clearError = () => {
    message.textContent = '';
    message.classList.remove('visible');
  };

  const loadCsrf = async () => {
    const response = await fetch('/api/auth/csrf', { credentials: 'same-origin' });
    if (!response.ok) throw new Error('Security token unavailable. Refresh and try again.');
    const body = await response.json();
    csrfToken = body.csrf_token;
  };

  loadCsrf().catch((error) => showError(error.message));

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearError();
    if (!form.reportValidity()) return;
    if (!csrfToken) {
      showError('Security token unavailable. Refresh and try again.');
      return;
    }

    const mode = form.dataset.authForm;
    const data = Object.fromEntries(new FormData(form).entries());
    if (mode === 'register' && data.password !== data.password_confirmation) {
      showError('The password confirmation does not match.');
      return;
    }

    button.disabled = true;
    button.textContent = mode === 'register' ? 'Creating account…' : 'Signing in…';
    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify(data),
      });
      const body = await response.json();
      if (!response.ok) {
        showError(body?.error?.message);
        await loadCsrf();
        return;
      }
      window.location.assign(body.redirect_url);
    } catch (_error) {
      showError('The service is unavailable. Check your connection and try again.');
    } finally {
      button.disabled = false;
      button.textContent = mode === 'register' ? 'Create account' : 'Sign in';
    }
  });
})();
