import { uploadAsset } from './asset-uploader.js';

function getCsrfToken() {
  const match = document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)');
  return match ? match.pop() : '';
}

async function api(url, { method = 'GET', body, formData } = {}) {
  const options = {
    method,
    credentials: 'same-origin',
    headers: { 'X-CSRFToken': getCsrfToken() },
  };
  if (formData) {
    options.body = formData;
  } else if (body != null) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const res = await fetch(url, options);
  return res.json();
}

export function initEditorPanel({ store, root, render, onStickerToggle }) {
  const panel = document.getElementById('editor-panel');
  if (!panel) return null;
  panel.hidden = false;

  const errorEl = document.getElementById('editor-error');
  const dirtyEl = document.getElementById('dirty-indicator');
  const layerList = document.getElementById('layer-list');
  const sceneSelect = document.getElementById('scene-select');
  const viewportSelect = document.getElementById('viewport-mode-select');

  const propIds = {
    x: 'prop-x',
    y: 'prop-y',
    width: 'prop-width',
    height: 'prop-height',
    rotation_deg: 'prop-rotation',
    scale: 'prop-scale',
    opacity: 'prop-opacity',
    z_index: 'prop-z',
    text: 'prop-text',
    url: 'prop-url',
    asset_url: 'prop-asset',
  };

  const showError = (msg) => {
    errorEl.hidden = false;
    errorEl.textContent = msg;
  };

  const clearError = () => {
    errorEl.hidden = true;
    errorEl.textContent = '';
  };

  function getSelectedLayer() {
    const state = store.getState();
    return state.layers.find((layer) => String(layer.id) === String(state.selectedLayerId));
  }

  function refreshLayerList(state) {
    layerList.innerHTML = '';
    for (const layer of state.layers.slice().sort((a, b) => a.layer_tier - b.layer_tier || a.z_index - b.z_index || a.id - b.id)) {
      const li = document.createElement('li');
      li.textContent = `${layer.layer_type} t${layer.layer_tier} z${layer.z_index} #${layer.id}`;
      if (String(layer.id) === String(state.selectedLayerId)) li.classList.add('is-selected');
      li.addEventListener('click', () => store.selectLayer(layer.id));
      layerList.appendChild(li);
    }
  }

  function fillLayerProps(layer) {
    for (const [key, id] of Object.entries(propIds)) {
      const input = document.getElementById(id);
      if (!input) continue;
      if (key === 'text') input.value = layer?.settings_json?.text ?? '';
      else if (key === 'url') input.value = layer?.settings_json?.url ?? '';
      else if (key === 'asset_url') input.value = layer?.settings_json?.asset_url ?? '';
      else input.value = layer?.[key] ?? '';
    }
  }

  function syncDirty(state) {
    dirtyEl.textContent = state.isDirty ? 'Dirty' : 'Saved';
    dirtyEl.classList.toggle('is-dirty', state.isDirty);
  }

  async function refreshScenes() {
    const res = await api('/api/editor/scenes');
    if (!res.ok) return;
    const currentId = store.getState().scene?.id;
    sceneSelect.innerHTML = '';
    for (const scene of res.data) {
      const option = document.createElement('option');
      option.value = scene.id;
      option.textContent = `${scene.id} - ${scene.name}${scene.is_active ? ' (active)' : ''}`;
      if (scene.id === currentId) option.selected = true;
      sceneSelect.appendChild(option);
    }
  }

  async function loadActiveScene() {
    const res = await api('/api/mainpage/scene/active');
    if (!res.ok) throw new Error(res.error || 'scene load failed');
    store.setScene(res.data);
    render();
  }

  function bindPanelDrag() {
    const handle = document.getElementById('editor-panel-handle');
    let sx = 0;
    let sy = 0;
    let sl = 0;
    let st = 0;

    handle.addEventListener('pointerdown', (e) => {
      sx = e.clientX;
      sy = e.clientY;
      const rect = panel.getBoundingClientRect();
      sl = rect.left;
      st = rect.top;

      const onMove = (ev) => {
        panel.style.left = `${sl + ev.clientX - sx}px`;
        panel.style.top = `${st + ev.clientY - sy}px`;
        panel.style.right = 'auto';
      };
      const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
      };
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp, { once: true });
    });
  }

  store.subscribe((state) => {
    refreshLayerList(state);
    syncDirty(state);
    fillLayerProps(getSelectedLayer());
    viewportSelect.value = state.viewportMode || 'both';
  });

  document.getElementById('undo-btn').addEventListener('click', () => { store.undo(); render(); });
  document.getElementById('redo-btn').addEventListener('click', () => { store.redo(); render(); });

  document.getElementById('add-layer-btn').addEventListener('click', async () => {
    clearError();
    const sceneId = store.getState().scene?.id;
    if (!sceneId) return;
    const layerType = document.getElementById('new-layer-type').value;
    const res = await api('/api/editor/layers', {
      method: 'POST',
      body: { scene_id: sceneId, layer_type: layerType },
    });
    if (!res.ok) return showError(res.error || 'layer add failed');
    store.addLayer(res.data, { recordUndo: true, markDirty: true });
    render();
  });

  document.getElementById('prop-apply-btn').addEventListener('click', async () => {
    clearError();
    const layer = getSelectedLayer();
    if (!layer) return;
    const patch = {
      x: Number(document.getElementById(propIds.x).value || 0),
      y: Number(document.getElementById(propIds.y).value || 0),
      width: Number(document.getElementById(propIds.width).value || 0),
      height: Number(document.getElementById(propIds.height).value || 0),
      rotation_deg: Number(document.getElementById(propIds.rotation_deg).value || 0),
      scale: Number(document.getElementById(propIds.scale).value || 1),
      opacity: Number(document.getElementById(propIds.opacity).value || 1),
      z_index: Number(document.getElementById(propIds.z_index).value || 0),
      settings_json: {
        ...(layer.settings_json || {}),
        text: document.getElementById(propIds.text).value,
        url: document.getElementById(propIds.url).value,
        asset_url: document.getElementById(propIds.asset_url).value,
      },
    };

    const res = await api(`/api/editor/layers/${layer.id}`, { method: 'PATCH', body: patch });
    if (!res.ok) return showError(res.error || 'layer patch failed');
    store.patchLayer(layer.id, res.data, { recordUndo: true, markDirty: true });
    render();
  });

  document.getElementById('layer-delete-btn').addEventListener('click', async () => {
    const layer = getSelectedLayer();
    if (!layer) return;
    clearError();
    const res = await api(`/api/editor/layers/${layer.id}/delete`, { method: 'DELETE' });
    if (!res.ok) return showError(res.error || 'delete failed');
    store.removeLayer(layer.id, { recordUndo: true, markDirty: true });
    render();
  });

  document.getElementById('save-draft-btn').addEventListener('click', async () => {
    clearError();
    const { scene, layers, viewportMode } = store.getState();
    if (!scene?.id) return;

    const sorted = layers.slice().sort((a, b) => a.layer_tier - b.layer_tier || a.z_index - b.z_index || a.id - b.id);
    const orders = sorted.map((layer, i) => ({ id: layer.id, z_index: i }));
    const reorderRes = await api('/api/editor/layers/reorder', { method: 'POST', body: { orders } });
    if (!reorderRes.ok) return showError(reorderRes.error || 'reorder failed');

    const sceneRes = await api(`/api/editor/scenes/${scene.id}`, { method: 'PATCH', body: { viewport_mode: viewportMode } });
    if (!sceneRes.ok) return showError(sceneRes.error || 'scene save failed');

    await loadActiveScene();
    store.setDirty(false);
    render();
  });

  document.getElementById('revision-save-btn').addEventListener('click', async () => {
    clearError();
    const { scene, layers } = store.getState();
    if (!scene?.id) return;
    const res = await api('/api/editor/revisions', {
      method: 'POST',
      body: { scene_id: scene.id, snapshot_json: { ...scene, layers } },
    });
    if (!res.ok) return showError(res.error || 'revision save failed');
  });

  document.getElementById('scene-new-btn').addEventListener('click', async () => {
    clearError();
    const res = await api('/api/editor/scenes/create', {
      method: 'POST',
      body: { name: `Scene ${new Date().toISOString().slice(0, 19)}`, viewport_mode: 'both' },
    });
    if (!res.ok) return showError(res.error || 'scene create failed');
    await refreshScenes();
    sceneSelect.value = String(res.data.id);
    store.setScene(res.data);
    render();
  });

  sceneSelect.addEventListener('change', async () => {
    clearError();
    const sceneId = Number(sceneSelect.value);
    const scenesRes = await api('/api/editor/scenes');
    if (!scenesRes.ok) return;
    const scene = scenesRes.data.find((s) => s.id === sceneId);
    if (!scene) return;

    const active = await api('/api/mainpage/scene/active');
    if (!active.ok) return;
    if (active.data.id === sceneId) {
      store.setScene(active.data);
      render();
      return;
    }

    await api(`/api/editor/scenes/${sceneId}`, { method: 'PATCH', body: { is_active: true } });
    await loadActiveScene();
    await refreshScenes();
  });

  document.getElementById('scene-activate-btn').addEventListener('click', async () => {
    clearError();
    const sceneId = Number(sceneSelect.value);
    if (!sceneId) return;
    const res = await api(`/api/editor/scenes/${sceneId}`, { method: 'PATCH', body: { is_active: true } });
    if (!res.ok) return showError(res.error || 'scene activate failed');
    await loadActiveScene();
    await refreshScenes();
  });

  viewportSelect.addEventListener('change', () => {
    store.setViewportMode(viewportSelect.value);
  });

  document.getElementById('sticker-mode-btn').addEventListener('click', async () => {
    try {
      const enabled = await onStickerToggle();
      document.getElementById('sticker-mode-btn').textContent = enabled ? '스티커 저장/종료' : '스티커 편집';
    } catch (error) {
      showError(error.message || 'sticker mode error');
    }
  });

  document.getElementById('asset-upload-btn').addEventListener('click', async () => {
    clearError();
    const fileInput = document.getElementById('asset-file-input');
    const kind = document.getElementById('asset-kind-select').value;
    const file = fileInput.files?.[0];
    if (!file) return showError('파일을 선택하세요');

    const res = await uploadAsset(file, kind);
    if (!res.ok) return showError(`${res.error_code || 'UPLOAD'}: ${res.error}`);

    const layer = getSelectedLayer();
    if (layer) {
      const patch = { settings_json: { ...(layer.settings_json || {}), asset_url: res.data.variants.full_webp || '' } };
      const updated = await api(`/api/editor/layers/${layer.id}`, { method: 'PATCH', body: patch });
      if (!updated.ok) return showError(updated.error || 'asset patch failed');
      store.patchLayer(layer.id, updated.data, { recordUndo: true, markDirty: true });
      render();
    }
  });

  bindPanelDrag();

  refreshScenes().catch((e) => showError(e.message));

  return {
    async saveLayerPatch(layerId, patch) {
      const res = await api(`/api/editor/layers/${layerId}`, { method: 'PATCH', body: patch });
      if (!res.ok) throw new Error(res.error || 'patch failed');
      store.patchLayer(layerId, res.data, { recordUndo: false, markDirty: true });
      render();
      return res.data;
    },
    clearError,
  };
}
