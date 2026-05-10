import { getTodayPlan, createPlan, completeTask, skipTask } from './api.js';
import { showDialogue, initTimeBasedTriggers, initIdleTrigger } from './companion.js';
import { startFocus } from './timer.js';

// ── 에러 배너 ─────────────────────────────────────────────────────────────────

function showError(msg) {
  const banner = document.getElementById('error-banner');
  if (!banner) return;
  banner.textContent = msg;
  banner.style.display = 'block';
}

// ── 태스크 렌더링 ─────────────────────────────────────────────────────────────

function renderTask(task) {
  const isPending = task.status === 'pending';

  const li = document.createElement('li');
  li.id = `task-${task.id}`;
  li.className = `task-item status-${task.status}${task.status === 'done' ? ' done' : ''}${task.status === 'skipped' ? ' skipped' : ''}`;

  // 왼쪽: 완료 버튼(원형) + 시간
  const left = document.createElement('div');
  left.className = 'task-left';

  const checkBtn = document.createElement('button');
  checkBtn.type = 'button';
  checkBtn.className = 'task-check';
  checkBtn.disabled = !isPending;
  checkBtn.title = '완료';
  checkBtn.innerHTML = task.status === 'done' ? '<i class="fa-solid fa-check"></i>' : '';
  checkBtn.addEventListener('click', () => onComplete(task.id, task.title));
  left.append(checkBtn);

  if (task.planned_start) {
    const time = document.createElement('span');
    time.className = 'task-time';
    time.textContent = task.planned_start.slice(0, 5);
    left.append(time);
  }

  // 중앙: 제목 + 메타
  const body = document.createElement('div');
  body.className = 'task-body';

  const title = document.createElement('span');
  title.className = 'task-title';
  title.textContent = task.title;
  body.append(title);

  if (task.planned_duration_min || task.point_reward) {
    const meta = document.createElement('div');
    meta.className = 'task-meta';
    if (task.planned_duration_min) {
      const dur = document.createElement('span');
      dur.className = 'task-duration';
      dur.textContent = `${task.planned_duration_min}분`;
      meta.append(dur);
    }
    if (task.point_reward) {
      const pts = document.createElement('span');
      pts.className = 'point-badge';
      pts.textContent = `+${task.point_reward}`;
      meta.append(pts);
    }
    body.append(meta);
  }

  // 오른쪽: 타이머 + 스킵
  const actions = document.createElement('div');
  actions.className = 'task-actions';

  const timerBtn = document.createElement('button');
  timerBtn.type = 'button';
  timerBtn.className = 'task-btn-timer';
  timerBtn.textContent = '▶ 집중';
  timerBtn.disabled = !isPending;
  timerBtn.addEventListener('click', () => {
    window.currentTaskId = task.id;
    window.currentTaskName = task.title;
    startFocus(task.id);
    const card = document.getElementById('timer-card');
    if (card) {
      card.hidden = false;
      const nameEl = card.querySelector('.timer-task-name');
      if (nameEl) nameEl.textContent = task.title;
    }
  });

  const skipBtn = document.createElement('button');
  skipBtn.type = 'button';
  skipBtn.className = 'task-btn-skip';
  skipBtn.textContent = '건너뛰기';
  skipBtn.disabled = !isPending;
  skipBtn.addEventListener('click', () => onSkip(task.id));

  actions.append(timerBtn, skipBtn);
  li.append(left, body, actions);
  return li;
}

function getTaskList() {
  return document.getElementById('task-list');
}

// ── 이벤트 핸들러 ─────────────────────────────────────────────────────────────

export async function onComplete(taskId, taskName) {
  let data;
  try {
    data = await completeTask(taskId);
  } catch (err) {
    showError(err?.data?.detail ?? '완료 처리 중 오류가 발생했습니다.');
    return;
  }

  const li = document.getElementById(`task-${taskId}`);
  if (li) {
    li.classList.add('done');
    li.querySelectorAll('button').forEach(b => { b.disabled = true; });
  }

  const { extra_trigger, points_earned: points, done_count, total } = data;

  if (extra_trigger) {
    await showDialogue(extra_trigger, {
      points: String(points),
      done_count: String(done_count),
      total: String(total),
      remaining: String(total - done_count),
    });
  }

  showDialogue('task_done', {
    task_name: taskName,
    points: String(points),
    done_count: String(done_count),
  });
}

export async function onSkip(taskId) {
  try {
    await skipTask(taskId);
  } catch (err) {
    showError(err?.data?.detail ?? '건너뛰기 처리 중 오류가 발생했습니다.');
    return;
  }

  const li = document.getElementById(`task-${taskId}`);
  if (li) {
    li.classList.add('skipped');
    li.querySelectorAll('button').forEach(b => { b.disabled = true; });
  }

  showDialogue('task_skip');
}

// ── 초기화 ────────────────────────────────────────────────────────────────────

export async function init() {
  let plan;
  try {
    plan = await getTodayPlan();
  } catch (err) {
    if (err?.status === 404) {
      try {
        plan = await createPlan();
      } catch (createErr) {
        showError('오늘 계획을 만들 수 없습니다.');
        return;
      }
    } else {
      showError('계획을 불러오는 중 오류가 발생했습니다.');
      return;
    }
  }

  const list = getTaskList();
  if (list) {
    list.innerHTML = '';
    const tasks = (plan.tasks ?? []).slice().sort((a, b) => a.display_order - b.display_order);
    tasks.forEach(task => list.append(renderTask(task)));
  }

  window.currentPlanId = plan.id;
  document.dispatchEvent(new CustomEvent('planLoaded', { detail: { planId: plan.id } }));

  // 진행률 바 갱신
  function updateProgress() {
    const tasks = plan.tasks ?? [];
    const total = tasks.length;
    const done = tasks.filter(t => t.status === 'done').length;
    const fill = document.getElementById('progress-fill');
    const count = document.getElementById('today-count');
    if (fill) fill.style.width = `${total > 0 ? Math.round(done / total * 100) : 0}%`;
    if (count) count.textContent = `${done} / ${total} 완료`;
  }
  updateProgress();

  initTimeBasedTriggers();
  initIdleTrigger();
}

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('task-list')) init();
});
