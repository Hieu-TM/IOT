/* Panel điều khiển trạm — poll /api/runner/status mỗi giây, nối nút bấm.
 *
 * Không framework, không CDN: dashboard phải chạy được trên LAN offline
 * (cùng quyết định với "SVG server-rendered thay Chart.js" của Module 5).
 */
(function () {
  var panel = document.getElementById('control-panel');
  if (!panel) return;

  var POLL_MS = 1000;
  var FLASH_HOLD_MS = 4000;
  var mode = 'preview';
  var running = false;
  var pollInFlight = false;
  var lastFlashAt = 0;

  function $(id) { return document.getElementById(id); }

  // A FastAPI/pydantic 422 body has `detail` as an array of
  // {loc, msg, type} objects, not a string — the 400/409 HTTPExceptions in
  // control.py use a plain Vietnamese string. Normalize both to one message
  // so the operator never sees "[object Object]".
  function detailToMessage(detail, fallback) {
    if (typeof detail === 'string' && detail) return detail;
    if (Array.isArray(detail) && detail.length) {
      return detail.map(function (e) {
        var field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : null;
        return field ? (field + ': ' + e.msg) : e.msg;
      }).join('; ');
    }
    return fallback;
  }

  function post(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    }).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok) throw new Error(detailToMessage(data.detail, 'HTTP ' + r.status));
        return data;
      });
    });
  }

  function flash(message, isError) {
    lastFlashAt = Date.now();
    var box = $('cp-warnings');
    box.hidden = false;
    box.className = 'cp-warnings' + (isError ? ' error' : '');
    box.textContent = message;
  }

  function saveSettings(patch) {
    return post('/api/settings', patch).catch(function (e) {
      flash('Không lưu được cấu hình: ' + e.message, true);
    });
  }

  /* --- render ------------------------------------------------------- */

  function render(s) {
    running = s.running;
    $('runner-state').textContent = s.running
      ? (s.mode === 'measure' ? 'đang ĐO' : 'đang XEM')
      : 'đã dừng';
    $('runner-state').className = 'chip' + (s.running ? ' chip-live' : '');

    var c = s.counters || {};
    $('runner-counters').textContent =
      'chu kỳ ' + (c.cycles || 0) + ' · chụp ' + (c.captured || 0) +
      ' · ghi ' + (c.written || 0) + ' · hỏng ' + (c.failed || 0);

    $('btn-start').disabled = s.running;
    $('btn-stop').disabled = !s.running;
    $('cp-phase').textContent = 'pha bơm: ' + (s.phase || '—');

    var dev = s.device;
    $('cp-board-info').textContent = dev
      ? (dev.device_id || '?') + ' · ' + (dev.firmware || '?') +
        ' · RSSI ' + ((dev.wifi && dev.wifi.rssi) || '?') + ' dBm' +
        (dev.prefs_saved ? ' · đã lưu cấu hình' : ' · CHƯA lưu cấu hình')
      : 'chưa kết nối';

    // A recent flash() (e.g. "Đã lưu ... vào sổ audit.") gets a short grace
    // window before the status snapshot is allowed to overwrite/hide it —
    // otherwise a poll tick a moment later erases it before it's read. A
    // real fault from the snapshot (s.error) always takes over immediately;
    // only the transient success/info toast gets held.
    var holdingFlash = !s.error && (Date.now() - lastFlashAt < FLASH_HOLD_MS);
    if (!holdingFlash) {
      var msgs = (s.warnings || []).slice();
      if (s.error) msgs.unshift(s.error);
      var box = $('cp-warnings');
      if (msgs.length) {
        box.hidden = false;
        box.className = 'cp-warnings' + (s.error ? ' error' : '');
        box.textContent = msgs.join('  •  ');
      } else {
        box.hidden = true;
      }
    }

    var last = s.last;
    $('cp-live').hidden = !last;
    if (last) {
      $('cp-last-code').textContent = last.sample_code;
      $('cp-last-count').textContent = last.particle_count + ' hạt';
      $('cp-last-written').textContent = last.written
        ? 'đã ghi vào sổ audit'
        : 'KHÔNG ghi (chế độ Xem)';
      $('btn-keep').hidden = last.written || !s.has_preview;
      if (s.has_preview) {
        // cache-bust: khung đổi mỗi chu kỳ, cùng một URL
        $('cp-preview').src = '/api/runner/preview.jpg?t=' + encodeURIComponent(last.at);
      }
    }
  }

  function poll() {
    // Guard against overlap: a slow/unreachable board must not let requests
    // stack up faster than they resolve. The flag is always cleared in
    // `finally`, so an error (or a rejected .json()) can never wedge it shut.
    if (pollInFlight) return;
    pollInFlight = true;
    fetch('/api/runner/status')
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () { /* server vừa restart — lần poll sau sẽ bắt lại */ })
      .finally(function () { pollInFlight = false; });
  }

  /* --- mode toggle -------------------------------------------------- */

  function setMode(next) {
    mode = next;
    var isMeasure = next === 'measure';
    $('btn-mode-measure').classList.toggle('active', isMeasure);
    $('btn-mode-preview').classList.toggle('active', !isMeasure);
    $('btn-mode-measure').setAttribute('aria-checked', String(isMeasure));
    $('btn-mode-preview').setAttribute('aria-checked', String(!isMeasure));
    $('cp-mode-hint').innerHTML = isMeasure
      ? 'Đo: mỗi chu kỳ bơm ghi <strong>một mẫu vĩnh viễn</strong> vào sổ audit.'
      : 'Xem: suy luận liên tục, <strong>không ghi</strong> vào sổ audit.';
    saveSettings({ mode: next });
  }

  /* --- wiring ------------------------------------------------------- */

  $('btn-mode-preview').addEventListener('click', function () { setMode('preview'); });
  $('btn-mode-measure').addEventListener('click', function () { setMode('measure'); });

  $('btn-start').addEventListener('click', function () {
    saveSettings({
      station_host: $('cp-host').value.trim(),
      batch_lot: $('cp-lot').value.trim() || null
    }).then(function () {
      return post('/api/runner/start', { mode: mode });
    }).then(render).catch(function (e) {
      flash('Không bắt đầu được: ' + e.message, true);
    });
  });

  $('btn-stop').addEventListener('click', function () {
    post('/api/runner/stop').then(render).catch(function (e) {
      flash('Không dừng được: ' + e.message, true);
    });
  });

  $('btn-probe').addEventListener('click', function () {
    var host = $('cp-host').value.trim() || 'aqua-scope.local';
    $('cp-host').value = host;
    $('cp-board-info').textContent = 'đang dò ' + host + '...';
    fetch('/api/station/probe?host=' + encodeURIComponent(host))
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(detailToMessage(d.detail, 'HTTP ' + r.status));
          return d;
        });
      })
      .then(function (dev) {
        saveSettings({ station_host: host });
        $('cp-board-info').textContent =
          'tìm thấy ' + (dev.device_id || '?') + ' · ' + (dev.firmware || '?');
      })
      .catch(function (e) {
        $('cp-board-info').textContent = 'không thấy board: ' + e.message;
      });
  });

  function control(varName, val, label) {
    post('/api/station/control', { var: varName, val: val })
      .then(function () { flash(label + ': board đã nhận.', false); })
      .catch(function (e) { flash(label + ' hỏng: ' + e.message, true); });
  }

  $('btn-darkmode').addEventListener('click', function () {
    control('darkmode', '1', 'Canh sáng buồng tối');
  });
  $('btn-save').addEventListener('click', function () {
    control('save', '1', 'Lưu vào flash');
  });
  $('btn-pump-on').addEventListener('click', function () {
    control('pump_auto', '1', 'Bơm auto BẬT');
  });
  $('btn-pump-off').addEventListener('click', function () {
    control('pump_auto', '0', 'Bơm auto TẮT');
  });

  $('btn-keep').addEventListener('click', function () {
    post('/api/runner/keep')
      .then(function (d) { flash('Đã lưu ' + d.sample_code + ' vào sổ audit.', false); })
      .catch(function (e) { flash('Không lưu được: ' + e.message, true); });
  });

  /* --- boot --------------------------------------------------------- */

  fetch('/api/settings')
    .then(function (r) { return r.json(); })
    .then(function (s) {
      $('cp-host').value = s.station_host || '';
      $('cp-lot').value = s.batch_lot || '';
      setMode(s.mode || 'preview');
    })
    .catch(function () {});

  poll();
  setInterval(poll, POLL_MS);
})();
