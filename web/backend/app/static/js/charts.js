/* ===========================================================================
   charts.js — khởi tạo Chart.js (vendor local, global `Chart`).
   - Phân bố kích thước → bar chart (histogram, bin fixed 0.3mm, plan §2.2),
     có value label trên mỗi bar để không chỉ phụ thuộc màu/trục.
   - Phân bố loại → doughnut (≤5 nhóm) với legend — tránh pie cồng kềnh (chart domain).
   Dữ liệu đọc từ <script type="application/json" id="…"> để Jinja chỉ cần in JSON.
   =========================================================================== */
(function () {
  'use strict';

  const LABEL_COLORS = {
    plastic: '#60a5fa', bubble: '#22d3ee', organic: '#a3e635',
    fiber: '#c084fc', unknown: '#94a3b8'
  };
  const ORDER = ['plastic', 'bubble', 'organic', 'fiber', 'unknown'];
  const LABEL_VI = { plastic: 'Plastic', bubble: 'Bubble', organic: 'Organic', fiber: 'Fiber', unknown: 'Unknown' };

  const INK = '#0b0f14';
  const GRID = 'rgba(148,163,184,0.14)';
  const TICK = '#94a3b8';

  // Chart.js mặc định quá sáng → ép theme tối + font phù hợp
  function baseOpts(extra) {
    return Object.assign({
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: TICK, font: { family: '"Fira Sans"', size: 12 }, usePointStyle: true, pointStyle: 'circle' } },
        tooltip: {
          backgroundColor: 'rgba(15,20,25,0.96)', borderColor: 'rgba(249,115,22,0.5)', borderWidth: 1,
          titleColor: '#f1f5f9', bodyColor: '#cbd5e1',
          titleFont: { family: '"Fira Sans"', weight: '600' }, bodyFont: { family: '"Fira Code"' },
          padding: 10, displayColors: true
        }
      }
    }, extra || {});
  }

  function readJSON(id) {
    const el = document.getElementById(id);
    if (!el || !el.textContent.trim()) return null;
    try { return JSON.parse(el.textContent); } catch { return null; }
  }

  function initSizeHistogram() {
    const data = readJSON('chart-size-data');
    const canvas = document.getElementById('chart-size');
    if (!data || !canvas) return;

    const bins = data.bins || [];
    const labels = bins.map(b => `${(+b.size_mm_from).toFixed(1)}–${(+b.size_mm_to).toFixed(1)}`);
    const counts = bins.map(b => b.count);

    // — Plugin: vẽ value label trên mỗi bar (chart domain: "Add value labels")
    const valueLabels = {
      id: 'valueLabels',
      afterDatasetsDraw(chart) {
        const { ctx, data, scales: { y } } = chart;
        if (!y) return;
        ctx.save();
        ctx.font = '600 10px "Fira Code"';
        ctx.fillStyle = '#cbd5e1';
        ctx.textAlign = 'center';
        data.datasets[0].data.forEach((v, i) => {
          if (!v) return; // bỏ qua bar 0 để đỡ rối
          const meta = chart.getDatasetMeta(0).data[i];
          if (!meta) return;
          ctx.fillText(String(v), meta.x, meta.y - 4);
        });
        ctx.restore();
      }
    };

    new Chart(canvas, {
      type: 'bar',
      data: { labels, datasets: [{
        label: 'Số hạt',
        data: counts,
        backgroundColor: counts.map((_, i) => 'rgba(249,115,22,0.55)'),
        borderColor: 'rgba(249,115,22,0.9)',
        borderWidth: 1,
        borderRadius: 3,
        hoverBackgroundColor: 'rgba(249,115,22,0.8)',
        maxBarThickness: 26
      }] },
      options: baseOpts({
        plugins: { /* tooltip default + unit */
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => `${c.parsed.y} hạt (${labels[c.dataIndex]} mm)` } }
        },
        scales: {
          x: { grid: { color: GRID, display: false }, ticks: { color: TICK, font: { family: '"Fira Code"', size: 9 }, maxRotation: 0, autoSkip: true, autoSkipPadding: 8 }, border: { color: GRID } },
          y: { beginAtZero: true, grid: { color: GRID }, ticks: { color: TICK, font: { family: '"Fira Code"', size: 10 }, precision: 0 }, border: { color: GRID } }
        }
      }),
      plugins: [valueLabels]
    });
  }

  function initLabelDonut() {
    const data = readJSON('chart-label-data');
    const canvas = document.getElementById('chart-label');
    if (!data || !canvas) return;

    // Sắp giảm dần để lát lớn nhất trước (chart domain: pie guidance)
    const entries = ORDER
      .map(k => [k, data[k] || 0])
      .filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1]);

    const labels = entries.map(([k]) => LABEL_VI[k] || k);
    const values = entries.map(([, v]) => v);
    const colors = entries.map(([k]) => LABEL_COLORS[k] || LABEL_COLORS.unknown);

    new Chart(canvas, {
      type: 'doughnut',
      data: { labels, datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: INK,
        borderWidth: 2,
        hoverOffset: 6
      }] },
      options: baseOpts({
        cutout: '62%',
        plugins: {
          legend: { position: 'right', labels: { color: TICK, font: { family: '"Fira Sans"', size: 12 }, usePointStyle: true, pointStyle: 'circle', padding: 12, boxWidth: 10 } },
          tooltip: { callbacks: {
            label: (c) => {
              const total = values.reduce((a, b) => a + b, 0) || 1;
              const pct = ((c.parsed / total) * 100).toFixed(0);
              return ` ${c.label}: ${c.parsed} hạt (${pct}%)`;
            }
          } }
        }
      })
    });
  }

  function init() { initSizeHistogram(); initLabelDonut(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
