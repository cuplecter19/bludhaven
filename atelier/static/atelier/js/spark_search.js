/**
 * spark_search.js — Debounced live search for Spark note list
 */
(function () {
  const DEBOUNCE_MS = 300;
  const searchInput = document.getElementById('spark-search');
  const noteList = document.getElementById('note-list');
  if (!searchInput || !noteList) return;

  let searchTimer = null;
  let currentTag = new URLSearchParams(window.location.search).get('tag') || '';

  document.querySelectorAll('.tag-filter').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tag-filter').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTag = btn.dataset.tag || '';
      doSearch(searchInput.value);
    });
  });

  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => doSearch(searchInput.value), DEBOUNCE_MS);
  });

  async function doSearch(query) {
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set('q', query.trim());
      const resp = await fetch(`/atelier/api/notes/search/?${params}`);
      const data = await resp.json();
      let notes = data.notes || [];
      if (currentTag) notes = notes.filter(n => n.tag && n.tag.name === currentTag);
      renderNotes(notes);
    } catch (err) {
      // silently fail
    }
  }

  function renderNotes(notes) {
    if (!notes.length) {
      noteList.innerHTML = '<p class="empty-hint">검색 결과가 없어요.</p>';
      return;
    }
    noteList.innerHTML = notes.map(n => `
      <a class="note-card${n.is_pinned ? ' pinned' : ''}" href="/atelier/spark/${n.id}/">
        <div class="note-card-header">
          ${n.is_pinned ? '<span class="pin-indicator">✦</span>' : ''}
          ${n.tag ? `<span class="tag-label">${n.tag.name_ko}</span>` : ''}
        </div>
        <p class="note-card-title">${escapeHtml(n.title || n.body_preview)}</p>
        <div class="note-card-footer">
          ${n.ref_count > 0 ? `<span class="ref-count">↔ ${n.ref_count}</span>` : ''}
          <time class="note-card-date">${n.created_at.slice(0, 10)}</time>
        </div>
      </a>
    `).join('');
  }

  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
})();
