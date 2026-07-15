// Stream demo — pure-frontend backlit-flow simulation (no backend, no DB).
// Ported from the design reference: falling dark blobs on a soft gray-green
// field, optional detection bboxes, live HUD. Uses the same 14 px/mm scale and
// the --p-* label palette so it reads as the same "system" as the still images.
(function () {
  var canvas = document.getElementById('stream-canvas');
  if (!canvas) return;

  var PXMM = 14.0;
  var LABELS = ['plastic', 'bubble', 'organic', 'fiber', 'unknown'];
  var VI = { plastic: 'Nhựa', bubble: 'Bọt khí', organic: 'Hữu cơ', fiber: 'Sợi', unknown: 'Không xác định' };

  var PLAY = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M5 3l14 9-14 9V3z"/></svg>';
  var PAUSE = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14"/><rect x="14" y="5" width="4" height="14"/></svg>';

  var els = {
    count: document.getElementById('hud-count'),
    fps: document.getElementById('hud-fps'),
    dist: document.getElementById('hud-dist'),
    pause: document.getElementById('pause-overlay'),
    toggle: document.getElementById('stream-toggle'),
    icon: document.getElementById('stream-icon'),
    label: document.getElementById('stream-label'),
    det: document.getElementById('det-toggle'),
    detSwitch: document.getElementById('det-switch'),
    speed: document.getElementById('speed'),
    speedVal: document.getElementById('speed-val')
  };

  var state = { playing: true, showDet: false, speed: 1.4 };
  var sim = { parts: [], acc: 0, last: 0, frames: 0, fpsT: 0, fps: 0, hudT: 0, seed: 1 };
  var raf = null;

  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function spawn(cw) {
    var r = mulberry32((sim.seed += 1) * 2654435761);
    var roll = r(), label = 'plastic';
    if (roll < 0.40) label = 'plastic';
    else if (roll < 0.65) label = 'bubble';
    else if (roll < 0.85) label = 'organic';
    else label = 'fiber';
    var size = 0.5 + r() * 3.6, rx = size * PXMM / 2, ry = rx;
    if (label === 'fiber') { rx = size * PXMM * 0.22; ry = size * PXMM * 1.1; }
    sim.parts.push({ x: 30 + r() * (cw - 60), y: -30, vy: 0.7 + r() * 0.8, rx: rx, ry: ry, rot: label === 'fiber' ? (r() - 0.5) : 0, label: label });
  }

  function colOf(css, l) { return css.getPropertyValue('--p-' + l).trim() || '#888'; }

  function loop(t) {
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    var cw = canvas.clientWidth || 800, ch = canvas.clientHeight || 440;
    if (canvas.width !== Math.round(cw * dpr)) { canvas.width = Math.round(cw * dpr); canvas.height = Math.round(ch * dpr); }
    var ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var dt = Math.min(50, t - sim.last); sim.last = t;

    var g = ctx.createRadialGradient(cw / 2, ch * 0.4, 10, cw / 2, ch * 0.4, Math.max(cw, ch) * 0.7);
    g.addColorStop(0, '#E4E6E1'); g.addColorStop(1, '#C7CAC3');
    ctx.fillStyle = g; ctx.fillRect(0, 0, cw, ch);

    var spd = state.speed;
    sim.acc += dt * spd;
    while (sim.acc > 520) { sim.acc -= 520; spawn(cw); }

    var det = state.showDet;
    var css = getComputedStyle(document.documentElement);
    var seen = {};
    sim.parts.forEach(function (p) {
      p.y += p.vy * spd * dt * 0.06;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
      if (p.label === 'bubble') {
        ctx.fillStyle = '#D2D4CE'; ctx.strokeStyle = '#3d3f39'; ctx.lineWidth = Math.max(2, p.rx * 0.22);
        ctx.beginPath(); ctx.ellipse(0, 0, p.rx, p.ry, 0, 0, 7); ctx.fill(); ctx.stroke();
      } else {
        var rg = ctx.createRadialGradient(0, 0, 1, 0, 0, p.rx * 1.1);
        rg.addColorStop(0, 'rgba(26,28,25,0.9)'); rg.addColorStop(0.65, 'rgba(40,42,37,0.55)'); rg.addColorStop(1, 'rgba(58,60,54,0)');
        ctx.fillStyle = rg; ctx.beginPath(); ctx.ellipse(0, 0, p.rx, p.ry, 0, 0, 7); ctx.fill();
      }
      ctx.restore();
      if (p.y > -40 && p.y < ch + 40) seen[p.label] = (seen[p.label] || 0) + 1;
      if (det) {
        var col = colOf(css, p.label);
        ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.setLineDash(p.label === 'unknown' ? [6, 4] : []);
        var bx = p.x - p.rx - 3, by = p.y - p.ry - 3;
        ctx.strokeRect(bx, by, p.rx * 2 + 6, p.ry * 2 + 6); ctx.setLineDash([]);
        ctx.fillStyle = col; ctx.font = '500 11px Archivo, sans-serif';
        var lbl = VI[p.label], tw = ctx.measureText(lbl).width + 8;
        ctx.fillRect(bx, by - 15, tw, 15);
        ctx.fillStyle = '#fff'; ctx.fillText(lbl, bx + 4, by - 4);
      }
    });
    sim.parts = sim.parts.filter(function (p) { return p.y < ch + 60; });

    sim.frames++;
    if (t - sim.fpsT > 500) { sim.fps = Math.round(sim.frames / ((t - sim.fpsT) / 1000)); sim.frames = 0; sim.fpsT = t; }
    if (t - sim.hudT > 250) {
      sim.hudT = t;
      var total = Object.values(seen).reduce(function (a, b) { return a + b; }, 0);
      renderHud(total, seen, sim.fps);
    }
    raf = requestAnimationFrame(loop);
  }

  function renderHud(total, dist, fps) {
    els.count.textContent = total;
    els.fps.textContent = fps;
    var present = LABELS.filter(function (l) { return dist[l]; });
    if (!present.length) { els.dist.innerHTML = '<span class="hud-empty">Chưa có hạt trong khung</span>'; return; }
    var css = getComputedStyle(document.documentElement);
    els.dist.innerHTML = '<div class="hud-dist">' + present.map(function (l) {
      return '<span class="item"><span class="swatch-xs" style="background:' + colOf(css, l) + '"></span>' + VI[l] + ' ' + dist[l] + '</span>';
    }).join('') + '</div>';
  }

  function start() { if (!raf) { sim.last = performance.now(); raf = requestAnimationFrame(loop); } }
  function stop() { if (raf) { cancelAnimationFrame(raf); raf = null; } }

  function syncControls() {
    els.icon.innerHTML = state.playing ? PAUSE : PLAY;
    els.label.textContent = state.playing ? 'Tạm dừng' : 'Bật stream';
    els.toggle.classList.toggle('playing', state.playing);
    els.pause.hidden = state.playing;
    els.detSwitch.classList.toggle('on', state.showDet);
    els.speedVal.textContent = state.speed.toFixed(1) + '×';
  }

  els.toggle.addEventListener('click', function () {
    state.playing = !state.playing;
    syncControls();
    if (state.playing) start(); else stop();
  });
  els.det.addEventListener('click', function () { state.showDet = !state.showDet; syncControls(); });
  els.speed.addEventListener('input', function () { state.speed = parseFloat(this.value); els.speedVal.textContent = state.speed.toFixed(1) + '×'; });

  // Pause the loop when the tab is hidden; resume if it was playing.
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) stop(); else if (state.playing) start();
  });

  syncControls();
  start();
})();
