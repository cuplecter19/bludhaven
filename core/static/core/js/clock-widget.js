const instances = new Map();

export function startClockWidget(layerId, el, options = {}) {
  stopClockWidget(layerId);
  const timezone = options.timezone || 'UTC';
  const format = options.format || { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };

  const timeEl = document.createElement('div');
  const dateEl = document.createElement('div');
  timeEl.className = 'clock-time';
  dateEl.className = 'clock-date';
  el.innerHTML = '';
  el.append(timeEl, dateEl);

  const dateFmt = new Intl.DateTimeFormat('ko-KR', { weekday: 'short', year: 'numeric', month: 'short', day: '2-digit', timeZone: timezone });
  const timeFmt = new Intl.DateTimeFormat('en-GB', { ...format, timeZone: timezone });

  const tick = () => {
    const now = new Date();
    timeEl.textContent = timeFmt.format(now);
    dateEl.textContent = dateFmt.format(now).toUpperCase();
  };

  tick();
  const timer = setInterval(tick, 1000);
  instances.set(layerId, timer);
}

export function stopClockWidget(layerId) {
  const timer = instances.get(layerId);
  if (timer) {
    clearInterval(timer);
    instances.delete(layerId);
  }
}
