export const LAYER_TYPE_TIER = {
  bg_image: -3,
  parallax_far: -2,
  bg_text: -1,
  main_image: 0,
  text: 1,
  clock: 1,
  menu_button: 1,
  user_profile: 1,
  sticker: 2,
  parallax_near: 3,
  parallax_ultra_near: 4,
};

export const TIER_BASE_Z = {
  '-3': 100,    // bg_image        (기존 -30000)
  '-2': 200,    // parallax_far    (기존 -20000)
  '-1': 300,    // bg_text         (기존 -10000)
   '0': 400,    // main_image      (기존 0)
   '1': 500,    // text/clock/menu (기존 10000)
   '2': 600,    // sticker         (기존 20000)
   '3': 700,    // parallax_near   (기존 30000)
   '4': 800,    // parallax_ultra_near (기존 40000)
};

export function getTierForType(layerType) {
  return LAYER_TYPE_TIER[layerType];
}

export function getRenderZ(layer) {
  const base = TIER_BASE_Z[String(layer.layer_tier)] ?? 0;
  return base + (layer.z_index ?? 0);
}
