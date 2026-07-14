/* ===========================================================================
   bbox_overlay.js — vẽ bounding-box lên canvas overlay khớp với ảnh JPEG đã
   lưu, THEO toạ độ gốc (image_width/image_height). Tự tính hệ số scale từ kích
   thước hiển thị thực tế của <img> so với độ phân giải gốc → overlay luôn khớp
   dù ảnh responsive co giãn (plan §5).
   =========================================================================== */
(function () {
  'use strict';

  // Đồng bộ palette label với base.html tailwind.config.lbl
  const LABEL_COLORS = {
    plastic: '#60a5fa',
    bubble:  '#22d3ee',
    organic: '#a3e635',
    fiber:   '#c084fc',
    unknown: '#94a3b8'
  };
  // Glyph thêm để không phụ thuộc màu (a11y: color not the only indicator)
  const LABEL_GLYPH = {
    plastic: 'P', bubble: 'B', organic: 'O', fiber: 'F', unknown: '?'
  };

  function drawBboxes(stage) {
    const img = stage.querySelector('img.bbox-src');
    const canvas = stage.querySelector('canvas');
    if (!img || !canvas) return;

    const naturalW = img.naturalWidth || parseFloat(img.dataset.naturalWidth) || 0;
    const naturalH = img.naturalHeight || parseFloat(img.dataset.naturalHeight) || 0;
    if (!naturalW || !naturalH) return; // ảnh chưa load xong

    const dispW = img.clientWidth;
    const dispH = img.clientHeight;
    if (!dispW || !dispH) return;

    const dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    canvas.width = Math.round(dispW * dpr);
    canvas.height = Math.round(dispH * dpr);
    const sx = (dispW * dpr) / naturalW;
    const sy = (dispH * dpr) / naturalH;

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    let particles;
    try {
      particles = JSON.parse(stage.dataset.particles || '[]');
    } catch { particles = []; }

    ctx.lineWidth = Math.max(1.5, dpr * 1.25);
    ctx.font = `${Math.round(11 * dpr)}px "Fira Code", ui-monospace, monospace`;
    ctx.textBaseline = 'top';

    particles.forEach((p) => {
      const color = LABEL_COLORS[p.label] || LABEL_COLORS.unknown;
      const x = p.bbox_x * sx, y = p.bbox_y * sy, w = p.bbox_w * sx, h = p.bbox_h * sy;

      // Rect với viền sáng + nền mờ để nổi trên cả vùng sáng/tối của ảnh
      ctx.fillStyle = color + '22';
      ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = color;
      ctx.strokeRect(x, y, w, h);

      // Tag glyph + index ở góc trên-left
      const tag = `#${p.blob_index} ${LABEL_GLYPH[p.label] || '?'}`;
      const tagW = ctx.measureText(tag).width + 8 * dpr;
      const tagH = 14 * dpr;
      ctx.fillStyle = color;
      ctx.fillRect(x, Math.max(0, y - tagH), tagW, tagH);
      ctx.fillStyle = '#0b0f14';
      ctx.fillText(tag, x + 4 * dpr, Math.max(0, y - tagH + 1.5 * dpr));
    });
  }

  function initStage(stage) {
    const img = stage.querySelector('img.bbox-src');
    if (!img || stage.dataset.bboxReady === '1') return;
    stage.dataset.bboxReady = '1';

    const redraw = () => drawBboxes(stage);
    if (img.complete && img.naturalWidth) redraw();
    else img.addEventListener('load', redraw, { once: true });
    img.addEventListener('loadeddata', redraw, { once: true });

    // Responsive: vẽ lại khi ảnh co giãn
    let ro;
    if ('ResizeObserver' in window) {
      ro = new ResizeObserver(() => redraw());
      ro.observe(img);
    }
    window.addEventListener('resize', redraw, { passive: true });
  }

  function init() {
    document.querySelectorAll('.bbox-stage').forEach(initStage);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  // Re-init nếu trang inject stage sau (an toàn cho turbolink-style)
  window.AquaScope = window.AquaScope || {};
  window.AquaScope.initBbox = init;
})();
