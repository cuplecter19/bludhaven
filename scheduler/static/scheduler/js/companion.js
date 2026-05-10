import {
  getDialogue,
  getCompanionPresets,
  createCompanionPreset,
  deleteCompanionPreset,
  activateCompanionPreset,
} from './api.js';

// ── 말풍선 ────────────────────────────────────────────────────────────────────

// 트리거별 당일 1회 제한 여부 (이벤트성 트리거는 제한 없음)
const ONCE_PER_DAY_TRIGGERS = new Set([
  'morning', 'afternoon', 'evening',
  'meal_breakfast', 'meal_lunch', 'meal_dinner', 'bedtime_nudge',
]);

function todayKey(trigger) {
  const d = new Date();
  const ymd = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return `greeted_${trigger}_${ymd}`;
}

function hasGreetedToday(trigger) {
  return ONCE_PER_DAY_TRIGGERS.has(trigger) && localStorage.getItem(todayKey(trigger)) === '1';
}

function markGreeted(trigger) {
  if (ONCE_PER_DAY_TRIGGERS.has(trigger)) localStorage.setItem(todayKey(trigger), '1');
}

let bubbleFadeTimer = null;

export async function showDialogue(trigger, params = {}) {
  if (hasGreetedToday(trigger)) return;

  let data;
  try {
    data = await getDialogue(trigger, params);
  } catch {
    return;
  }
  if (!data?.text) return;

  const bubble = document.getElementById('companion-bubble');
  if (!bubble) return;

  bubble.textContent = data.text;
  bubble.style.opacity = '1';
  bubble.style.display = 'block';
  markGreeted(trigger);

  if (bubbleFadeTimer) clearTimeout(bubbleFadeTimer);
  bubbleFadeTimer = setTimeout(() => {
    bubble.style.transition = 'opacity 0.6s';
    bubble.style.opacity = '0';
    setTimeout(() => { bubble.style.display = 'none'; }, 650);
  }, 3000);
}

// ── 시간대별 트리거 ───────────────────────────────────────────────────────────

export function initTimeBasedTriggers() {
  function check() {
    const now = new Date();
    const h = now.getHours();
    const m = now.getMinutes();
    const hm = h * 60 + m;

    const inBreak = window.timerRunning === true;

    if (hm >= 5 * 60 && hm < 11 * 60)  showDialogue('morning');
    if (hm >= 11 * 60 && hm < 17 * 60) showDialogue('afternoon');
    if (hm >= 17 * 60 && hm < 24 * 60) showDialogue('evening');

    if (!inBreak) {
      if (hm >= 7 * 60 && hm <= 9 * 60)        showDialogue('meal_breakfast');
      if (hm >= 12 * 60 && hm <= 13 * 60 + 30)  showDialogue('meal_lunch');
      if (hm >= 18 * 60 && hm <= 20 * 60)       showDialogue('meal_dinner');
      if (hm >= 23 * 60)                         showDialogue('bedtime_nudge');
    }
  }

  check();
  setInterval(check, 60_000);
}

// ── 유휴 감지 ─────────────────────────────────────────────────────────────────

export function initIdleTrigger() {
  let lastActive = Date.now();
  let firedThisSession = false;

  ['mousemove', 'keydown', 'click'].forEach(evt =>
    document.addEventListener(evt, () => { lastActive = Date.now(); }, { passive: true })
  );

  setInterval(() => {
    if (firedThisSession) return;
    if (Date.now() - lastActive >= 20 * 60 * 1000) {
      showDialogue('long_idle');
      firedThisSession = true;
    }
  }, 60_000);
}

// ── 헬퍼 ──────────────────────────────────────────────────────────────────────

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = e => resolve(e.target.result);
    reader.onerror = reject;
    reader.readAsText(file);
  });
}

function extractDialogueMap(parsed) {
  if (Array.isArray(parsed)) return parsed[0]?.fields?.dialogue_map ?? {};
  return parsed;
}

function showModalMessage(msg, type = 'error') {
  const el = document.getElementById('modal-error');
  if (!el) return;
  el.textContent = msg;
  el.dataset.type = type;
  el.hidden = false;
}

function hideModalMessage() {
  const el = document.getElementById('modal-error');
  if (el) el.hidden = true;
}

// ── 프리셋 목록 ───────────────────────────────────────────────────────────────

export async function loadPresetList() {
  let presets;
  try {
    presets = await getCompanionPresets();
  } catch {
    return;
  }

  const list = document.getElementById('preset-list');
  if (!list) return;

  list.innerHTML = '';
  presets.forEach(preset => {
    const card = document.createElement('div');
    card.className = 'preset-card';
    card.dataset.presetId = preset.id;
    card.dataset.imageUrl = preset.image_url || '';
    card.dataset.emoji = preset.animal_emoji || '🦇';

    const info = document.createElement('div');
    info.className = 'preset-info';

    if (preset.image_url) {
      const img = document.createElement('img');
      img.src = preset.image_url;
      img.alt = preset.name;
      img.className = 'preset-thumb';
      info.append(img);
    } else {
      const emojiEl = document.createElement('span');
      emojiEl.className = 'preset-emoji-display';
      emojiEl.textContent = preset.animal_emoji || '🦇';
      info.append(emojiEl);
    }

    const nameEl = document.createElement('span');
    nameEl.textContent = preset.name;
    info.append(nameEl);

    const activateBtn = document.createElement('button');
    activateBtn.type = 'button';
    activateBtn.textContent = '적용';
    activateBtn.addEventListener('click', () => onActivatePreset(preset.id));

    card.append(info, activateBtn);

    if (!preset.is_default) {
      const deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.textContent = '삭제';
      deleteBtn.addEventListener('click', () => onDeletePreset(preset.id));
      card.append(deleteBtn);
    }

    list.append(card);
  });
}

export async function onActivatePreset(presetId) {
  try {
    await activateCompanionPreset(presetId);
  } catch {
    return;
  }

  const card = document.querySelector(`[data-preset-id="${presetId}"]`);
  const avatar = document.getElementById('companion-avatar');
  if (avatar && card) {
    if (card.dataset.imageUrl) {
      avatar.innerHTML = `<img src="${card.dataset.imageUrl}" alt=""
        style="width:40px;height:40px;border-radius:50%;object-fit:cover;display:block">`;
    } else {
      avatar.textContent = card.dataset.emoji || '🦇';
    }
  }

  closeCompanionModal();
}

export async function onDeletePreset(presetId) {
  if (!confirm('이 프리셋을 삭제할까요?')) return;
  try {
    await deleteCompanionPreset(presetId);
  } catch {
    return;
  }
  loadPresetList();
}

// ── 프리셋 저장 ───────────────────────────────────────────────────────────────

const DIALOGUE_TRIGGERS = [
  'morning', 'afternoon', 'evening',
  'meal_breakfast', 'meal_lunch', 'meal_dinner', 'bedtime_nudge',
  'task_start', 'task_done', 'task_skip',
  'cheer_first_task', 'cheer_halfway', 'cheer_focus_long',
  'all_tasks_done', 'day_complete', 'streak_praise',
  'long_idle', 'return_from_break', 'overdue_gentle',
];

export async function onSavePreset() {
  const name = document.getElementById('preset-name')?.value.trim();
  if (!name) return;

  hideModalMessage();

  // dialogue_map: JSON 파일이 있으면 그 파일을 파싱, 없으면 textarea에서 수집
  let dialogue_map;
  const jsonFile = document.getElementById('preset-json-file')?.files?.[0];
  if (jsonFile) {
    try {
      const text = await readFileAsText(jsonFile);
      dialogue_map = extractDialogueMap(JSON.parse(text));
    } catch {
      showModalMessage('JSON 형식이 올바르지 않아요');
      return;
    }
  } else {
    dialogue_map = {};
    DIALOGUE_TRIGGERS.forEach(trigger => {
      const el = document.getElementById(`dlg-${trigger}`);
      if (!el) return;
      const lines = el.value.split('\n').map(l => l.trim()).filter(Boolean);
      if (lines.length) dialogue_map[trigger] = lines;
    });
  }

  const data = {
    name,
    animal_emoji:  document.getElementById('preset-emoji')?.value.trim()  ?? '',
    theme_color:   document.getElementById('preset-color')?.value.trim()  ?? '',
    system_prompt: document.getElementById('preset-prompt')?.value.trim() ?? '',
    dialogue_map,
    image: document.getElementById('preset-image-file')?.files?.[0] ?? null,
  };

  try {
    await createCompanionPreset(data);
  } catch {
    return;
  }

  // 폼 초기화
  ['preset-name', 'preset-emoji', 'preset-color', 'preset-prompt',
   'preset-image-file', 'preset-json-file'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  DIALOGUE_TRIGGERS.forEach(trigger => {
    const el = document.getElementById(`dlg-${trigger}`);
    if (el) el.value = '';
  });
  const imgPreview = document.getElementById('preset-image-preview');
  if (imgPreview) { imgPreview.src = ''; imgPreview.hidden = true; }
  const emojiText = document.getElementById('emoji-preview-text');
  if (emojiText) { emojiText.textContent = '🦇'; emojiText.style.display = ''; }
  hideModalMessage();

  loadPresetList();
}

// ── 모달 ──────────────────────────────────────────────────────────────────────

function closeCompanionModal() {
  const modal = document.getElementById('companion-modal');
  if (modal) modal.style.display = 'none';
}

export function initCompanionModal() {
  const avatar = document.getElementById('companion-avatar');
  const modal  = document.getElementById('companion-modal');
  const overlay = document.getElementById('companion-modal-overlay');
  const closeBtn = document.getElementById('companion-modal-close');
  const saveBtn  = document.getElementById('save-preset-btn');

  if (avatar && modal) {
    avatar.addEventListener('click', () => {
      modal.style.display = 'block';
      loadPresetList();
    });
  }

  if (closeBtn) closeBtn.addEventListener('click', closeCompanionModal);
  if (overlay)  overlay.addEventListener('click', closeCompanionModal);
  if (saveBtn)  saveBtn.addEventListener('click', onSavePreset);

  // 이모지 입력 → 미리보기 텍스트 업데이트
  document.getElementById('preset-emoji')?.addEventListener('input', e => {
    const imgPreview = document.getElementById('preset-image-preview');
    if (imgPreview && !imgPreview.hidden) return; // 이미지가 있으면 이모지 무시
    const emojiText = document.getElementById('emoji-preview-text');
    if (emojiText) emojiText.textContent = e.target.value || '🦇';
  });

  // 이미지 파일 선택 → 미리보기 즉시 표시
  document.getElementById('preset-image-file')?.addEventListener('change', e => {
    const file = e.target.files?.[0];
    const imgPreview = document.getElementById('preset-image-preview');
    const emojiText = document.getElementById('emoji-preview-text');
    if (!file) {
      if (imgPreview) { imgPreview.src = ''; imgPreview.hidden = true; }
      if (emojiText) emojiText.style.display = '';
      return;
    }
    const reader = new FileReader();
    reader.onload = ev => {
      if (imgPreview) { imgPreview.src = ev.target.result; imgPreview.hidden = false; }
      if (emojiText) emojiText.style.display = 'none';
    };
    reader.readAsDataURL(file);
  });

  // JSON 파일 선택 → 각 트리거 textarea 자동 입력
  document.getElementById('preset-json-file')?.addEventListener('change', async e => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await readFileAsText(file);
      const map = extractDialogueMap(JSON.parse(text));
      DIALOGUE_TRIGGERS.forEach(trigger => {
        const el = document.getElementById(`dlg-${trigger}`);
        if (!el || !(trigger in map)) return;
        el.value = Array.isArray(map[trigger]) ? map[trigger].join('\n') : map[trigger];
      });
      showModalMessage('JSON을 불러왔어요. 내용을 확인해주세요.', 'success');
    } catch {
      showModalMessage('JSON 형식이 올바르지 않아요.', 'error');
    }
  });

  // 탭 전환: data-tab 속성으로 활성 탭 관리
  document.querySelectorAll('[data-tab-target]').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tabTarget;
      document.querySelectorAll('[data-tab]').forEach(panel => {
        panel.style.display = panel.dataset.tab === target ? 'block' : 'none';
      });
      document.querySelectorAll('[data-tab-target]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
}

document.addEventListener('DOMContentLoaded', initCompanionModal);
