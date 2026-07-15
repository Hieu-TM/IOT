// Draws detection bounding boxes over the stored backlit image and links them
// to the particle table (hovering a row highlights its box and vice versa).
//
// The overlay is an <svg> with viewBox = source resolution, sized 100% over the
// <img>; the browser scales it with the image, so it stays aligned at any
// responsive width without manual scale math. Reads its particle list from a
// sibling <script type="application/json"> and its natural size from data-imgw/h.
(function () {
  var SVGNS = 'http://www.w3.org/2000/svg';

  function el(name, attrs) {
    var n = document.createElementNS(SVGNS, name);
    for (var k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    return n;
  }

  function initFigure(fig) {
    var img = fig.querySelector('img');
    var dataScript = document.getElementById(fig.dataset.particles);
    if (!img || !dataScript) return;

    var parts;
    try { parts = JSON.parse(dataScript.textContent); } catch (e) { return; }
    if (!parts.length) return;

    var w = +fig.dataset.imgw || 640;
    var h = +fig.dataset.imgh || 480;
    var withLabels = fig.dataset.labels === '1';
    var tip = fig.querySelector('.bbox-tip');

    var svg = el('svg', { class: 'bbox-overlay', viewBox: '0 0 ' + w + ' ' + h });
    svg.setAttribute('preserveAspectRatio', 'none');

    var groups = [];
    parts.forEach(function (p, i) {
      var g = el('g', { 'data-idx': i });
      var rect = el('rect', {
        class: 'box', x: p.x, y: p.y, width: p.w, height: p.h, rx: 2,
        fill: p.color, 'fill-opacity': 0,
        style: 'stroke:' + p.color,
        'stroke-dasharray': p.dashed ? '6 4' : null
      });
      g.appendChild(rect);

      if (withLabels) {
        var tw = p.vi.length * 6.4 + 10;
        var ty = Math.max(0, p.y - 17);
        g.appendChild(el('rect', { x: p.x, y: ty, width: tw, height: 15, rx: 2, style: 'fill:' + p.color }));
        var text = el('text', {
          x: p.x + 5, y: Math.max(11, p.y - 6), 'font-size': 11,
          fill: '#fff', 'font-family': 'Archivo, sans-serif', 'font-weight': 500
        });
        text.textContent = p.vi;
        g.appendChild(text);
      }

      g.addEventListener('mouseenter', function () { highlight(i, true); });
      g.addEventListener('mouseleave', function () { highlight(i, false); });
      svg.appendChild(g);
      groups[i] = g;
    });
    fig.appendChild(svg);

    // Link to the particle table rows, if present on this page.
    var rows = {};
    document.querySelectorAll('#particle-table tr[data-idx]').forEach(function (tr) {
      var i = +tr.dataset.idx;
      rows[i] = tr;
      tr.addEventListener('mouseenter', function () { highlight(i, true); });
      tr.addEventListener('mouseleave', function () { highlight(i, false); });
    });

    function highlight(i, on) {
      var g = groups[i];
      if (g) g.classList.toggle('on', on);
      if (rows[i]) rows[i].style.background = on ? 'var(--surface-1)' : '';
      if (tip && withLabels) showTip(i, on);
    }

    function showTip(i, on) {
      if (!on) { tip.style.display = 'none'; return; }
      var p = parts[i];
      tip.innerHTML =
        '<div class="tip-head"><span class="swatch-xs" style="background:' + p.color + '"></span>' + p.vi + '</div>' +
        '<div class="tip-sub">' + p.size_mm + ' mm · độ tin cậy ' + p.conf_pct + '%</div>';
      tip.style.left = (p.cx / w * 100) + '%';
      tip.style.top = (p.y / h * 100) + '%';
      tip.style.display = 'block';
    }
  }

  document.querySelectorAll('.bbox-figure').forEach(initFigure);
})();
