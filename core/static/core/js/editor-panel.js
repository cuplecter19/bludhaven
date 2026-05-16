import { uploadAsset, uploadAssetFromUrl } from './asset-uploader.js';

const TEXT_STYLE_LAYER_TYPES = new Set(['text', 'bg_text', 'menu_button', 'clock', 'user_profile']);
const IMAGE_ASSET_LAYER_TYPES = new Set([
  'bg_image', 'parallax_far', 'main_image',
  'sticker', 'parallax_near', 'parallax_ultra_near'
]);
const HEX_COLOR_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

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

function parseUnitValue(str, fallbackUnit = 'px') {
  const value = String(str ?? '').trim();
  if (value.endsWith('%')) return { value: parseFloat(value) || 0, unit: '%' };
  if (value.endsWith('px')) return { value: parseFloat(value) || 0, unit: 'px' };
  return { value: parseFloat(value) || 0, unit: fallbackUnit };
}

function normalizeHexColor(value, fallback) {
  const normalized = String(value || '').trim();
  return HEX_COLOR_RE.test(normalized) ? normalized : fallback;
}

function setToggleState(button, isActive) {
  if (!button) return;
  button.classList.toggle('is-active', isActive);
  button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
}

function ensureSelectOption(select, value) {
  if (!select || !value) return;
  const hasOption = Array.from(select.options).some((option) => option.value === value);
  if (!hasOption) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
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
  const textStyleSection = document.getElementById('text-style-section');
  const clockFontSizeSection = document.getElementById('clock-font-size-section');
  const fontSelect = document.getElementById('prop-font-family');
  const fontList = document.getElementById('font-list');
  const assetUploadSection = document.getElementById('asset-upload-section');
  const fontManagementSection = document.getElementById('font-management-section');
  const assetLibrarySection = document.getElementById('asset-library-section');
  const assetThumbGrid = document.getElementById('asset-thumb-grid');
  const assetTabs = document.querySelectorAll('.asset-tab');
  const toggleItalic = document.getElementById('toggle-italic');
  const toggleUnderline = document.getElementById('toggle-underline');
  const toggleStrikethrough = document.getElementById('toggle-strikethrough');
  const toggleAlignLeft = document.getElementById('toggle-align-left');
  const toggleAlignCenter = document.getElementById('toggle-align-center');
  const toggleAlignRight = document.getElementById('toggle-align-right');
  let currentAssetKind = 'background';
  let assetCache = {};

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

  function getLayerTextValue(layer, settings) {
    if (layer.layer_type === 'menu_button') return settings.label ?? settings.text ?? '';
    if (layer.layer_type === 'user_profile') return settings.guest_text ?? settings.text ?? '';
    return settings.text ?? '';
  }

  function refreshSectionVisibility(layer) {
    const type = layer?.layer_type ?? null;

    const isTextLayer = TEXT_STYLE_LAYER_TYPES.has(type);
    textStyleSection.hidden = !isTextLayer;
    clockFontSizeSection.hidden = type !== 'clock';
    if (fontManagementSection) fontManagementSection.hidden = !isTextLayer;

    const isImageLayer = IMAGE_ASSET_LAYER_TYPES.has(type);
    assetLibrarySection.hidden = !isImageLayer;
    assetUploadSection.hidden = !isImageLayer;
  }

  function fillLayerProps(layer) {
    if (!layer) {
      refreshSectionVisibility(null);
      return;
    }

    const s = layer.settings_json || {};
    document.getElementById('prop-x').value = `${layer.x}${s.x_unit || 'px'}`;
    document.getElementById('prop-y').value = `${layer.y}${s.y_unit || 'px'}`;
    document.getElementById('prop-width').value = `${layer.width}${s.width_unit || 'px'}`;
    document.getElementById('prop-height').value = `${layer.height}${s.height_unit || 'px'}`;
    document.getElementById('prop-rotation').value = layer.rotation_deg ?? 0;
    document.getElementById('prop-scale').value = layer.scale ?? 1;
    document.getElementById('prop-opacity').value = layer.opacity ?? 1;
    document.getElementById('prop-z').value = layer.z_index ?? 0;
    document.getElementById('prop-text').value = getLayerTextValue(layer, s);
    document.getElementById('prop-url').value = s.url ?? '';
    document.getElementById('prop-asset').value = s.asset_url ?? '';
    document.getElementById('prop-fit').value = s.fit || 'cover';

    ensureSelectOption(fontSelect, s.font_family || '');
    fontSelect.value = s.font_family || '';
    document.getElementById('prop-font-weight').value = s.font_weight || '';
    document.getElementById('prop-size-mode').value = s.size_mode || 'font';
    document.getElementById('prop-font-size').value = s.font_size || '';
    document.getElementById('prop-letter-spacing').value = s.letter_spacing || '';
    document.getElementById('prop-line-height').value = s.line_height ?? '';

    const textColor = s.text_color || s.color || '#ffffff';
    const borderColor = s.border_color || '#000000';
    const bgColor = s.bg_color || '';
    document.getElementById('prop-bg-color-text').value = bgColor;
    if (bgColor) document.getElementById('prop-bg-color').value = normalizeHexColor(bgColor, '#ffffff');
    const bgOpacity = s.bg_color_opacity ?? 1;
    document.getElementById('prop-bg-opacity').value      = bgOpacity;
    document.getElementById('prop-bg-opacity-text').value = bgOpacity;

    document.getElementById('prop-text-color').value = normalizeHexColor(textColor, '#ffffff');
    document.getElementById('prop-text-color-text').value = textColor;
    document.getElementById('prop-border-width').value = s.border_width ?? 0;
    document.getElementById('prop-border-style').value = s.border_style || 'solid';
    document.getElementById('prop-border-color').value = normalizeHexColor(borderColor, '#000000');
    document.getElementById('prop-border-color-text').value = borderColor;
    document.getElementById('prop-time-font-size').value = s.time_font_size || '';
    document.getElementById('prop-date-font-size').value = s.date_font_size || '';

    setToggleState(toggleItalic, s.font_style === 'italic');
    setToggleState(toggleUnderline, s.text_decoration === 'underline');
    setToggleState(toggleStrikethrough, s.text_decoration === 'line-through');

    const align = s.text_align || 'left';
    setToggleState(toggleAlignLeft,   align === 'left');
    setToggleState(toggleAlignCenter, align === 'center');
    setToggleState(toggleAlignRight,  align === 'right');
    
    refreshSectionVisibility(layer);
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
        const panelBounds = panel.getBoundingClientRect();
        const newLeft = Math.max(0, Math.min(window.innerWidth - panelBounds.width, sl + ev.clientX - sx));
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

  function bindPanelResize() {
    const MIN_HEIGHT = 500;

    function getMaxHeight() {
      return window.innerHeight - 32;
    }

    function startResize(e, fromTop) {
      e.preventDefault();
      const startY = e.clientY;
      const rect = panel.getBoundingClientRect();
      const startHeight = rect.height;
      const startTop = rect.top;

      // Switch from max-height to explicit height so resize is smooth
      const prevMaxHeight = panel.style.maxHeight;
      panel.style.height = `${startHeight}px`;
      panel.style.maxHeight = 'none';

      const onMove = (ev) => {
        const delta = ev.clientY - startY;
        if (fromTop) {
          const newHeight = Math.min(getMaxHeight(), Math.max(MIN_HEIGHT, startHeight - delta));
          const newTop = startTop + (startHeight - newHeight);
          panel.style.height = `${newHeight}px`;
          panel.style.top = `${newTop}px`;
        } else {
          const newHeight = Math.min(getMaxHeight(), Math.max(MIN_HEIGHT, startHeight + delta));
          panel.style.height = `${newHeight}px`;
        }
      };
      const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        // Keep the user-set height but restore max-height constraint
        panel.style.maxHeight = prevMaxHeight;
      };
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp, { once: true });
    }

    const topHandle = document.getElementById('editor-panel-resize-top');
    const bottomHandle = document.getElementById('editor-panel-resize-bottom');
    if (topHandle) topHandle.addEventListener('pointerdown', (e) => startResize(e, true));
    if (bottomHandle) bottomHandle.addEventListener('pointerdown', (e) => startResize(e, false));
  }


  function injectFontFace(font) {
    if (!font.url) return;
    const id = `bh-font-${font.id}`;
    if (document.getElementById(id)) return;
    const style = document.createElement('style');
    style.id = id;
    style.textContent = `@font-face { font-family: '${font.font_family}'; src: url('${font.url}')${font.format ? ` format('${font.format}')` : ''}; font-display: swap; }`;
    document.head.appendChild(style);
  }

  function renderFontList(fonts) {
    fontList.innerHTML = '';
    for (const font of fonts) {
      const item = document.createElement('li');
      const label = document.createElement('span');
      label.textContent = `${font.name} (${font.font_family})`;
      label.style.fontFamily = font.font_family;

      const deleteButton = document.createElement('button');
      deleteButton.type = 'button';
      deleteButton.textContent = '삭제';
      deleteButton.addEventListener('click', async () => {
        const res = await api(`/api/editor/fonts/${font.id}/delete`, { method: 'DELETE' });
        if (!res.ok) return showError(res.error || 'font delete failed');
        await loadFonts();
      });

      item.append(label, deleteButton);
      fontList.appendChild(item);
    }
  }

  async function loadFonts() {
    const res = await api('/api/editor/fonts/');
    if (!res.ok) return;
    const currentValue = fontSelect.value;
    fontSelect.innerHTML = '<option value="">-- 기본 폰트 --</option>';
    for (const font of res.data) {
      const option = document.createElement('option');
      option.value = font.font_family;
      option.textContent = font.name;
      fontSelect.appendChild(option);
      injectFontFace(font);
    }
    ensureSelectOption(fontSelect, currentValue);
    fontSelect.value = currentValue || '';
    renderFontList(res.data);
  }

  function bindColorPair(pickerId, textId, fallback) {
    const picker = document.getElementById(pickerId);
    const text = document.getElementById(textId);

    picker.addEventListener('input', () => {
      text.value = picker.value;
    });
    text.addEventListener('input', () => {
      const normalized = normalizeHexColor(text.value, '');
      if (normalized) picker.value = normalized;
    });

    if (!text.value) text.value = fallback;
    picker.value = normalizeHexColor(text.value, fallback);
  }

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

      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'asset-thumb__delete';
      delBtn.textContent = '✕';
      delBtn.title = '에셋 삭제';
      delBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!confirm('이 에셋을 삭제하면 복구할 수 없습니다. 계속하시겠습니까?')) return;
        const res = await api(`/api/assets/${asset.id}/delete`, { method: 'DELETE' });
        if (!res.ok) return showError(res.error || '에셋 삭제 실패');
        delete assetCache[currentAssetKind];
        await loadAssets(currentAssetKind);
      });

      thumb.addEventListener('click', () => {
        const assetInput = document.getElementById('prop-asset');
        assetInput.value = asset.full_url;
        assetInput.style.outline = '2px solid #5cb2ff';
        setTimeout(() => {
          assetInput.style.outline = '';
        }, 1200);
      });

      thumb.append(img, delBtn);
      assetThumbGrid.appendChild(thumb);
    }
  }

  bindColorPair('prop-text-color', 'prop-text-color-text', '#ffffff');
  bindColorPair('prop-border-color', 'prop-border-color-text', '#000000');
  bindColorPair('prop-bg-color', 'prop-bg-color-text', '#ffffff');

  const bgOpacityRange = document.getElementById('prop-bg-opacity');
  const bgOpacityText  = document.getElementById('prop-bg-opacity-text');
  bgOpacityRange.addEventListener('input', () => { bgOpacityText.value = bgOpacityRange.value; });
  bgOpacityText.addEventListener('input', () => {
    const v = Math.min(1, Math.max(0, parseFloat(bgOpacityText.value) || 0));
    bgOpacityRange.value = v;
  });

  toggleItalic.addEventListener('click', () => setToggleState(toggleItalic, !toggleItalic.classList.contains('is-active')));
  toggleUnderline.addEventListener('click', () => {
    const nextState = !toggleUnderline.classList.contains('is-active');
    setToggleState(toggleUnderline, nextState);
    if (nextState) setToggleState(toggleStrikethrough, false);
  });
  toggleStrikethrough.addEventListener('click', () => {
    const nextState = !toggleStrikethrough.classList.contains('is-active');
    setToggleState(toggleStrikethrough, nextState);
    if (nextState) setToggleState(toggleUnderline, false);
  });

  function setAlign(align) {
  setToggleState(toggleAlignLeft,   align === 'left');
  setToggleState(toggleAlignCenter, align === 'center');
  setToggleState(toggleAlignRight,  align === 'right');
}

  toggleAlignLeft.addEventListener('click',   () => setAlign('left'));
  toggleAlignCenter.addEventListener('click', () => setAlign('center'));
  toggleAlignRight.addEventListener('click',  () => setAlign('right'));

  store.subscribe((state) => {
    refreshLayerList(state);
    syncDirty(state);
    fillLayerProps(getSelectedLayer());
    viewportSelect.value = state.viewportMode || 'both';
  });

  document.getElementById('undo-btn').addEventListener('click', () => {
    store.undo();
    render();
  });
  document.getElementById('redo-btn').addEventListener('click', () => {
    store.redo();
    render();
  });

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
    const px = parseUnitValue(document.getElementById('prop-x').value, s.x_unit || 'px');
    const py = parseUnitValue(document.getElementById('prop-y').value, s.y_unit || 'px');
    const pw = parseUnitValue(document.getElementById('prop-width').value, s.width_unit || 'px');
    const ph = parseUnitValue(document.getElementById('prop-height').value, s.height_unit || 'px');
    const textValue = document.getElementById('prop-text').value;
    let textDecoration = 'none';
    if (toggleUnderline.classList.contains('is-active')) {
      textDecoration = 'underline';
    } else if (toggleStrikethrough.classList.contains('is-active')) {
      textDecoration = 'line-through';
    }

    const settingsPatch = {
      ...s,
      x_unit: px.unit,
      y_unit: py.unit,
      width_unit: pw.unit,
      height_unit: ph.unit,
      fit: document.getElementById('prop-fit').value || s.fit || 'cover',
      url: document.getElementById('prop-url').value,
      asset_url: document.getElementById('prop-asset').value,
      font_family: fontSelect.value,
      font_weight: document.getElementById('prop-font-weight').value || '',
      font_style: toggleItalic.classList.contains('is-active') ? 'italic' : 'normal',
      text_decoration: textDecoration,
      text_align: toggleAlignCenter.classList.contains('is-active') ? 'center'
          : toggleAlignRight.classList.contains('is-active')  ? 'right'
          : 'left',
      size_mode: document.getElementById('prop-size-mode').value || 'font',
      font_size: document.getElementById('prop-font-size').value,
      letter_spacing: document.getElementById('prop-letter-spacing').value,
      line_height: document.getElementById('prop-line-height').value,
      text_color: document.getElementById('prop-text-color-text').value,
      bg_color: document.getElementById('prop-bg-color-text').value || '',
      bg_color_opacity: parseFloat(document.getElementById('prop-bg-opacity').value) ?? 1,
      border_width: Number(document.getElementById('prop-border-width').value || 0),
      border_style: document.getElementById('prop-border-style').value || 'solid',
      border_color: document.getElementById('prop-border-color-text').value,
      time_font_size: document.getElementById('prop-time-font-size').value,
      date_font_size: document.getElementById('prop-date-font-size').value,
    };

    if (layer.layer_type === 'menu_button') {
      settingsPatch.label = textValue;
      settingsPatch.text = textValue;
    } else if (layer.layer_type === 'user_profile') {
      settingsPatch.guest_text = textValue;
    } else {
      settingsPatch.text = textValue;
    }

    const patch = {
      x: px.value,
      y: py.value,
      width: pw.value,
      height: ph.value,
      rotation_deg: Number(document.getElementById('prop-rotation').value || 0),
      scale: Number(document.getElementById('prop-scale').value || 1),
      opacity: Number(document.getElementById('prop-opacity').value || 1),
      z_index: Number(document.getElementById('prop-z').value || 0),
      settings_json: settingsPatch,
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
    const scene = scenesRes.data.find((item) => item.id === sceneId);
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
    if (!layer) return;

    const patch = { settings_json: { ...(layer.settings_json || {}), asset_url: res.data.variants.full_webp || '' } };
    const updated = await api(`/api/editor/layers/${layer.id}`, { method: 'PATCH', body: patch });
    if (!updated.ok) return showError(updated.error || 'asset patch failed');
    store.patchLayer(layer.id, updated.data, { recordUndo: true, markDirty: true });
    render();
  });

  document.getElementById('asset-url-upload-btn').addEventListener('click', async () => {
    clearError();
    const urlInput = document.getElementById('asset-url-input');
    const kind = document.getElementById('asset-kind-select').value;
    const url = urlInput.value.trim();
    if (!url) return showError('이미지 URL을 입력하세요');

    const res = await uploadAssetFromUrl(url, kind);
    if (!res.ok) return showError(`${res.error_code || 'UPLOAD'}: ${res.error}`);

    delete assetCache[kind];
    if (currentAssetKind === kind) loadAssets(kind);

    const layer = getSelectedLayer();
    if (!layer) return;

    const patch = { settings_json: { ...(layer.settings_json || {}), asset_url: res.data.variants.full_webp || '' } };
    const updated = await api(`/api/editor/layers/${layer.id}`, { method: 'PATCH', body: patch });
    if (!updated.ok) return showError(updated.error || 'asset patch failed');
    store.patchLayer(layer.id, updated.data, { recordUndo: true, markDirty: true });
    render();
  });


  for (const tab of assetTabs) {
    tab.addEventListener('click', () => {
      assetTabs.forEach((item) => item.classList.remove('is-active'));
      tab.classList.add('is-active');
      currentAssetKind = tab.dataset.kind;
      delete assetCache[currentAssetKind];
      loadAssets(currentAssetKind);
    });
  }

  document.getElementById('font-url-register-btn').addEventListener('click', async () => {
    clearError();
    const res = await api('/api/editor/fonts/register-url', {
      method: 'POST',
      body: {
        name: document.getElementById('font-name-input').value,
        font_family: document.getElementById('font-family-input').value,
        url: document.getElementById('font-url-input').value,
      },
    });
    if (!res.ok) return showError(res.error || 'font register failed');
    await loadFonts();
  });

  document.getElementById('font-file-upload-btn').addEventListener('click', async () => {
    clearError();
    const file = document.getElementById('font-file-input').files?.[0];
    if (!file) return showError('폰트 파일을 선택하세요');
    const formData = new FormData();
    formData.append('name', document.getElementById('font-file-name-input').value);
    formData.append('font_family', document.getElementById('font-file-family-input').value);
    formData.append('file', file);
    const res = await api('/api/editor/fonts/upload', {
      method: 'POST',
      formData,
    });
    if (!res.ok) return showError(res.error || 'font upload failed');
    await loadFonts();
  });

  const initialState = store.getState();
  refreshLayerList(initialState);
  syncDirty(initialState);
  fillLayerProps(getSelectedLayer());
  viewportSelect.value = initialState.viewportMode || 'both';
  refreshSectionVisibility(getSelectedLayer());

  loadAssets(currentAssetKind);
  loadFonts();
  bindPanelDrag();
  bindPanelResize();
  refreshScenes().catch((error) => showError(error.message));

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
