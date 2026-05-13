const HISTORY_LIMIT = 20;

export function createStateStore() {
  const state = {
    scene: null,
    layers: [],
    selectedLayerId: null,
    isDirty: false,
    viewportMode: 'both',
    stickerEditMode: false,
  };

  const listeners = new Set();
  const undoStack = [];
  const redoStack = [];

  function cloneCurrent() {
    return JSON.parse(JSON.stringify({
      scene: state.scene,
      layers: state.layers,
      selectedLayerId: state.selectedLayerId,
      isDirty: state.isDirty,
      viewportMode: state.viewportMode,
      stickerEditMode: state.stickerEditMode,
    }));
  }

  function emit() {
    for (const cb of listeners) cb(getState());
  }

  function pushUndo() {
    undoStack.push(cloneCurrent());
    if (undoStack.length > HISTORY_LIMIT) undoStack.shift();
    redoStack.length = 0;
  }

  function assignFrom(snapshot) {
    state.scene = snapshot.scene;
    state.layers = snapshot.layers;
    state.selectedLayerId = snapshot.selectedLayerId;
    state.isDirty = snapshot.isDirty;
    state.viewportMode = snapshot.viewportMode;
    state.stickerEditMode = snapshot.stickerEditMode;
  }

  return {
    subscribe(cb) { listeners.add(cb); return () => listeners.delete(cb); },
    getState() { return JSON.parse(JSON.stringify(state)); },
    setScene(scene) {
      state.scene = scene;
      state.layers = scene?.layers || [];
      state.viewportMode = scene?.viewport_mode || 'both';
      state.selectedLayerId = state.layers[0]?.id ?? null;
      state.isDirty = false;
      emit();
    },
    setLayers(layers, { markDirty = false, recordUndo = false } = {}) {
      if (recordUndo) pushUndo();
      state.layers = layers;
      if (markDirty) state.isDirty = true;
      emit();
    },
    patchLayer(layerId, patch, { markDirty = true, recordUndo = true } = {}) {
      if (recordUndo) pushUndo();
      state.layers = state.layers.map((layer) => layer.id === layerId ? { ...layer, ...patch } : layer);
      if (markDirty) state.isDirty = true;
      emit();
    },
    addLayer(layer, { markDirty = true, recordUndo = true } = {}) {
      if (recordUndo) pushUndo();
      state.layers = [...state.layers, layer];
      state.selectedLayerId = layer.id;
      if (markDirty) state.isDirty = true;
      emit();
    },
    removeLayer(layerId, { markDirty = true, recordUndo = true } = {}) {
      if (recordUndo) pushUndo();
      state.layers = state.layers.filter((layer) => layer.id !== layerId);
      if (state.selectedLayerId === layerId) state.selectedLayerId = state.layers[0]?.id ?? null;
      if (markDirty) state.isDirty = true;
      emit();
    },
    selectLayer(layerId) {
      state.selectedLayerId = layerId;
      emit();
    },
    setDirty(value) {
      state.isDirty = value;
      emit();
    },
    setViewportMode(mode) {
      state.viewportMode = mode;
      state.isDirty = true;
      emit();
    },
    setStickerEditMode(enabled) {
      state.stickerEditMode = enabled;
      emit();
    },
    undo() {
      const snapshot = undoStack.pop();
      if (!snapshot) return;
      redoStack.push(cloneCurrent());
      assignFrom(snapshot);
      emit();
    },
    redo() {
      const snapshot = redoStack.pop();
      if (!snapshot) return;
      undoStack.push(cloneCurrent());
      assignFrom(snapshot);
      emit();
    },
  };
}
