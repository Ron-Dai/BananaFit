export async function api(url, options = {}) {
  const response = await fetch(url, { credentials: 'include', ...options });
  let body = {};
  try { body = await response.json(); } catch (_error) { /* use an empty safe response */ }
  if (!response.ok) {
    const error = new Error(body?.error?.message || 'The request could not be completed.');
    error.status = response.status;
    throw error;
  }
  return body;
}

export async function startTodayWorkout() {
  const csrf = await api('/api/auth/csrf');
  return api('/api/workouts/today/start', {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrf.csrf_token },
  });
}
