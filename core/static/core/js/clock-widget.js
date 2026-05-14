const instances = new Map();

export function startClockWidget(layerId, el, options = {}) {
  stopClockWidget(layerId);
  const timezone = options.timezone || 'UTC';
  const format = options.format || { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
  const textColor = options.text_color || options.color;

  const timeEl = document.createElement('div');
  const dateEl = document.createElement('div');
  timeEl.className = 'clock-time';
  dateEl.className = 'clock-date';
  el.innerHTML = '';
  el.append(timeEl, dateEl);

  if (options.font_family) el.style.fontFamily = options.font_family;
  if (options.font_weight) el.style.fontWeight = String(options.font_weight);
  if (textColor) el.style.color = textColor;
  if (options.font_style) el.style.fontStyle = options.font_style;
  if (options.text_decoration) el.style.textDecoration = options.text_decoration;
  if (options.font_size && options.size_mode !== 'box') el.style.fontSize = options.font_size;
  if (options.letter_spacing) el.style.letterSpacing = options.letter_spacing;
  if (options.line_height) el.style.lineHeight = String(options.line_height);
  if (options.time_font_size) timeEl.style.fontSize = options.time_font_size;
  if (options.date_font_size) dateEl.style.fontSize = options.date_font_size;
  if (options.border_width) {
    el.style.border = `${options.border_width}px ${options.border_style || 'solid'} ${options.border_color || '#000000'}`;
  }

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
