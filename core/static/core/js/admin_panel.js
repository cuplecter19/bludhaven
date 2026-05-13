/* admin_panel.js — 관리 패널 로직 */

(function () {
    'use strict';

    // ── CSRF 토큰 헬퍼 ───────────────────────────────────────────
    function getCookie(name) {
        var v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return v ? v.pop() : '';
    }

    function apiCall(url, method, data, isFormData) {
        var opts = {
            method: method,
            headers: { 'X-CSRFToken': getCookie('csrftoken') },
            credentials: 'same-origin',
        };
        if (data) {
            if (isFormData) {
                opts.body = data;
            } else {
                opts.headers['Content-Type'] = 'application/json';
                opts.body = JSON.stringify(data);
            }
        }
        return fetch(url, opts).then(function (r) { return r.json(); });
    }

    function showError(msg) {
        var el = document.getElementById('admin-panel-error');
        if (el) { el.textContent = msg; el.style.display = 'block'; }
        else { alert('오류: ' + msg); }
    }

    function clearError() {
        var el = document.getElementById('admin-panel-error');
        if (el) { el.style.display = 'none'; }
    }

    // ── 패널 드래그 ──────────────────────────────────────────────
    function makeDraggable(el, handleEl) {
        var startX, startY, startLeft, startTop;
        handleEl.addEventListener('pointerdown', function (e) {
            e.preventDefault();
            startX = e.clientX;
            startY = e.clientY;
            var rect = el.getBoundingClientRect();
            startLeft = rect.left;
            startTop  = rect.top;
            document.addEventListener('pointermove', onMove);
            document.addEventListener('pointerup', onUp, { once: true });
        });
        function onMove(e) {
            el.style.left = (startLeft + e.clientX - startX) + 'px';
            el.style.top  = (startTop  + e.clientY - startY) + 'px';
            el.style.right = 'auto';
            el.style.bottom = 'auto';
        }
        function onUp() {
            document.removeEventListener('pointermove', onMove);
        }
    }

    // ── 스티커 드래그 이동 ───────────────────────────────────────
    function enableStickerDrag(stickerEl) {
        var pk = stickerEl.dataset.pk;
        var handle = stickerEl.querySelector('.sticker-handle');
        if (!handle) return;
        var startX, startY, startLeft, startTop;
        handle.addEventListener('pointerdown', function (e) {
            e.preventDefault();
            handle.setPointerCapture(e.pointerId);
            startX = e.clientX;
            startY = e.clientY;
            var rect = stickerEl.getBoundingClientRect();
            startLeft = rect.left;
            startTop  = rect.top;
            handle.addEventListener('pointermove', onMove);
            handle.addEventListener('pointerup', onUp, { once: true });
        });
        function onMove(e) {
            var newLeft = startLeft + e.clientX - startX;
            var newTop  = startTop  + e.clientY - startY;
            stickerEl.style.left = newLeft + 'px';
            stickerEl.style.top  = newTop  + 'px';
        }
        function onUp(e) {
            handle.removeEventListener('pointermove', onMove);
            var newLeft = (startLeft + e.clientX - startX) + 'px';
            var newTop  = (startTop  + e.clientY - startY) + 'px';
            clearError();
            apiCall('/core/api/sticker/' + pk + '/move/', 'PATCH', { pos_left: newLeft, pos_top: newTop })
                .then(function (res) {
                    if (!res.ok) showError(res.error || '스티커 이동 저장 실패');
                })
                .catch(function () { showError('스티커 이동 저장 중 오류 발생'); });
        }
    }

    // ── 텍스트블록 실시간 미리보기 ───────────────────────────────
    function bindTextBlockPreview(input, pk, field) {
        input.addEventListener('input', function () {
            var tbEl = document.getElementById('textblock-' + pk);
            if (!tbEl) return;
            if (field === 'pos_left') tbEl.style.left = input.value;
            else if (field === 'pos_top') tbEl.style.top = input.value;
            else if (field === 'font_size') tbEl.style.fontSize = input.value;
            else if (field === 'color') tbEl.style.color = input.value;
            else if (field === 'z_index') tbEl.style.zIndex = input.value;
        });
    }

    function saveTextBlock(pk, data) {
        clearError();
        apiCall('/core/api/textblock/' + pk + '/update/', 'PATCH', data)
            .then(function (res) {
                if (!res.ok) showError(res.error || '텍스트블록 저장 실패');
            })
            .catch(function () { showError('텍스트블록 저장 중 오류 발생'); });
    }

    // ── 패럴랙스 설정 슬라이더 ───────────────────────────────────
    function bindParallaxSliders() {
        var speedInput   = document.getElementById('parallax-speed-input');
        var overlayInput = document.getElementById('parallax-overlay-input');
        var saveBtn      = document.getElementById('parallax-save-btn');
        if (!saveBtn) return;
        if (speedInput) {
            speedInput.addEventListener('input', function () {
                document.documentElement.style.setProperty('--parallax-speed', speedInput.value);
            });
        }
        if (overlayInput) {
            overlayInput.addEventListener('input', function () {
                document.documentElement.style.setProperty('--overlay-opacity', overlayInput.value);
            });
        }
        saveBtn.addEventListener('click', function () {
            var data = {};
            if (speedInput)   data.speed           = parseFloat(speedInput.value);
            if (overlayInput) data.overlay_opacity  = parseFloat(overlayInput.value);
            clearError();
            apiCall('/core/api/parallax/update/', 'POST', data)
                .then(function (res) {
                    if (!res.ok) showError(res.error || '패럴랙스 저장 실패');
                })
                .catch(function () { showError('패럴랙스 저장 중 오류 발생'); });
        });
    }

    // ── 시계 설정 ────────────────────────────────────────────────
    function bindClockConfig() {
        var saveBtn = document.getElementById('clock-save-btn');
        if (!saveBtn) return;
        saveBtn.addEventListener('click', function () {
            var data = {};
            ['pos_left', 'pos_top', 'font_size', 'color', 'z_index'].forEach(function (f) {
                var el = document.getElementById('clock-' + f.replace('_', '-') + '-input');
                if (el) data[f] = el.value;
            });
            var activeEl = document.getElementById('clock-is-active-input');
            if (activeEl) data.is_active = activeEl.checked;
            clearError();
            apiCall('/core/api/clock/update/', 'POST', data)
                .then(function (res) {
                    if (!res.ok) showError(res.error || '시계 설정 저장 실패');
                    else {
                        var cw = document.getElementById('clock-widget');
                        if (cw && data.pos_left) cw.style.left     = data.pos_left;
                        if (cw && data.pos_top)  cw.style.top      = data.pos_top;
                        if (cw && data.font_size) cw.style.fontSize = data.font_size;
                        if (cw && data.color)     cw.style.color    = data.color;
                        if (cw && data.z_index)   cw.style.zIndex   = data.z_index;
                    }
                })
                .catch(function () { showError('시계 설정 저장 중 오류 발생'); });
        });
    }

    // ── 스티커 추가 ──────────────────────────────────────────────
    function bindStickerAdd() {
        var form = document.getElementById('sticker-add-form');
        if (!form) return;
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var fd = new FormData(form);
            clearError();
            apiCall('/core/api/sticker/add/', 'POST', fd, true)
                .then(function (res) {
                    if (!res.ok) { showError(res.error || '스티커 추가 실패'); return; }
                    var d = res.data;
                    var layer = document.querySelector('.layer-stickers');
                    if (!layer) return;
                    var div = document.createElement('div');
                    div.className = 'sticker-item sticker-item--editable';
                    div.id = 'sticker-' + d.pk;
                    div.dataset.pk = d.pk;
                    div.style.cssText = 'left:' + d.pos_left + ';top:' + d.pos_top +
                        ';width:' + d.width + ';height:' + d.height +
                        ';transform:rotate(' + d.rotate + 'deg);z-index:' + d.z_index + ';';
                    div.innerHTML = '<img src="' + d.image + '" alt="' + d.title + '" draggable="false">' +
                        '<div class="sticker-handle" title="드래그하여 이동">⠿</div>';
                    layer.appendChild(div);
                    enableStickerDrag(div);
                    form.reset();
                })
                .catch(function () { showError('스티커 추가 중 오류 발생'); });
        });
    }

    // ── 스티커 삭제 ──────────────────────────────────────────────
    function bindStickerDelete() {
        document.addEventListener('click', function (e) {
            if (!e.target.matches('.sticker-delete-btn')) return;
            var pk = e.target.dataset.pk;
            if (!pk || !confirm('스티커를 삭제하시겠습니까?')) return;
            clearError();
            apiCall('/core/api/sticker/' + pk + '/delete/', 'DELETE')
                .then(function (res) {
                    if (!res.ok) { showError(res.error || '스티커 삭제 실패'); return; }
                    var el = document.getElementById('sticker-' + pk);
                    if (el) el.remove();
                })
                .catch(function () { showError('스티커 삭제 중 오류 발생'); });
        });
    }

    // ── 초기화 ───────────────────────────────────────────────────
    function init() {
        // 패널 드래그
        var panel  = document.getElementById('admin-panel');
        var handle = document.getElementById('admin-panel-handle');
        if (panel && handle) makeDraggable(panel, handle);

        // 기존 스티커 드래그
        document.querySelectorAll('.sticker-item--editable').forEach(enableStickerDrag);

        // 텍스트블록 미리보기 바인딩
        document.querySelectorAll('[data-tb-pk]').forEach(function (row) {
            var pk = row.dataset.tbPk;
            ['pos_left', 'pos_top', 'font_size', 'color', 'z_index'].forEach(function (f) {
                var inp = row.querySelector('[data-field="' + f + '"]');
                if (inp) bindTextBlockPreview(inp, pk, f);
            });
            var saveBtn = row.querySelector('.tb-save-btn');
            if (saveBtn) {
                saveBtn.addEventListener('click', function () {
                    var data = {};
                    ['content', 'pos_left', 'pos_top', 'font_size', 'color', 'z_index'].forEach(function (f) {
                        var inp = row.querySelector('[data-field="' + f + '"]');
                        if (inp) data[f] = inp.value;
                    });
                    saveTextBlock(pk, data);
                });
            }
        });

        bindParallaxSliders();
        bindClockConfig();
        bindStickerAdd();
        bindStickerDelete();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
