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

  // 기존 fillLayerProps 교체
function fillLayerProps(layer) {
  if (!layer) return;
  const s = layer.settings_json || {};

  // 좌표/크기는 값+단위 문자열로 표시 (ex: "50%", "200px")
  document.getElementById('prop-x').value      = `${layer.x}${s.x_unit || 'px'}`;
  document.getElementById('prop-y').value      = `${layer.y}${s.y_unit || 'px'}`;
  document.getElementById('prop-width').value  = `${layer.width}${s.width_unit || 'px'}`;
  document.getElementById('prop-height').value = `${layer.height}${s.height_unit || 'px'}`;

  document.getElementById('prop-rotation').value = layer.rotation_deg ?? 0;
  document.getElementById('prop-scale').value    = layer.scale ?? 1;
  document.getElementById('prop-opacity').value  = layer.opacity ?? 1;
  document.getElementById('prop-z').value        = layer.z_index ?? 0;
  document.getElementById('prop-text').value     = s.text  ?? '';
  document.getElementById('prop-url').value      = s.url   ?? '';
  document.getElementById('prop-asset').value    = s.asset_url ?? '';

  // fit 셀렉트 반영
  const fitSelect = document.getElementById('prop-fit');
  if (fitSelect) fitSelect.value = s.fit || 'cover';
}

function parseUnitValue(str, fallbackUnit = 'px') {
  const s = String(str ?? '').trim();
  if (s.endsWith('%'))  return { value: parseFloat(s) || 0, unit: '%'  };
  if (s.endsWith('px')) return { value: parseFloat(s) || 0, unit: 'px' };
  // 단위 없이 숫자만 입력하면 fallback 단위 사용
  return { value: parseFloat(s) || 0, unit: fallbackUnit };
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
        const rect = panel.getBoundingClientRect();
        const newLeft = Math.max(0, Math.min(window.innerWidth - rect.width, sl + ev.clientX - sx));
        const newTop = Math.max(0, Math.min(window.innerHeight - 40, st + ev.clientY - sy));
        panel.style.left = `${newLeft}px`;
        panel.style.top = `${newTop}px`;
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
  const s = layer.settings_json || {};

  const px = parseUnitValue(document.getElementById('prop-x').value,     s.x_unit      || 'px');
  const py = parseUnitValue(document.getElementById('prop-y').value,     s.y_unit      || 'px');
  const pw = parseUnitValue(document.getElementById('prop-width').value,  s.width_unit  || 'px');
  const ph = parseUnitValue(document.getElementById('prop-height').value, s.height_unit || 'px');

  const patch = {
    x:            px.value,
    y:            py.value,
    width:        pw.value,
    height:       ph.value,
    rotation_deg: Number(document.getElementById('prop-rotation').value || 0),
    scale:        Number(document.getElementById('prop-scale').value    || 1),
    opacity:      Number(document.getElementById('prop-opacity').value  || 1),
    z_index:      Number(document.getElementById('prop-z').value        || 0),
    settings_json: {
      ...s,
      // 단위 저장
      x_unit:      px.unit,
      y_unit:      py.unit,
      width_unit:  pw.unit,
      height_unit: ph.unit,
      // 기타 설정
      fit:         document.getElementById('prop-fit')?.value || s.fit || 'cover',
      text:        document.getElementById('prop-text').value,
      url:         document.getElementById('prop-url').value,
      asset_url:   document.getElementById('prop-asset').value,
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
    const { scene, viewportMode } = store.getState();
    if (!scene?.id) return;

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
    const now = new Date();
    const formatted = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const res = await api('/api/editor/scenes/create', {
      method: 'POST',
      body: { name: `Scene ${formatted}`, viewport_mode: 'both' },
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

    delete assetCache[kind];
    if (currentAssetKind === kind) loadAssets(kind);

    const layer = getSelectedLayer();
    if (layer) {
      const patch = { settings_json: { ...(layer.settings_json || {}), asset_url: res.data.variants.full_webp || '' } };
      const updated = await api(`/api/editor/layers/${layer.id}`, { method: 'PATCH', body: patch });
      if (!updated.ok) return showError(updated.error || 'asset patch failed');
      store.patchLayer(layer.id, updated.data, { recordUndo: true, markDirty: true });
      render();
    }
  });

    // initEditorPanel 내부, bindPanelDrag() 호출 위에 추가

  // ── 에셋 라이브러리 ─────────────────────────────────────────
  const assetLibrarySection = document.getElementById('asset-library-section');
  const assetThumbGrid      = document.getElementById('asset-thumb-grid');
  const assetTabs           = document.querySelectorAll('.asset-tab');
  let currentAssetKind      = 'background';
  let assetCache            = {};  // kind → 데이터 캐시

  async function loadAssets(kind) {
    if (assetCache[kind]) {
      renderAssetGrid(assetCache[kind]);
      return;
    }
    const res = await api(`/api/assets?kind=${kind}`);
    if (!res.ok) return;
    assetCache[kind] = res.data;
    renderAssetGrid(res.data);
  }

  function renderAssetGrid(assets) {
  assetThumbGrid.innerHTML = '';
  if (!assets.length) {
    assetThumbGrid.innerHTML = '<p class="asset-empty">업로드된 에셋 없음</p>';
    return;
  }
  for (const asset of assets) {
    const thumb = document.createElement('div');
    thumb.className = 'asset-thumb';
    thumb.title = `${asset.width}×${asset.height} · ${(asset.bytes / 1024).toFixed(0)}KB`;

    const img = document.createElement('img');
    img.src = asset.thumb_url;
    img.alt = asset.kind;
    img.loading = 'lazy';

    // 삭제 버튼
    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'asset-thumb__delete';
    delBtn.textContent = '✕';
    delBtn.title = '에셋 삭제';
    delBtn.addEventListener('click', async (e) => {
      e.stopPropagation();  // 썸네일 클릭(URL 삽입)과 분리
      if (!confirm('이 에셋을 삭제하면 복구할 수 없습니다. 계속하시겠습니까?')) return;
      const res = await api(`/api/assets/${asset.id}/delete`, { method: 'DELETE' });
      if (!res.ok) return showError(res.error || '에셋 삭제 실패');
      // 캐시 무효화 후 목록 갱신
      delete assetCache[currentAssetKind];
      await loadAssets(currentAssetKind);
    });

    // 썸네일 클릭 → asset_url 삽입
    thumb.addEventListener('click', () => {
      const assetInput = document.getElementById('prop-asset');
      if (assetInput) {
        assetInput.value = asset.full_url;
        assetInput.style.outline = '2px solid #5cb2ff';
        setTimeout(() => { assetInput.style.outline = ''; }, 1200);
      }
    });

    thumb.append(img, delBtn);
    assetThumbGrid.appendChild(thumb);
  }
}

  // 탭 클릭 이벤트
  for (const tab of assetTabs) {
    tab.addEventListener('click', () => {
      assetTabs.forEach((t) => t.classList.remove('is-active'));
      tab.classList.add('is-active');
      currentAssetKind = tab.dataset.kind;
      // 탭 전환 시 캐시 무효화 (새 업로드 반영)
      delete assetCache[currentAssetKind];
      loadAssets(currentAssetKind);
    });
  }

  // 씬이 로드됐을 때 에셋 라이브러리 표시
  // 기존 store.subscribe 콜백 안에 추가:
  store.subscribe((state) => {
    refreshLayerList(state);
    syncDirty(state);
    fillLayerProps(getSelectedLayer());
    viewportSelect.value = state.viewportMode || 'both';

    // ↓ 추가: 씬이 있으면 에셋 라이브러리 표시
    if (state.scene?.id) {
      assetLibrarySection.hidden = false;
    }
  });

  // 업로드 성공 후 캐시 무효화 (기존 asset-upload-btn 핸들러 끝에 추가)
  // delete assetCache[kind]; loadAssets(currentAssetKind);
  // → 업로드 버튼 핸들러 마지막에 아래 두 줄 추가:
  //   delete assetCache[kind];
  //   if (currentAssetKind === kind) loadAssets(kind);

  // 초기 로드
  loadAssets(currentAssetKind);

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
