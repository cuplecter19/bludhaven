export function createStickerEditController({
  root,
  getLayerById,
  patchLayerLocal,
  savePatch,
}) {
  const dirtyStickerMap = new Map();
  let enabled = false;

  function attachControls(stickerEl, layer) {
    stickerEl.classList.add('scene-layer--sticker-edit');
    if (stickerEl.querySelector('.sticker-hover-controls')) return;

    const controls = document.createElement('div');
    controls.className = 'sticker-hover-controls';

    const zDown = document.createElement('button');
    zDown.type = 'button';
    zDown.textContent = '-';

    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = `z:${layer.z_index}`;

    const zUp = document.createElement('button');
    zUp.type = 'button';
    zUp.textContent = '+';

    controls.append(zDown, badge, zUp);

    const resizeHandle = document.createElement('div');
    resizeHandle.className = 'sticker-resize-handle';

    const rotateHandle = document.createElement('div');
    rotateHandle.className = 'sticker-rotate-handle';

    stickerEl.append(controls, resizeHandle, rotateHandle);

    zUp.addEventListener('click', () => incrementStickerZ(layer.id, badge));
    zDown.addEventListener('click', () => decrementStickerZ(layer.id, badge));

    bindStickerResizeHandle(stickerEl, layer, resizeHandle);
    bindStickerRotateHandle(stickerEl, layer, rotateHandle);
  }

  function incrementStickerZ(layerId, badge) {
    const layer = getLayerById(layerId);
    if (!layer) return;
    const next = Math.min(999, (layer.z_index ?? 0) + 1);
    patchLayerLocal(layerId, { z_index: next });
    dirtyStickerMap.set(layerId, true);
    badge.textContent = `z:${next}`;
  }

  function decrementStickerZ(layerId, badge) {
    const layer = getLayerById(layerId);
    if (!layer) return;
    const next = Math.max(0, (layer.z_index ?? 0) - 1);
    patchLayerLocal(layerId, { z_index: next });
    dirtyStickerMap.set(layerId, true);
    badge.textContent = `z:${next}`;
  }

  function bindStickerResizeHandle(stickerEl, layer, handleEl) {
    let startX = 0;
    let startY = 0;
    let startW = 0;
    let startH = 0;

    handleEl.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      startX = e.clientX;
      startY = e.clientY;
      startW = layer.width;
      startH = layer.height;

      const onMove = (ev) => {
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;
        const keepRatio = ev.shiftKey;
        let nextW = Math.max(20, startW + dx);
        let nextH = Math.max(20, startH + dy);
        if (keepRatio) {
          const ratio = startW / Math.max(startH, 1);
          nextH = nextW / ratio;
        }
        patchLayerLocal(layer.id, { width: nextW, height: nextH });
        dirtyStickerMap.set(layer.id, true);
      };

      const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
      };

      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp, { once: true });
    });
  }

  function bindStickerRotateHandle(stickerEl, layer, handleEl) {
    handleEl.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const rect = stickerEl.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;

      const onMove = (ev) => {
        const rad = Math.atan2(ev.clientY - cy, ev.clientX - cx);
        const deg = (rad * 180) / Math.PI;
        patchLayerLocal(layer.id, { rotation_deg: deg });
        dirtyStickerMap.set(layer.id, true);
      };

      const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
      };

      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp, { once: true });
    });
  }

  async function saveStickerEdits() {
    const promises = [];
    for (const layerId of dirtyStickerMap.keys()) {
      const layer = getLayerById(layerId);
      if (!layer) continue;
      promises.push(savePatch(layerId, {
        z_index: layer.z_index,
        width: layer.width,
        height: layer.height,
        rotation_deg: layer.rotation_deg,
      }));
    }
    await Promise.all(promises);
    dirtyStickerMap.clear();
  }

  async function toggleStickerEditMode() {
    enabled = !enabled;
    const stickerEls = Array.from(root.querySelectorAll(".scene-layer[data-layer-type='sticker']"));

    if (enabled) {
      for (const stickerEl of stickerEls) {
        const layerId = Number(stickerEl.dataset.layerId);
        const layer = getLayerById(layerId);
        if (!layer) continue;
        attachControls(stickerEl, layer);
      }
      return true;
    }

    await saveStickerEdits();
    for (const stickerEl of stickerEls) {
      stickerEl.classList.remove('scene-layer--sticker-edit');
      stickerEl.querySelectorAll('.sticker-hover-controls,.sticker-resize-handle,.sticker-rotate-handle').forEach((el) => el.remove());
    }
    return false;
  }

  return {
    toggleStickerEditMode,
    saveStickerEdits,
    isEnabled: () => enabled,
  };
}
