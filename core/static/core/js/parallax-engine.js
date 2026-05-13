let rafId = null;

export function initParallaxEngine(container, layers, options = {}) {
  const state = {
    targetX: 0,
    targetY: 0,
    currentX: 0,
    currentY: 0,
    sensitivity: options.sensitivity ?? 1,
    maxOffset: options.maxOffset ?? 40,
    invert: !!options.invert,
  };

  const nodes = layers
    .filter((layer) => ['parallax_far', 'parallax_near', 'parallax_ultra_near'].includes(layer.layer_type) && layer.enabled)
    .map((layer) => ({
      layer,
      el: container.querySelector(`.scene-layer[data-layer-id='${layer.id}']`),
    }))
    .filter((x) => x.el);

  const onMouseMove = (e) => {
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    const dx = (e.clientX - cx) / cx;
    const dy = (e.clientY - cy) / cy;
    state.targetX = dx;
    state.targetY = dy;
  };

  function tickParallaxFrame() {
    state.currentX += (state.targetX - state.currentX) * 0.08;
    state.currentY += (state.targetY - state.currentY) * 0.08;

    for (const item of nodes) {
      const offset = computeParallaxOffset(item.layer, state);
      const base = item.el.dataset.baseTransform || '';
      item.el.style.transform = `${base} translate(${offset.x}px, ${offset.y}px)`;
    }
    rafId = requestAnimationFrame(tickParallaxFrame);
  }

  window.addEventListener('mousemove', onMouseMove, { passive: true });
  rafId = requestAnimationFrame(tickParallaxFrame);

  return {
    disposeParallaxEngine() {
      window.removeEventListener('mousemove', onMouseMove);
      if (rafId) cancelAnimationFrame(rafId);
    },
  };
}

export function computeParallaxOffset(layer, inputState) {
  const settings = layer.settings_json || {};
  const depth = settings.depth ?? (layer.layer_type === 'parallax_ultra_near' ? 1 : layer.layer_type === 'parallax_near' ? 0.6 : 0.3);
  const sensitivity = settings.sensitivity ?? inputState.sensitivity;
  const invert = settings.invert ?? inputState.invert;
  const maxOffset = settings.max_offset ?? inputState.maxOffset;

  const sign = invert ? -1 : 1;
  return {
    x: sign * inputState.currentX * depth * sensitivity * maxOffset,
    y: sign * inputState.currentY * depth * sensitivity * maxOffset,
  };
}
