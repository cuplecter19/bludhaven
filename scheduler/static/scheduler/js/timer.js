import { startTimer, stopTimer } from './api.js';
import { showDialogue } from './companion.js';

// ── 상태 ──────────────────────────────────────────────────────────────────────

let currentSessionId = null;
let sessionType = null;
let intervalId = null;
let elapsed = 0;
let cheer25Fired = false;

window.timerRunning = false;

// ── DOM helpers ───────────────────────────────────────────────────────────────

function formatTime(secs) {
  const m = String(Math.floor(secs / 60)).padStart(2, '0');
  const s = String(secs % 60).padStart(2, '0');
  return `${m}:${s}`;
}

function updateDisplay() {
  const el = document.getElementById('timer-display');
  if (el) el.textContent = formatTime(elapsed);
}

function setButtonState(running) {
  const startBtn = document.getElementById('timer-start-btn');
  const breakBtn = document.getElementById('timer-break-btn');
  const stopBtn  = document.getElementById('timer-stop-btn');

  if (startBtn) startBtn.disabled = running;
  if (breakBtn) breakBtn.disabled = running;
  if (stopBtn)  stopBtn.disabled  = !running;
}

// ── 내부 ──────────────────────────────────────────────────────────────────────

function clearTimer() {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
  }
  currentSessionId = null;
  sessionType = null;
  elapsed = 0;
  cheer25Fired = false;
  window.timerRunning = false;
  updateDisplay();
  setButtonState(false);
}

function startInterval() {
  elapsed = 0;
  updateDisplay();
  intervalId = setInterval(() => {
    elapsed += 1;
    updateDisplay();

    if (sessionType === 'focus' && elapsed === 25 * 60 && !cheer25Fired) {
      cheer25Fired = true;
      showDialogue('cheer_focus_long');
    }
  }, 1000);
}

// ── 공개 API ──────────────────────────────────────────────────────────────────

export async function startFocus(taskId) {
  let data;
  try {
    data = await startTimer(taskId, 'focus');
  } catch {
    return;
  }
  currentSessionId = data.id;
  sessionType = 'focus';
  window.timerRunning = true;
  setButtonState(true);
  startInterval();
}

export async function startBreak(taskId) {
  let data;
  try {
    data = await startTimer(taskId, 'break');
  } catch {
    return;
  }
  currentSessionId = data.id;
  sessionType = 'break';
  window.timerRunning = true;
  setButtonState(true);
  startInterval();
}

export async function stop() {
  if (!currentSessionId) return;
  const wasBreak = sessionType === 'break';
  try {
    await stopTimer(currentSessionId);
  } catch {
    return;
  }
  clearTimer();
  if (wasBreak) showDialogue('return_from_break');
}

// ── 버튼 바인딩 ───────────────────────────────────────────────────────────────

// taskId는 페이지에서 주입 (window.currentTaskId 또는 data 속성)
function resolveTaskId() {
  return window.currentTaskId ?? null;
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('timer-start-btn')?.addEventListener('click', () => {
    const id = resolveTaskId();
    if (id) startFocus(id);
  });

  document.getElementById('timer-break-btn')?.addEventListener('click', () => {
    const id = resolveTaskId();
    if (id) startBreak(id);
  });

  document.getElementById('timer-stop-btn')?.addEventListener('click', stop);

  updateDisplay();
  setButtonState(false);
});
