/**
 * note_editor.js — Auto-save with 1.5s debounce + Ctrl+S
 * New note: POST to /atelier/api/notes/, get ID, replace URL with history.replaceState
 * Existing note: PATCH to /atelier/api/notes/<id>/
 */

(function () {
  const DEBOUNCE_MS = 1500;
  const BASE_URL = '/atelier/api/notes/';

  function getCsrfToken() {
    const name = 'csrftoken';
    const cookies = document.cookie.split(';');
    for (let c of cookies) {
      const [k, v] = c.trim().split('=');
      if (k === name) return decodeURIComponent(v);
    }
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  let noteId = (typeof window.__NOTE_ID__ !== 'undefined') ? window.__NOTE_ID__ : null;
  let saveTimer = null;
  let selectedTagId = null;

  const titleInput = document.getElementById('note-title');
  const bodyTextarea = document.getElementById('note-body');
  const saveIndicator = document.getElementById('save-indicator');
  const tagBtns = document.querySelectorAll('.tag-btn');
  const dropdown = document.getElementById('autocomplete-dropdown');

  if (!bodyTextarea) return;

  // Tag selector
  tagBtns.forEach(btn => {
    if (btn.classList.contains('active')) {
      selectedTagId = btn.dataset.tagId || null;
    }
    btn.addEventListener('click', () => {
      tagBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedTagId = btn.dataset.tagId || null;
      scheduleSave();
    });
  });

  function showIndicator(msg, isError) {
    saveIndicator.textContent = msg;
    saveIndicator.style.color = isError ? 'var(--mood-hard)' : 'var(--ink-soft)';
    saveIndicator.classList.add('visible');
    setTimeout(() => saveIndicator.classList.remove('visible'), 2000);
  }

  async function save() {
    const body = bodyTextarea.value;
    if (!body.trim()) return;

    const payload = {
      body,
      title: titleInput ? titleInput.value : '',
      tag_id: selectedTagId ? parseInt(selectedTagId) : null,
    };

    try {
      let resp;
      if (noteId) {
        resp = await fetch(`${BASE_URL}${noteId}/`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          body: JSON.stringify(payload),
        });
      } else {
        resp = await fetch(BASE_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          body: JSON.stringify(payload),
        });
        if (resp.ok) {
          const data = await resp.json();
          noteId = data.id;
          history.replaceState({}, '', `/atelier/spark/${noteId}/`);
          showIndicator('저장됨', false);
          return;
        }
      }
      if (resp.ok) {
        showIndicator('저장됨', false);
      } else {
        showIndicator('저장 실패 — 다시 시도', true);
      }
    } catch (err) {
      showIndicator('저장 실패 — 다시 시도', true);
    }
  }

  function scheduleSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, DEBOUNCE_MS);
  }

  if (titleInput) titleInput.addEventListener('input', scheduleSave);
  bodyTextarea.addEventListener('input', scheduleSave);

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      clearTimeout(saveTimer);
      save();
    }
  });

  // [[ autocomplete
  let acSearchTimer = null;

  bodyTextarea.addEventListener('keyup', (e) => {
    const text = bodyTextarea.value;
    const cursor = bodyTextarea.selectionStart;
    const before = text.slice(0, cursor);
    const match = before.match(/\[\[([^\]]{0,40})$/);
    if (!match) {
      hideDropdown();
      return;
    }
    const query = match[1];
    clearTimeout(acSearchTimer);
    acSearchTimer = setTimeout(() => fetchSuggestions(query), 300);
  });

  async function fetchSuggestions(query) {
    if (!query.trim()) { hideDropdown(); return; }
    try {
      const resp = await fetch(`/atelier/api/notes/search/?q=${encodeURIComponent(query)}`);
      const data = await resp.json();
      renderDropdown(data.notes || []);
    } catch { hideDropdown(); }
  }

  function renderDropdown(notes) {
    if (!notes.length) { hideDropdown(); return; }
    dropdown.innerHTML = '';
    notes.slice(0, 8).forEach(n => {
      const item = document.createElement('div');
      item.className = 'autocomplete-item';
      item.textContent = n.title || n.body_preview;
      item.addEventListener('mousedown', (e) => {
        e.preventDefault();
        insertReference(n.title || String(n.id));
        hideDropdown();
      });
      dropdown.appendChild(item);
    });
    dropdown.classList.remove('hidden');
  }

  function insertReference(ref) {
    const text = bodyTextarea.value;
    const cursor = bodyTextarea.selectionStart;
    const before = text.slice(0, cursor);
    const after = text.slice(cursor);
    const openIdx = before.lastIndexOf('[[');
    const newText = text.slice(0, openIdx) + `[[${ref}]]` + after;
    bodyTextarea.value = newText;
    scheduleSave();
  }

  function hideDropdown() {
    if (dropdown) dropdown.classList.add('hidden');
  }

  bodyTextarea.addEventListener('blur', () => setTimeout(hideDropdown, 200));
})();
