/**
 * pulse_chart.js — Calendar grid, mood trend chart, PHQ-9 trend chart
 */
(function () {
  const calendarGrid = document.getElementById('calendar-grid');
  const calendarTitle = document.getElementById('calendar-title');
  const prevBtn = document.getElementById('prev-month');
  const nextBtn = document.getElementById('next-month');
  const trendChart = document.getElementById('trend-chart');
  const phq9Chart = document.getElementById('phq9-trend-chart');

  if (!calendarGrid) return;

  const now = new Date();
  let currentYear = now.getFullYear();
  let currentMonth = now.getMonth() + 1;

  async function fetchCalendar(year, month) {
    const resp = await fetch('/atelier/api/pulse/calendar/?year=' + year + '&month=' + month);
    return resp.json();
  }

  async function renderCalendar(year, month) {
    calendarTitle.textContent = year + '년 ' + month + '월';
    calendarGrid.innerHTML = '';

    const data = await fetchCalendar(year, month);
    const dayMap = {};
    (data.days || []).forEach(function(d) { dayMap[d.date] = d; });

    ['일', '월', '화', '수', '목', '금', '토'].forEach(function(d) {
      var cell = document.createElement('div');
      cell.className = 'calendar-cell';
      cell.style.fontWeight = 'bold';
      cell.style.background = 'transparent';
      cell.textContent = d;
      calendarGrid.appendChild(cell);
    });

    var firstDay = new Date(year, month - 1, 1).getDay();
    var daysInMonth = new Date(year, month, 0).getDate();

    for (var i = 0; i < firstDay; i++) {
      var empty = document.createElement('div');
      empty.className = 'calendar-cell';
      empty.style.background = 'transparent';
      calendarGrid.appendChild(empty);
    }

    for (var d = 1; d <= daysInMonth; d++) {
      var dateStr = year + '-' + String(month).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      var cell = document.createElement('div');
      cell.className = 'calendar-cell';
      cell.textContent = d;
    if (dayMap[dateStr]) {
        var dot = document.createElement('div');
        dot.className = 'mood-dot ' + dayMap[dateStr].level;
        var rawTags = dayMap[dateStr].emotion_tags || '';
        var tags = rawTags.split(';').map(function(t) { return t.trim(); }).filter(Boolean);
        if (tags.length) {
          dot.setAttribute('data-tooltip', tags.map(function(t) { return '#' + t; }).join(' '));
        }
        cell.appendChild(dot);
      }
      calendarGrid.appendChild(cell);
    }
  }

  if (prevBtn) prevBtn.addEventListener('click', function() {
    currentMonth--;
    if (currentMonth < 1) { currentMonth = 12; currentYear--; }
    renderCalendar(currentYear, currentMonth);
  });

  if (nextBtn) nextBtn.addEventListener('click', function() {
    currentMonth++;
    if (currentMonth > 12) { currentMonth = 1; currentYear++; }
    renderCalendar(currentYear, currentMonth);
  });

  renderCalendar(currentYear, currentMonth);

  // ---------------------------------------------------------------------------
  // Generic SVG bar chart helper
  // ---------------------------------------------------------------------------

  function buildBarChart(container, dataPoints, getVal, maxVal, colorFn, emptyMsg, getLabel) {
    if (!container) return;
    if (!dataPoints || !dataPoints.length) {
      container.textContent = emptyMsg;
      return;
    }
    var labelArea = getLabel ? 35 : 20;
    var width = container.clientWidth || 400;
    var height = 100;
    var barW = Math.max(4, Math.floor((width - 20) / dataPoints.length) - 2);

    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', height + labelArea);
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + (height + labelArea));

    dataPoints.forEach(function(d, i) {
      var x = 10 + i * (barW + 2);
      var val = getVal(d);
      var barHeight = Math.max(2, Math.round((val / maxVal) * height));
      var y = height - barHeight;
      var rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', x);
      rect.setAttribute('y', y);
      rect.setAttribute('width', barW);
      rect.setAttribute('height', barHeight);
      rect.setAttribute('fill', colorFn(val));
      rect.setAttribute('rx', 2);

      // Tooltip via title element
      var title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
      title.textContent = `${d.logged_at}: ${val}`;
      rect.appendChild(title);
      svg.appendChild(rect);

      // Date label on X-axis
      if (getLabel) {
        var labelText = getLabel(d);
        var tx = x + barW / 2;
        var ty = height + 8;
        var text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', tx);
        text.setAttribute('y', ty);
        text.setAttribute('font-size', '9');
        text.setAttribute('fill', '#888');
        text.setAttribute('text-anchor', 'end');
        text.setAttribute('transform', 'rotate(-45,' + tx + ',' + ty + ')');
        text.textContent = labelText;
        svg.appendChild(text);
      }
    });

    container.innerHTML = '';
    container.appendChild(svg);
  }

  // ---------------------------------------------------------------------------
  // Mood trend chart (max 10)
  // ---------------------------------------------------------------------------

  async function renderTrend() {
    if (!trendChart) return;
    var trendData = window.__PULSE_TREND__;
    if (!trendData) {
      try {
        var resp = await fetch('/atelier/api/pulse/trend/?days=30');
        var json = await resp.json();
        trendData = json.data || [];
      } catch (e) {
        trendData = [];
      }
    }
    buildBarChart(
      trendChart,
      trendData,
      function(d) { return d.mood_score; },
      10,
      function(v) { return v > 6 ? '#4a7c59' : v > 3 ? '#5a6a7a' : '#8b4a4a'; },
      '최근 30일 데이터가 없어요.',
      function(d) {
        var dt = new Date(d.logged_at);
        return (dt.getMonth() + 1) + '/' + dt.getDate();
      }
    );
  }

  // ---------------------------------------------------------------------------
  // PHQ-9 trend chart (max 27)
  // ---------------------------------------------------------------------------

  // PHQ-9 severity colour: 0-4 minimal (#4a7c59), 5-9 mild (#a07010),
  //   10-14 moderate (#5a6a7a), 15-19 mod-severe (#8b4a4a), 20-27 severe (#7a1a1a)
  function phq9Color(v) {
    if (v <= 4) return '#4a7c59';
    if (v <= 9) return '#a07010';
    if (v <= 14) return '#5a6a7a';
    if (v <= 19) return '#8b4a4a';
    return '#7a1a1a';
  }

  async function renderPhq9Trend() {
    if (!phq9Chart) return;
    try {
      var resp = await fetch('/atelier/api/pulse/phq9-trend/');
      var json = await resp.json();
      var data = json.data || [];
      buildBarChart(
        phq9Chart,
        data,
        function(d) { return d.total_score; },
        27,
        phq9Color,
        'PHQ-9 기록이 없어요.',
        function(d) {
          var parts = d.logged_at.split('-');
          return parseInt(parts[1]) + '/' + parseInt(parts[2]);
        }
      );
    } catch (e) {
      if (phq9Chart) phq9Chart.textContent = 'PHQ-9 데이터를 불러오지 못했어요.';
    }
  }

  renderTrend();
  renderPhq9Trend();
})();
