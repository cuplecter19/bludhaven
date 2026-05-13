/* index.js — 메인 페이지 JS (패럴랙스) */

(function () {
    'use strict';

    // ── 패럴랙스 배경 ────────────────────────────────────────────
    var parallaxBg = document.querySelector('.layer-parallax-bg');
    var speed = parseFloat(parallaxBg ? (parallaxBg.dataset.parallaxSpeed || '0.4') : '0.4');

    function onScroll() {
        if (!parallaxBg) return;
        requestAnimationFrame(function () {
            parallaxBg.style.transform = 'translateY(' + (window.scrollY * speed) + 'px)';
        });
    }

    if (parallaxBg) {
        window.addEventListener('scroll', onScroll, { passive: true });
    }

    // ── 시계 위젯 ────────────────────────────────────────────────
    var DAYS   = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
    var MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                  'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

    function pad(n) { return String(n).padStart(2, '0'); }

    function tick() {
        var clockTime = document.getElementById('clock-time');
        var clockDate = document.getElementById('clock-date');
        if (!clockTime || !clockDate) return;
        var now  = new Date();
        var h    = pad(now.getHours());
        var m    = pad(now.getMinutes());
        var s    = pad(now.getSeconds());
        var day  = DAYS[now.getDay()];
        var date = pad(now.getDate());
        var mon  = MONTHS[now.getMonth()];
        var yr   = now.getFullYear();
        clockTime.textContent = h + ':' + m + ':' + s;
        clockDate.textContent = day + ' ' + date + ' ' + mon + ' ' + yr;
    }

    tick();
    setInterval(tick, 1000);
}());
