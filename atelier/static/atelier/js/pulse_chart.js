/**
 * pulse_chart.js — Calendar grid and mood trend chart
 * Reads window.__PULSE_TREND__ or fetches from /atelier/api/pulse/trend/
 */
(function () {
  const calendarGrid = document.getElementById('calendar-grid');
  const calendarTitle = document.getElementById('calendar-title');
  const prevBtn = document.getElementById('prev-month');
  const nextBtn = document.getElementById('next-month');
  const trendChart = document.getElementById('trend-chart');

  if (!calendarGrid) return;

  const now = new Date();
  let currentYear = now.getFullYear();
  let currentMonth = now.getMonth() + 1; // 1-based

  async function fetchCalendar(year, month) {
    const resp = await fetch(`/atelier/api/pulse/calendar/?year=${year}&month=${month}`);
    return resp.json();
  }

  async function renderCalendar(year, month) {
    calendarTitle.textContent = `${year}년 ${month}월`;
    calendarGrid.innerHTML = '';

    const data = await fetchCalendar(year, month);
    const dayMap = {};
    (data.days || []).forEach(d => { dayMap[d.date] = d; });

    // Day headers
    ['일', '월', '화', '수', '목', '금', '토'].forEach(d => {
      const cell = document.createElement('div');
      cell.className = 'calendar-cell';
      cell.style.fontWeight = 'bold';
      cell.style.background = 'transparent';
      cell.textContent = d;
      calendarGrid.appendChild(cell);
    });

    const firstDay = new Date(year, month - 1, 1).getDay();
    const daysInMonth = new Date(year, month, 0).getDate();

    for (let i = 0; i < firstDay; i++) {
      const empty = document.createElement('div');
      empty.className = 'calendar-cell';
      empty.style.background = 'transparent';
      calendarGrid.appendChild(empty);
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const cell = document.createElement('div');
      cell.className = 'calendar-cell';
      cell.textContent = d;
      if (dayMap[dateStr]) {
        const dot = document.createElement('div');
        dot.className = `mood-dot ${dayMap[dateStr].level}`;
        cell.appendChild(dot);
      }
      calendarGrid.appendChild(cell);
    }
  }

  if (prevBtn) prevBtn.addEventListener('click', () => {
    currentMonth--;
    if (currentMonth < 1) { currentMonth = 12; currentYear--; }
    renderCalendar(currentYear, currentMonth);
  });

  if (nextBtn) nextBtn.addEventListener('click', () => {
    currentMonth++;
    if (currentMonth > 12) { currentMonth = 1; currentYear++; }
    renderCalendar(currentYear, currentMonth);
  });

  renderCalendar(currentYear, currentMonth);

  // Trend chart
  async function renderTrend() {
    if (!trendChart) return;
    let trendData = window.__PULSE_TREND__;
    if (!trendData) {
      const resp = await fetch('/atelier/api/pulse/trend/?days=30');
      const json = await resp.json();
      trendData = json.data || [];
    }
    if (!trendData.length) {
      trendChart.textContent = '최근 30일 데이터가 없어요.';
      return;
    }
    const max = 10;
    const width = trendChart.clientWidth || 400;
    const height = 100;
    const barW = Math.max(4, Math.floor((width - 20) / trendData.length) - 2);

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', height + 20);
    svg.setAttribute('viewBox', `0 0 ${width} ${height + 20}`);

    trendData.forEach((d, i) => {
      const x = 10 + i * (barW + 2);
      const barHeight = Math.round((d.mood_score / max) * height);
      const y = height - barHeight;
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', x);
      rect.setAttribute('y', y);
      rect.setAttribute('width', barW);
      rect.setAttribute('height', barHeight);
      rect.setAttribute('fill', d.mood_score > 6 ? '#4a7c59' : d.mood_score > 3 ? '#5a6a7a' : '#8b4a4a');
      rect.setAttribute('rx', 2);
      svg.appendChild(rect);
    });

    trendChart.innerHTML = '';
    trendChart.appendChild(svg);
  }

  renderTrend();
})();
