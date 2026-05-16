import { getRenderZ, getTierForType } from './layer-registry.js';
import { startClockWidget, stopClockWidget } from './clock-widget.js';
import { createMenuButtonLayer } from './menu-button-widget.js';
import { createUserProfileWidget } from './user-profile-widget.js';
import { createAuthButtonsWidget } from './auth-buttons-widget.js';

function fitTextToBox(el) {
  if (!el || el.offsetWidth === 0) return;
  const boxWidth = el.offsetWidth;
  const boxHeight = el.offsetHeight;
  if (boxHeight === 0) return;

  const minSize = 6;
  const maxSize = 300;
  let low = minSize;
  let high = maxSize;
  let best = minSize;

  for (let i = 0; i < 16; i += 1) {
    const mid = (low + high) / 2;
    el.style.fontSize = `${mid}px`;
    const fits = el.scrollWidth <= boxWidth && el.scrollHeight <= boxHeight;
    if (fits) {
      best = mid;
      low = mid;
    } else {
      high = mid;
    }
  }

  el.style.fontSize = `${Math.floor(best)}px`;
}

function applyTextLayerStyles(el, s = {}) {
  const textColor = s.text_color || s.color;
  const borderWidth = Number(s.border_width || 0);

  el.style.whiteSpace = 'pre-wrap';
  if (s.font_family) el.style.fontFamily = s.font_family;
  if (s.font_weight) el.style.fontWeight = String(s.font_weight);
  if (s.font_style) el.style.fontStyle = s.font_style;
  if (s.text_decoration) el.style.textDecoration = s.text_decoration;
  if (s.text_align)     el.style.textAlign      = s.text_align;
  if (s.bg_color)        el.style.backgroundColor = s.bg_color;
  if (textColor) el.style.color = textColor;
  if (s.font_size && s.size_mode !== 'box') el.style.fontSize = s.font_size;
  if (s.letter_spacing) el.style.letterSpacing = s.letter_spacing;
  if (s.line_height) el.style.lineHeight = String(s.line_height);
  if (s.text_shadow) el.style.textShadow = s.text_shadow;
  if (borderWidth > 0) {
    el.style.border = `${borderWidth}px ${s.border_style || 'solid'} ${s.border_color || '#000000'}`;
  }
  if (s.size_mode === 'box') {
    requestAnimationFrame(() => fitTextToBox(el));
  }
}

export function normalizeLayer(layer) {
  const normalized = {
    ...layer,
    layer_tier: layer.layer_tier ?? getTierForType(layer.layer_type),
    z_index: Number(layer.z_index ?? 0),
    x: Number(layer.x ?? 0),
    y: Number(layer.y ?? 0),
    width: Number(layer.width ?? 200),
    height: Number(layer.height ?? 200),
    rotation_deg: Number(layer.rotation_deg ?? 0),
    scale: Number(layer.scale ?? 1),
    opacity: Number(layer.opacity ?? 1),
    enabled: layer.enabled !== false,
    settings_json: layer.settings_json || {},
  };

  const expectedTier = getTierForType(normalized.layer_type);
  if (expectedTier !== undefined && normalized.layer_tier !== expectedTier) {
    normalized.layer_tier = expectedTier;
  }
  return normalized;
}

export function sortLayersForRender(layers) {
  return [...layers].sort((a, b) => {
    if (a.layer_tier !== b.layer_tier) return a.layer_tier - b.layer_tier;
    if (a.z_index !== b.z_index) return a.z_index - b.z_index;
    return String(a.id).localeCompare(String(b.id), undefined, { numeric: true });
  });
}

export function applyLayerStyle(el, layer) {
  const s = layer.settings_json || {};

  // 단위 결정 (없으면 px 폴백)
  const xu = s.x_unit      || 'px';
  const yu = s.y_unit      || 'px';
  const wu = s.width_unit  || 'px';
  const hu = s.height_unit || 'px';

  el.style.position = 'absolute';
  el.style.left     = `${layer.x}${xu}`;
  el.style.top      = `${layer.y}${yu}`;
  el.style.width    = `${Math.max(0, layer.width)}${wu}`;
  el.style.height   = `${Math.max(0, layer.height)}${hu}`;

  const baseTransform = `translate(0px, 0px) rotate(${layer.rotation_deg}deg) scale(${layer.scale})`;
  el.style.transform      = baseTransform;
  el.dataset.baseTransform = baseTransform;
  el.style.opacity     = String(layer.opacity);
  el.style.zIndex      = String(getRenderZ(layer));
  el.style.pointerEvents = 'auto';

  // 이미지 레이어: fit 설정 적용
  const imageTypes = ['bg_image', 'main_image', 'parallax_far', 'parallax_near', 'parallax_ultra_near', 'sticker'];
  if (imageTypes.includes(layer.layer_type)) {
    const fit = s.fit || 'cover';
    const img = el.querySelector('img');
    if (img) img.style.objectFit = fit;
  }
}

export function createLayerElement(layer) {
  const el = document.createElement('div');
  el.className = 'scene-layer';
  el.dataset.layerId = String(layer.id);
  el.dataset.layerType = layer.layer_type;
  const settings = layer.settings_json || {};

  switch (layer.layer_type) {
    case 'bg_image':
    case 'main_image':
    case 'sticker':
    case 'parallax_far':
    case 'parallax_near':
    case 'parallax_ultra_near': {
      const img = document.createElement('img');
      img.alt = layer.settings_json?.alt || layer.layer_type;
      img.src = layer.settings_json?.asset_url || '';
      el.appendChild(img);
      break;
    }
    case 'bg_text':
    case 'text': {
      el.classList.add('scene-layer--text');
      el.textContent = settings.text || '';
      applyTextLayerStyles(el, settings);
      break;
    }
    case 'clock': {
      el.classList.add('scene-layer--clock');
      startClockWidget(layer.id, el, settings);
      break;
    }
    case 'menu_button': {
      el.classList.add('scene-layer--menu-button');
      el.appendChild(createMenuButtonLayer(layer));
      applyTextLayerStyles(el, settings);
      break;
    }
    case 'user_profile': {
      el.classList.add('scene-layer--user-profile');
      createUserProfileWidget(layer).then((wrapper) => {
        el.innerHTML = '';
        el.appendChild(wrapper);
      });
      break;
    }
    case 'auth_buttons': {
      el.classList.add('scene-layer--auth-buttons');
      createAuthButtonsWidget(layer).then((wrapper) => {
        el.innerHTML = '';
        el.appendChild(wrapper);
      });
      break;
    }
    default:
      el.textContent = `[Unsupported ${layer.layer_type}]`;
  }

  return el;
}

export function renderScene(root, scene, options = {}) {
  root.innerHTML = '';
  const layers = sortLayersForRender((scene.layers || []).map(normalizeLayer)).filter((layer) => layer.enabled);
  if (!layers.length) {
    const fallback = document.createElement('div');
    fallback.className = 'fallback-empty';
    fallback.textContent = '씬이 비어 있습니다. 관리자 패널에서 레이어를 추가하세요.';
    root.appendChild(fallback);
    return;
  }

  for (const layer of layers) {
    if (layer.layer_type === 'bg_image' && layer.settings_json?.asset_url) {
      const url = layer.settings_json.asset_url;
      document.body.style.backgroundImage = `url('${url}')`;
      document.body.style.backgroundSize = layer.settings_json.fit === 'contain' ? 'contain' : 'cover';
      document.body.style.backgroundPosition = 'center center';
      document.body.style.backgroundRepeat = 'no-repeat';
      document.body.style.backgroundAttachment = 'fixed';
      try {
        localStorage.setItem('bh_bg_url', url);
      } catch {}
    }
    const el = createLayerElement(layer);
    applyLayerStyle(el, layer);
    if (options.selectedLayerId != null && String(layer.id) === String(options.selectedLayerId)) {
      el.classList.add('scene-layer--selected');
    }
    root.appendChild(el);
  }

  if (typeof options.afterRender === 'function') {
    options.afterRender(layers);
  }
}

export function teardownDynamicWidgets(root) {
  root.querySelectorAll(".scene-layer[data-layer-type='clock']").forEach((el) => {
    stopClockWidget(Number(el.dataset.layerId));
  });
}
