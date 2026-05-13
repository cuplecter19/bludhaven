export const LAYER_TYPE_TIER = {
  bg_image: -3,
  parallax_far: -2,
  bg_text: -1,
  main_image: 0,
  text: 1,
  clock: 1,
  menu_button: 1,
  sticker: 2,
  parallax_near: 3,
  parallax_ultra_near: 4,
};

export const TIER_BASE_Z = {
  '-3': -30000,
  '-2': -20000,
  '-1': -10000,
  '0': 0,
  '1': 10000,
  '2': 20000,
  '3': 30000,
  '4': 40000,
};

export function getTierForType(layerType) {
  return LAYER_TYPE_TIER[layerType];
}

export function getRenderZ(layer) {
  const base = TIER_BASE_Z[String(layer.layer_tier)] ?? 0;
  return base + (layer.z_index ?? 0);
}
