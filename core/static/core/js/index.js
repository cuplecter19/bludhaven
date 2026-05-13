import { createStateStore } from './state-store.js';
import { renderScene, teardownDynamicWidgets } from './scene-renderer.js';
import { initParallaxEngine } from './parallax-engine.js';
import { initEditorPanel } from './editor-panel.js';
import { createStickerEditController } from './sticker-edit-mode.js';

const root = document.getElementById('scene-root');
const isAdmin = !!window.__CORE_MAINPAGE__?.isAdmin;
const store = createStateStore();
let parallaxEngine = null;
let editor = null;

export async function loadActiveScene() {
  const res = await fetch('/api/mainpage/scene/active', { credentials: 'same-origin' });
  const payload = await res.json();
  if (!payload.ok) throw new Error(payload.error || 'Failed to load scene');
  return payload.data || {
    id: null,
    name: 'Fallback Scene',
    is_active: true,
    viewport_mode: 'both',
    layers: [{
      id: 'fallback-msg',
      layer_type: 'text',
      layer_tier: 1,
      z_index: 0,
      enabled: true,
      x: 24,
      y: 24,
      width: 500,
      height: 80,
      rotation_deg: 0,
      scale: 1,
      opacity: 1,
      settings_json: { text: '활성 씬이 없습니다. 관리자에서 씬을 생성해주세요.' },
    }],
  };
}

function patchLayerLocal(layerId, patch) {
  store.patchLayer(layerId, patch, { markDirty: true, recordUndo: false });
  render();
}

function getLayerById(layerId) {
  const state = store.getState();
  return state.layers.find((layer) => String(layer.id) === String(layerId));
}

function render() {
  const state = store.getState();
  teardownDynamicWidgets(root);
  renderScene(root, { ...state.scene, layers: state.layers }, {
    selectedLayerId: state.selectedLayerId,
    afterRender(layers) {
      if (parallaxEngine) parallaxEngine.disposeParallaxEngine();
      parallaxEngine = initParallaxEngine(root, layers, { sensitivity: 1, maxOffset: 42 });
    },
  });
}

(async function boot() {
  const scene = await loadActiveScene();
  store.setScene(scene);
  render();

  const stickerController = createStickerEditController({
    root,
    getLayerById,
    patchLayerLocal,
    savePatch: async (layerId, patch) => editor?.saveLayerPatch(layerId, patch),
  });

  if (isAdmin) {
    editor = initEditorPanel({
      store,
      root,
      render,
      onStickerToggle: async () => {
        const enabled = await stickerController.toggleStickerEditMode();
        store.setStickerEditMode(enabled);
        return enabled;
      },
    });
  }

  window.addEventListener('beforeunload', () => {
    if (parallaxEngine) parallaxEngine.disposeParallaxEngine();
    teardownDynamicWidgets(root);
  });
})();
