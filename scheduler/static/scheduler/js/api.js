const BASE = '/scheduler';

function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

async function request(method, url, body = undefined) {
  const headers = { 'X-CSRFToken': getCsrfToken() };
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: 'same-origin',
  });

  if (res.status === 401) {
    window.location.href = '/accounts/login/';
    return null;
  }

  if (res.status === 204) return { ok: true };

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    console.error(`API ${method} ${url} →`, res.status, err);
    throw Object.assign(new Error(err.detail ?? 'API error'), { status: res.status, data: err });
  }

  return res.json();
}

// Content-Type을 지정하지 않으면 브라우저가 multipart/form-data + boundary를 자동으로 설정
async function requestFormData(method, url, formData) {
  const res = await fetch(url, {
    method,
    headers: { 'X-CSRFToken': getCsrfToken() },
    body: formData,
    credentials: 'same-origin',
  });

  if (res.status === 401) {
    window.location.href = '/accounts/login/';
    return null;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    console.error(`API ${method} ${url} →`, res.status, err);
    throw Object.assign(new Error(err.detail ?? 'API error'), { status: res.status, data: err });
  }

  return res.json();
}

// ── Plans ─────────────────────────────────────────────────────────────────────

export async function getTodayPlan() {
  return request('GET', `${BASE}/plans/today/`);
}

export async function createPlan() {
  return request('POST', `${BASE}/plans/`);
}

export async function getSummary(planId) {
  return request('GET', `${BASE}/plans/${planId}/summary/`);
}

// ── Tasks ─────────────────────────────────────────────────────────────────────

export async function completeTask(taskId) {
  return request('POST', `${BASE}/tasks/${taskId}/complete/`);
}

export async function skipTask(taskId) {
  return request('POST', `${BASE}/tasks/${taskId}/skip/`);
}

// ── Timer ─────────────────────────────────────────────────────────────────────

export async function startTimer(taskId, type) {
  return request('POST', `${BASE}/timer/start/`, { task_id: taskId, session_type: type });
}

export async function stopTimer(sessionId) {
  return request('POST', `${BASE}/timer/stop/`, { session_id: sessionId });
}

// ── Companion ─────────────────────────────────────────────────────────────────

export async function getDialogue(trigger, params = {}) {
  const qs = new URLSearchParams({ trigger, ...params });
  return request('GET', `${BASE}/dialogue/?${qs}`);
}

export async function getCompanionPresets() {
  return request('GET', `${BASE}/companion/presets/`);
}

export async function createCompanionPreset(data) {
  const fd = new FormData();
  fd.append('name', data.name ?? '');
  fd.append('animal_emoji', data.animal_emoji ?? '');
  fd.append('theme_color', data.theme_color ?? '');
  fd.append('system_prompt', data.system_prompt ?? '');
  fd.append('dialogue_map', JSON.stringify(data.dialogue_map ?? {}));
  if (data.image instanceof File) fd.append('image', data.image);
  return requestFormData('POST', `${BASE}/companion/presets/`, fd);
}

export async function deleteCompanionPreset(presetId) {
  return request('DELETE', `${BASE}/companion/presets/${presetId}/`);
}

export async function activateCompanionPreset(presetId) {
  return request('PATCH', `${BASE}/companion/presets/${presetId}/activate/`);
}

// ── History ───────────────────────────────────────────────────────────────────

export async function getWeeklyHistory(offset = 0) {
  return request('GET', `${BASE}/history/weekly/?week_offset=${offset}`);
}

// ── Recurring Tasks ───────────────────────────────────────────────────────────

export async function getRecurringTasks() {
  return request('GET', `${BASE}/recurring-tasks/`);
}

export async function createRecurringTask(data) {
  return request('POST', `${BASE}/recurring-tasks/`, data);
}

export async function deleteRecurringTask(taskId) {
  return request('DELETE', `${BASE}/recurring-tasks/${taskId}/`);
}

export async function getActiveCompanion() {
  return request('GET', `${BASE}/companion/me/`);
}
