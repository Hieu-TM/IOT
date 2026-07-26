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
  var currentDevice = null;

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

  // Resolves `true` on success, `false` on failure — never rejects, so
  // fire-and-forget callers (setMode, btn-probe) that don't chain off the
  // return value keep working exactly as before: the failure still flashes
  // here and nothing else changes for them. A caller that DOES need to know
  // whether the save actually landed (btn-start, below) checks the boolean
  // instead of relying on the promise settling — this used to always resolve
  // (even on failure) with no way for a caller to tell, so btn-start's
  // `.then(...)` chain ran unconditionally and could start a measurement run
  // under stale settings.
  function saveSettings(patch) {
    return post('/api/settings', patch).then(function () {
      return true;
    }).catch(function (e) {
      flash('Không lưu được cấu hình: ' + e.message, true);
      return false;
    });
  }

  function setCommandActive(buttonId, active) {
    var button = $(buttonId);
    button.classList.toggle('cp-command-active', !!active);
    button.setAttribute('aria-pressed', String(!!active));
  }

  function setCommandBusy(buttonId, busy) {
    var button = $(buttonId);
    button.classList.toggle('cp-command-busy', !!busy);
    button.disabled = !!busy;
  }

  function markFlashSaved(saved) {
    setCommandActive('btn-save', saved === true);
    if (currentDevice) currentDevice.prefs_saved = saved;
  }

  /* --- render ------------------------------------------------------- */

  function render(s) {
    running = s.running;
    if (s.device) currentDevice = s.device;
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

    var dev = s.device || currentDevice;
    if (dev) {
      var savedLabel = dev.prefs_saved === true
        ? ' · đã lưu cấu hình'
        : (dev.prefs_saved === false ? ' · CHƯA lưu cấu hình' : '');
      $('cp-board-info').textContent =
        (dev.device_id || '?') + ' · ' + (dev.firmware || '?') +
        ' · RSSI ' + ((dev.wifi && dev.wifi.rssi) || '?') + ' dBm' +
        savedLabel;
    } else {
      $('cp-board-info').textContent = 'chưa kết nối';
    }
    markFlashSaved(dev && dev.prefs_saved === true);
    var pump = dev && dev.pump;
    setCommandActive('btn-pump-on', pump && pump.auto === true);
    setCommandActive('btn-pump-off', pump && pump.auto === false);
    var cam = dev && dev.camera;
    setCommandActive('btn-darkmode', cam && !cam.aec && !cam.agc);

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
      // In Đo mode has_preview is always false (measure writes straight to
      // the audit trail and never holds a RAM frame — see runner.py's
      // `_capture_and_process`), so #cp-preview's src would stay "" while
      // #cp-live is unhidden above. An empty src on an <img> re-requests the
      // current page URL in several browsers and renders as a broken-image
      // box — hide the element itself instead of leaving it pointed at
      // nothing.
      $('cp-preview').hidden = !s.has_preview;
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
    }).then(function (saved) {
      // saveSettings() already flashed the "Không lưu được cấu hình: ..."
      // message on failure — short-circuit here instead of piling
      // "Không bắt đầu được" on top of it, and instead of starting the run
      // under whatever station_host/batch_lot were last saved to disk.
      if (!saved) return;
      return post('/api/runner/start', { mode: mode }).then(render);
    }).catch(function (e) {
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
        currentDevice = dev;
        markFlashSaved(dev.prefs_saved === true);
        saveSettings({ station_host: host });
        $('cp-board-info').textContent =
          'tìm thấy ' + (dev.device_id || '?') + ' · ' + (dev.firmware || '?');
      })
      .catch(function (e) {
        $('cp-board-info').textContent = 'không thấy board: ' + e.message;
      });
  });

  function control(varName, val, label, buttonId, activeAfter) {
    if (buttonId) setCommandBusy(buttonId, true);
    post('/api/station/control', { var: varName, val: val })
      .then(function () {
        if (buttonId) setCommandActive(buttonId, activeAfter);
        flash(label + ': board đã nhận.', false);
      })
      .catch(function (e) { flash(label + ' hỏng: ' + e.message, true); })
      .finally(function () {
        if (buttonId) setCommandBusy(buttonId, false);
      });
  }

  $('btn-darkmode').addEventListener('click', function () {
    control('darkmode', '1', 'Canh sáng buồng tối', 'btn-darkmode', true);
  });
  $('btn-save').addEventListener('click', function () {
    // Do NOT short-circuit on `currentDevice.prefs_saved === true` here.
    // prefs_saved is a sticky NVS flag meaning "something has been saved to
    // flash at some point", not "the current settings are saved" — it stays
    // true forever after the first save until `?var=reset`. Gating the POST
    // on it made every save after the first a silent no-op: the operator
    // re-tunes exposure, presses Save, sees no error, and the new values
    // never reach flash. Always POST; only the indicator reflects prefs_saved.
    setCommandBusy('btn-save', true);
    post('/api/station/control', { var: 'save', val: '1' })
      .then(function () {
        markFlashSaved(true);
        flash('Lưu vào flash: board đã nhận.', false);
      })
      .catch(function (e) { flash('Lưu vào flash hỏng: ' + e.message, true); })
      .finally(function () { setCommandBusy('btn-save', false); });
  });
  $('btn-pump-on').addEventListener('click', function () {
    control('pump_auto', '1', 'Bơm auto BẬT', 'btn-pump-on', true);
    setCommandActive('btn-pump-off', false);
  });
  $('btn-pump-off').addEventListener('click', function () {
    control('pump_auto', '0', 'Bơm auto TẮT', 'btn-pump-off', true);
    setCommandActive('btn-pump-on', false);
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
