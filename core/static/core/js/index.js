import { createStateStore } from './state-store.js';
import { renderScene, teardownDynamicWidgets } from './scene-renderer.js';
import { initParallaxEngine } from './parallax-engine.js';
import { initEditorPanel } from './editor-panel.js';
import { createStickerEditController } from './sticker-edit-mode.js';

const root = document.getElementById('scene-root');
window.__CORE_MAINPAGE__ = JSON.parse(document.getElementById('core-mainpage-data')?.textContent || '{}');
const isAdmin = !!window.__CORE_MAINPAGE__?.isAdmin;
const store = createStateStore();
let parallaxEngine = null;
let editor = null;

try {
  const savedBg = localStorage.getItem('bh_bg_url');
  if (savedBg) {
    document.body.style.backgroundImage = `url('${savedBg}')`;
    document.body.style.backgroundSize = 'cover';
    document.body.style.backgroundPosition = 'center center';
    document.body.style.backgroundRepeat = 'no-repeat';
    document.body.style.backgroundAttachment = 'fixed';
  }
} catch {}

async function loadAndInjectFonts() {
  try {
    const res = await fetch('/api/mainpage/fonts', { credentials: 'same-origin' });
    const payload = await res.json();
    if (!payload.ok || !Array.isArray(payload.data)) return;
    for (const font of payload.data) {
      if (!font.url) continue;
      const id = `bh-font-${font.id}`;
      if (document.getElementById(id)) continue;
      const safeFontFamily = String(font.font_family).replace(/['"\\]/g, '');
      const safeUrl = String(font.url).replace(/['"\\]/g, '');
      const safeFormat = font.format ? String(font.format).replace(/['"\\]/g, '') : '';
      const style = document.createElement('style');
      style.id = id;
      style.textContent = `@font-face { font-family: '${safeFontFamily}'; src: url('${safeUrl}')${safeFormat ? ` format('${safeFormat}')` : ''}; font-display: swap; }`;
      document.head.appendChild(style);
    }
  } catch {}
}

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
  const [scene] = await Promise.all([loadActiveScene(), loadAndInjectFonts()]);
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
