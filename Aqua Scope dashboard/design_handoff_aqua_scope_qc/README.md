# Handoff: Aqua Scope — QC Dashboard

## Overview
Aqua Scope is a read-only QC dashboard for a water-quality monitoring station in a food-processing plant. It traces particle samples captured by a backlit imaging device (`aquascope-01`): dashboard overview, a filterable history/audit table, a per-sample detail view (image + bbox overlay + particle table + histogram + raw JSON), and a live "stream demo" canvas simulation. UI copy is Vietnamese throughout. Data model is append-only — there are no edit/delete affordances anywhere by design.

## About the Design Files
The files in this bundle (`Aqua Scope QC.dc.html`, `support.js`) are **design references built in HTML/React-like JSX**, not production code to copy directly. They render as a single-page app with client-side view switching (no router, no backend — all data is a hardcoded mock array and synthetic image generation). Your task is to **recreate this design in the target codebase's actual stack** (its component library, routing, state management, real API calls) — reproducing the exact layout, spacing, color, typography, and interaction behavior described below, not the literal markup.

## Fidelity
**High-fidelity.** Colors, spacing, type sizes, and component states are final. Treat hex/px values below as exact. The particle bbox synthesis and canvas stream simulation are demo-only stand-ins for a real detection feed/image — implement those against real backend data instead of porting the mock math.

## Design System
Built on the **Modernist** design system's structural principles (Archivo typeface, flat surfaces, thin 1px hairline borders, flush-left labels, generous spacing, 8-12px card radii) combined with a custom domain color palette (teal/amber/blue + a 5-color particle-label map) that carries QC meaning and should NOT be swapped for Modernist's red accent — the color-to-meaning mapping is a functional requirement of this product, not a brand choice.

## Screens / Views

### 1. Dashboard (`Bảng điều khiển QC`)
**Purpose:** At-a-glance shift summary + latest sample + quick nav to history.
**Layout:** Left sidebar (236px, fixed) + main content area. Content max-width 1180px, vertical flex, 20px gaps.
- **Metric tile row**: CSS grid, `repeat(auto-fit, minmax(190px,1fr))`, 14px gap. 4 tiles: "Mẫu hôm nay" (sample count), "Tổng hạt hôm nay" (total particle count), "Tỉ lệ nhựa" (plastic % in teal text), "Cảnh báo" (warning count — tile background switches to amber-bg (`#FAEEDA` light / `rgba(239,159,39,.15)` dark) when count > 0, otherwise neutral `--surface-1`). Tile padding 16px 18px, radius 8px (`--r-tile`). Value text 30px/600, label 12.5px, hint caption 11.5px `--text-3`.
- **2-column row** (`1.5fr / 1fr`, 20px gap, collapses to 1 column ≤900px): "Mẫu mới nhất" card (status chip + link to detail + backlit image + 4-row metadata list) beside "Phân bố loại" card (132px donut chart with center total label + color-swatch legend list with %).
- **Recent samples table**: last 5 today's samples, columns Mã mẫu / Mã lô / Giờ chụp / Số hạt / Trạng thái, row click opens detail. Header row 11px/500 `--text-2`.
- Collapsible "Ghi chú thiết kế" note block (`<details>`) at bottom explaining layout rationale — informational only, can be dropped in production.
- **Empty state**: icon + title + message centered card, shown when no samples loaded.

### 2. History / Audit (`Lịch sử · audit`)
**Purpose:** Dense, filterable audit log of all samples; CSV export.
**Layout:** Filter bar (from-date, to-date, lot-code select, clear-filters button, CSV export button) in a bordered card, 16px 18px padding. Below: result count summary caption, then a dense data table (min-width 820px, horizontal scroll on overflow) with columns Mã mẫu (monospace) / Mã lô / Thời gian chụp / Số hạt (right-aligned) / Phân bố loại (colored count chips per label) / Trạng thái (status chip) / row action link "Chi tiết →". Row height ~12px vertical padding, 1px top border between rows, no card-per-row. Pagination controls bottom-right (10 rows/page).
**States:** loading (shimmer skeleton rows), error (centered icon + retry button), empty (no filter matches), normal.
**Note:** No edit/delete UI anywhere — data is append-only.

### 3. Sample Detail (`Chi tiết mẫu`)
**Purpose:** Full inspection of one sample's backlit image + detected particles.
**Layout:** 2-column grid `1.35fr / 1fr` (stacks on mobile), left column sticky (`top:76px`) containing the backlit image card with SVG bbox overlays (colored per label, dashed for "unknown", labeled tag on hover) and a color legend row below. Right column (16px gap, stacked cards): metadata card (2-col key/value grid: Mã lô, Thiết bị, Giờ chụp, Giờ nhận, Hiệu chuẩn px/mm, Kích thước ảnh), particle table (Nhãn / Tin cậy / Kích thước / Diện tích / Tâm x,y — hover row ↔ hover bbox is bidirectional), size histogram (bar chart, fixed 0.3mm bins, 0–5mm range, blue bars), label distribution (horizontal bar list), and a collapsible raw metadata JSON block (monospace, `<pre>`, toggle open/closed).
**States:** loading (skeleton), error, 404/not-found (large "404" + message + "Về lịch sử" button), normal.

### 4. Stream Demo (`Stream demo`)
**Purpose:** Live canvas simulation of the backlit particle flow, for demoing the imaging concept without a live camera feed.
**Layout:** Amber demo-mode banner at top (`Chế độ demo — mô phỏng, không ghi vào lịch sử`) — always visible, explains this view is not real detection data. Below: a canvas (452px tall, light gray-green background `#C9CCC5`) rendering falling particle blobs (ellipses, gradient-shaded, bubbles get a highlight, fibers are elongated+rotated). Floating HUD (top-left, translucent blur card): live particle count + FPS; second pill shows per-label counts currently visible. Toolbar below canvas: play/pause button (teal when off / gray when playing), "Hiện detection" toggle switch (pill switch, teal when on) that overlays colored bbox+label per particle when enabled, and a speed slider (0.4×–3×).
**Pause overlay**: centered pill "Đã tạm dừng · nhấn Bật stream" when paused.

### Sidebar & Header (persistent chrome)
- Sidebar: brand mark (teal rounded-square logo) + "Aqua Scope" wordmark, 3 nav buttons (Bảng điều khiển / Lịch sử · audit / Stream demo), a "Tham chiếu" divider section with a "Trạng thái" (states gallery) link, and a footer block showing device online status dot + "aquascope-01 · trực tuyến" + a note "Dữ liệu chỉ đọc · append-only."
- Header: sticky, blurred-glass background, screen title (16.5px/600), a "LAN · demo" status pill, a "Xem trạng thái" state-simulator dropdown (dashboard/history/detail only — dev/QA tool, can be dropped in production or kept behind a feature flag), dark-mode toggle (persisted), "Xuất CSV" primary teal button.
- Toast: bottom-center floating confirmation (e.g. after CSV export), auto-dismiss ~2.6s.

## Interactions & Behavior
- Client-side view switching (dashboard/history/detail/stream/states-gallery) — no page reload.
- Dark mode: toggle in header, persisted to localStorage, applied via a `data-theme="dark"` attribute that swaps all CSS custom properties (0.22s color-transition).
- History filters (date range + lot) are client-applied and reset pagination to page 1 on change; "Xuất CSV" always exports according to the currently active filter.
- Sample detail image ↔ particle table hover is bidirectional (hovering a table row highlights its bbox on the image and vice versa).
- Raw JSON panel is collapsed by default; toggle button flips an open/closed state.
- Stream demo runs a `requestAnimationFrame` loop; play/pause toggles the loop, speed slider scales fall speed and spawn rate, "Hiện detection" toggle overlays bbox+label per particle without affecting the underlying simulation.
- "Xem trạng thái" dropdown (dashboard/history/detail) is a design/QA affordance to preview empty/loading/error/404 states without real data — decide with your team whether to ship it (e.g. behind a debug flag) or drop it.

## State Management
Per-screen states needed for real implementation:
- Dashboard: `normal`, `empty` (no samples loaded)
- History: `normal`, `empty` (filters match nothing), `loading`, `error`
- Detail: `normal`, `notfound` (404 / invalid sample id), `loading`, `error`
- Filters: `fromDate`, `toDate`, `lotCode`, `page` (History)
- Detail: `sampleId` (route param), `jsonOpen` (bool), `hoveredParticleIndex`
- Stream: `playing` (bool), `showDetections` (bool), `speed` (0.4–3.0)
- Global: `theme` (light/dark, persisted), `toast` (transient message)

**Data fetching requirements for production:** samples list (paginated, filterable by date range + lot code), single sample detail (metadata + particle detections + backlit image URL), CSV export endpoint respecting active filters, and — for the stream view — either a live MJPEG/WebSocket feed from the device or an explicit "demo mode" flag so it's never confused with a real audit record.

## Design Tokens

**Color** (light / dark):
- Background: `--bg` `#F4F5F3` / `#0F1214`
- Surface: `--surface` `#FFFFFF` / `#171B1E`; `--surface-1` `#F0F1EE` / `#1E2327` (tile fill, table header); `--surface-2` `#E9EAE6` / `#262C31` (hover/skeleton)
- Border: `--border` `rgba(24,26,22,.10)` / `rgba(255,255,255,.09)`; `--border-strong` `rgba(24,26,22,.18)` / `rgba(255,255,255,.18)`
- Text: `--text` `#1B1D19` / `#E7E9E6`; `--text-2` `#5C5E58` / `#A7ABA4`; `--text-3` `#8A8C84` / `#797E77`
- Teal (brand / "Đạt" pass status): `--teal` `#1D9E75` / `#2FB88A`; `--teal-strong` `#0F6E56` / `#7FE0BD`; `--teal-bg` `#E1F5EE` / `rgba(29,158,117,.16)`; `--teal-text` `#0F6E56` / `#5FD3A6`
- Amber (backlit / "Cảnh báo" warning status): `--amber` `#EF9F27` / `#F3B24D`; `--amber-strong` `#854F0B` / `#F8CB80`; `--amber-bg` `#FAEEDA` / `rgba(239,159,39,.15)`; `--amber-text` `#854F0B` / `#F3B24D`
- Blue (info / histogram bars): `--blue` `#378ADD` / `#5AA2E8`; `--blue-bg` `#E8F1FC` / `rgba(55,138,221,.16)`; `--blue-text` `#1E5FA8` / `#84B8EF`
- Gray (neutral): `--gray` `#888780` / `#9A998F`
- **Particle label colors** (used consistently across bbox overlay, charts, chips — do not deviate): plastic `--p-plastic` = teal; bubble `--p-bubble` = blue; organic `--p-organic` = amber; fiber `--p-fiber` = gray (`#888780`/`#9A998F`); unknown `--p-unknown` = `#B4B2A9` (both modes, dashed outline in bbox)

**Radius:** `--r-card` 12px (cards), `--r-tile` 8px (metric tiles), `--r-chip` 999px (status chips/pills)

**Shadow:** `--shadow`: `0 1px 2px rgba(24,26,22,.05)` light / `0 1px 2px rgba(0,0,0,.4)` dark (cards only — flat otherwise, no heavy elevation)

**Typography:** Archivo (400/500/600), loaded via Google Fonts. Scale: 30px/600 (metric values), 16.5px/600 (page title), 14–14.5px/600 (card headings), 13px/400 (body), 12–12.5px (table/meta text), 11–11.5px (captions/labels), 10–10.5px (micro labels/section eyebrows). Monospace (`ui-monospace, Menlo, monospace`) for sample codes, lot codes, JSON, centroid coordinates.

**Spacing:** page padding 26px top / 28px sides; card padding 16-18px; grid gaps 14–20px; row vertical padding ~9-12px.

**Borders:** 1px hairlines throughout (`--border`), not the heavier rules Modernist uses on its own pages — this product prioritizes dense tabular scanning over poster-style structure.

## Assets
- **Brand mark**: small inline SVG (teal rounded-square with a ring + two dots) — replace with the real Aqua Scope logo if one exists.
- **Icons**: minimal inline SVG line icons (grid, list, wave, layers, download, check, warning-triangle, sun/moon), 16–30px, stroke-based, 1.5–1.8px stroke width, rounded caps/joins. Recreate with your codebase's icon set (e.g. Lucide) at equivalent weights.
- **Backlit particle images**: synthetic — a soft gray-green radial-gradient field (`#E4E6E1` → `#C9CCC5`) with dark soft-edged ellipse "blobs" per particle (bubbles get a light-gray ring + highlight; fibers are elongated and rotated). This stands in for the real device's backlit photograph. In production, swap for the actual captured image with detection bboxes drawn as an overlay (SVG/canvas) at the same coordinate scale (14 px/mm calibration, 640×480 source resolution).
- **Charts**: donut (dashboard) and bar histogram (detail) are hand-built inline SVG, not a charting library — recreate with your codebase's chart component of choice using the same color mapping and proportions.

## Files
- `Aqua Scope QC.dc.html` — full design reference (all 4 screens + states gallery + chrome), inline-styled, React-class-component-style logic embedded in the file.
- `support.js` — runtime helper the reference file depends on to render (not application logic to port).
