/**
 * note_editor.js — Auto-save (1.5s debounce) + Ctrl+S
 *                  Markdown split-view (desktop) / tab-view (mobile)
 *                  [[...]] autocomplete (unchanged)
 *
 * Requires: marked.js and DOMPurify loaded before this script.
 */

(function () {
  const DEBOUNCE_MS = 1500;
  const RENDER_DEBOUNCE_MS = 300;
  const BASE_URL = '/atelier/api/notes/';

  // Allowed tags / attrs for DOMPurify sanitisation
  const PURIFY_TAGS = [
    'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'strong', 'em', 'code', 'pre',
    'blockquote', 'hr', 'a', 'span',
  ];
  const PURIFY_ATTR = ['href', 'target', 'rel', 'class', 'data-ref-id'];

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

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  let noteId = (typeof window.__NOTE_ID__ !== 'undefined') ? window.__NOTE_ID__ : null;
  let saveTimer = null;
  let renderTimer = null;
  let selectedTagId = null;

  const titleInput = document.getElementById('note-title');
  const bodyTextarea = document.getElementById('note-body');
  const saveIndicator = document.getElementById('save-indicator');
  const tagBtns = document.querySelectorAll('.tag-btn');
  const dropdown = document.getElementById('autocomplete-dropdown');
  const previewDiv = document.getElementById('md-preview');
  const tabEdit = document.getElementById('md-tab-edit');
  const tabPreview = document.getElementById('md-tab-preview');

  if (!bodyTextarea) return;

  // Configure marked
  if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true });
    const renderer = new marked.Renderer();
    renderer.html = () => '';  // strip raw HTML blocks
    marked.use({ renderer });
  }

  // Rendering pipeline
  function preprocessReferences(text) {
    return text.replace(/\[\[([^\]]{1,200})\]\]/g, (match, ref) => {
      return '<span class="md-ref" data-ref-id="' + escapeHtml(ref) + '">' + escapeHtml(ref) + '</span>';
    });
  }

  function renderMarkdown(rawText) {
    if (!previewDiv) return;
    if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') return;

    const withRefs = preprocessReferences(rawText);
    const markedHtml = marked.parse(withRefs);
    const clean = DOMPurify.sanitize(markedHtml, {
      ALLOWED_TAGS: PURIFY_TAGS,
      ALLOWED_ATTR: PURIFY_ATTR,
    });

    const tmp = document.createElement('div');
    tmp.innerHTML = clean;
    tmp.querySelectorAll('a').forEach(function(a) {
      a.setAttribute('target', '_blank');
      a.setAttribute('rel', 'noopener noreferrer');
    });
    previewDiv.innerHTML = tmp.innerHTML;
  }

  function scheduleRender() {
    clearTimeout(renderTimer);
    renderTimer = setTimeout(function() { renderMarkdown(bodyTextarea.value); }, RENDER_DEBOUNCE_MS);
  }

  if (previewDiv) renderMarkdown(bodyTextarea.value);

  // Tag selector
  tagBtns.forEach(function(btn) {
    if (btn.classList.contains('active')) selectedTagId = btn.dataset.tagId || null;
    btn.addEventListener('click', function() {
      tagBtns.forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      selectedTagId = btn.dataset.tagId || null;
      scheduleSave();
    });
  });

  function showIndicator(msg, isError) {
    saveIndicator.textContent = msg;
    saveIndicator.style.color = isError ? 'var(--mood-hard)' : 'var(--ink-soft)';
    saveIndicator.classList.add('visible');
    setTimeout(function() { saveIndicator.classList.remove('visible'); }, 2000);
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
        resp = await fetch(BASE_URL + noteId + '/', {
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
          history.replaceState({}, '', '/atelier/spark/' + noteId + '/');
          showIndicator('저장됨', false);
          const exportLink = document.getElementById('note-export-link');
          if (exportLink) exportLink.href = '/atelier/spark/' + noteId + '/export/';
          return;
        }
      }
      if (resp.ok) showIndicator('저장됨', false);
      else showIndicator('저장 실패 — 다시 시도', true);
    } catch (err) {
      showIndicator('저장 실패 — 다시 시도', true);
    }
  }

  function scheduleSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, DEBOUNCE_MS);
  }

  if (titleInput) titleInput.addEventListener('input', scheduleSave);
  bodyTextarea.addEventListener('input', function() {
    scheduleSave();
    scheduleRender();
  });

  document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      clearTimeout(saveTimer);
      save();
    }
  });

  // Tab key → 2 spaces
  bodyTextarea.addEventListener('keydown', function(e) {
    if (e.key === 'Tab') {
      e.preventDefault();
      var start = bodyTextarea.selectionStart;
      var end = bodyTextarea.selectionEnd;
      bodyTextarea.value = bodyTextarea.value.slice(0, start) + '  ' + bodyTextarea.value.slice(end);
      bodyTextarea.selectionStart = bodyTextarea.selectionEnd = start + 2;
    }
  });

  // Mobile tab switching
  function activateTab(which) {
    if (!tabEdit || !tabPreview || !previewDiv) return;
    if (which === 'edit') {
      bodyTextarea.style.display = '';
      previewDiv.style.display = 'none';
      tabEdit.classList.add('active');
      tabPreview.classList.remove('active');
    } else {
      renderMarkdown(bodyTextarea.value);
      bodyTextarea.style.display = 'none';
      previewDiv.style.display = '';
      tabEdit.classList.remove('active');
      tabPreview.classList.add('active');
    }
  }

  if (tabEdit) tabEdit.addEventListener('click', function() { activateTab('edit'); });
  if (tabPreview) tabPreview.addEventListener('click', function() { activateTab('preview'); });

  // [[ autocomplete
  let acSearchTimer = null;

  bodyTextarea.addEventListener('keyup', function(e) {
    var text = bodyTextarea.value;
    var cursor = bodyTextarea.selectionStart;
    var before = text.slice(0, cursor);
    var match = before.match(/\[\[([^\]]{0,40})$/);
    if (!match) { hideDropdown(); return; }
    var query = match[1];
    clearTimeout(acSearchTimer);
    acSearchTimer = setTimeout(function() { fetchSuggestions(query); }, 300);
  });

  async function fetchSuggestions(query) {
    if (!query.trim()) { hideDropdown(); return; }
    try {
      const resp = await fetch('/atelier/api/notes/search/?q=' + encodeURIComponent(query));
      const data = await resp.json();
      renderDropdown(data.notes || []);
    } catch (err) {
      console.error('[note_editor] Autocomplete fetch failed:', err);
      hideDropdown();
    }
  }

  function renderDropdown(notes) {
    if (!notes.length) { hideDropdown(); return; }
    dropdown.innerHTML = '';
    notes.slice(0, 8).forEach(function(n) {
      var item = document.createElement('div');
      item.className = 'autocomplete-item';
      item.textContent = n.title || n.body_preview;
      item.addEventListener('mousedown', function(e) {
        e.preventDefault();
        insertReference(n.title || String(n.id));
        hideDropdown();
      });
      dropdown.appendChild(item);
    });
    dropdown.classList.remove('hidden');
  }

  function insertReference(ref) {
    var text = bodyTextarea.value;
    var cursor = bodyTextarea.selectionStart;
    var before = text.slice(0, cursor);
    var after = text.slice(cursor);
    var openIdx = before.lastIndexOf('[[');
    bodyTextarea.value = text.slice(0, openIdx) + '[[' + ref + ']]' + after;
    scheduleSave();
    scheduleRender();
  }

  function hideDropdown() {
    if (dropdown) dropdown.classList.add('hidden');
  }

  bodyTextarea.addEventListener('blur', function() { setTimeout(hideDropdown, 200); });

  // Expose save function for publish button
  window.__saveNote = save;
})();
