# Plan: Hệ thống Web Aqua Scope (triển khai)

> **Vai trò:** đây là **PLAN** (làm thế nào — lộ trình, phân rã module, verify).
> Phần **cái gì / tại sao / hợp đồng / yêu cầu** ở SPEC: `docs/superpowers/specs/2026-07-14-web-system-design.md`.
> Mọi tham chiếu `FR-*/SEC-*/DATA-*/PERF-*` bên dưới trỏ về SPEC.
> **Thay thế** phần §7/§8/§9 của `web_plan.md` (nay là lịch sử).

---

## 0. Hiện trạng (2026-07-14)

- **Module 1** (core: `config/database/models/main`) — **đã code**, có smoke test.
- **Module 2** (`routers/ingest.py`) — **đã code** hành vi chính, **nhưng thiếu** SEC-1 (validate `sample_code`), SEC-3 (giới hạn upload), DATA-1 (UTC), và **chưa có test**.
- **Module 3** (`routers/samples.py`) — **đã code**, **nhưng thiếu** SEC-2 (CSV injection), PERF-1 (bỏ N+1), và **chưa có test**.
- **Module 4** (mock), **Module 5** (frontend), **Module 6** (wiring) — **chưa làm**. Router M2/M3 **chưa `include_router` vào `main.py`** → `/api/*` hiện chưa truy cập được.

---

## 1. Sơ đồ phụ thuộc

```
M1 Core [gate, gần xong] ──┬──▶ M2 Ingest (+SEC-1/3, DATA-1, test) ──┐
                           └──▶ M3 Read   (+SEC-2, PERF-1, test)    ──┼──▶ M6 Wiring + E2E
M4 Mock      ── song song, không phụ thuộc code ─────────────────────┤
M5 Frontend  ── song song, dùng fixture; nối M3 ở M6 ────────────────┘
```

Data contract (SPEC §5) đã chốt cứng → module dựa vào **hợp đồng viết**, không chờ nhau code xong (chỉ cần file import tồn tại đúng tên).

## 2. Bảng module

| # | Module | File sở hữu | Phụ thuộc | Việc phải làm (ngoài phần đã code) | Tiêu chí xong |
|---|---|---|---|---|---|
| **1** | Core & Data Layer | `requirements.txt`, `app/{config,database,models,main}.py` | — | Thêm hằng `WARN_PARTICLE_COUNT`, `MAX_UPLOAD_BYTES` vào `config.py`; ràng buộc validate SPEC §5.1 vào `IngestPayload` (regex `sample_code` SEC-1, bound `confidence/size/bbox`) | uvicorn chạy, tạo 2 bảng; smoke test xanh |
| **2** | Ingest API | `app/routers/ingest.py` | M1 | **SEC-1** reject `sample_code` xấu (422); **SEC-3** 413 khi >MAX; **DATA-1** convert `captured_at`→UTC; **test_ingest.py** (201/200/422/400/413/500, idempotent, rollback+xoá ảnh, traversal 422) | Test xanh; đúng FR-1 |
| **3** | Read API | `app/routers/samples.py` | M1 | **SEC-2** sanitize ô CSV; **PERF-1** gộp particle 1 truy vấn; **test_read_api.py** (list/detail/csv, DB rỗng, filter, histogram biên, injection vô hiệu) | Test xanh; đúng FR-2/3 |
| **4** | Mock Sender | `web/mock_sender.py` | hợp đồng FR-1 | Viết theo FR-5 (class weight, size range, ảnh Pillow tại bbox); tự test bằng HTTP server giả nếu M2 chưa xong | POST đúng FR-1, N mẫu hợp lý |
| **5** | Frontend | `app/routers/pages.py`, `templates/*`, `static/**` | fixture (SPEC §7) | 4 trang (Dashboard/History/Detail/**Stream**); design tokens §7.1; `bbox_overlay.js`/`charts.js`/`stream_sim.js`; Chart.js vendor local; empty/loading/lỗi | 4 trang render với fixture; không CDN |
| **6** | Wiring & Verify | `main.py` (include_router, mount `/static` `/images`), `.gitignore` (thêm `web/backend/data/`) | M1–M5 | Ráp thật, thay fixture bằng M3 | Chạy đủ kịch bản §4 |

## 3. Lộ trình theo pha

1. **Phase 1 — Core hoàn thiện.** Bổ sung hằng số + ràng buộc validate SPEC §5.1 vào M1. *Verify:* smoke test + import sạch.
2. **Phase 2 — Ingest cứng cáp.** Thêm SEC-1/SEC-3/DATA-1 vào M2 + `test_ingest.py`. *Verify:* `pytest test_ingest.py` xanh, gồm ca `sample_code="../x"`→422.
3. **Phase 3 — Read cứng cáp.** Thêm SEC-2/PERF-1 vào M3 + `test_read_api.py`. *Verify:* injection test + đếm số truy vấn (không N+1).
4. **Phase 4 — Mock sender.** M4 theo FR-5. *Verify:* bắn vào M2, N dòng xuất hiện.
5. **Phase 5 — Frontend.** M5: 4 trang + assets + stream sim. *Verify:* duyệt bằng fixture; kiểm không có `<script src=http>`.
6. **Phase 6 — Wiring + E2E.** M6: include router, mount static/images, `.gitignore`. *Verify:* kịch bản §4.
7. **Phase 7 (tương lai, tách riêng) — Firmware.** `HTTPClient` + build JSON trong `loopCycle()` sau `runVision()`, POST đúng FR-1; lỗi POST non-fatal (FR-6).

## 4. Kịch bản verify E2E (không cần phần cứng)

1. `pip install -r web/requirements.txt`
2. `uvicorn app.main:app --port 8000 --reload` (từ `web/backend/`)
3. `python web/mock_sender.py --count 15 --interval 2`
4. `/` → dashboard hiện mẫu mới nhất trong 15.
5. `/history` → đủ 15 dòng; thử filter ngày/lô.
6. Chi tiết 1 mẫu → ảnh + bbox khớp elip mock, 2 chart đúng.
7. Xuất CSV → mở bằng bảng tính: **không** ô nào chạy như công thức; số dòng khớp tổng `particle_count`.
8. `/stream` → bật stream + toggle detection thấy bbox; xác nhận không request nào tới `/api/*`.
9. Dừng+chạy lại uvicorn → dữ liệu còn.
10. `python web/mock_sender.py --count 100` → phân trang History OK.
11. `pytest -q` → toàn bộ xanh (mọi module có test happy + lỗi).
12. **Ca an ninh:** POST `sample_code="../../evil"` → 422, không có file ngoài `data/images/`.

## 5. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| Sửa M2/M3 (thêm SEC/DATA fix) làm hồi quy hành vi đã chạy | Viết test **trước** khi sửa (TDD); test bao ca cũ + ca fix |
| DATA-1 (UTC) đổi cách lưu datetime → dữ liệu cũ lệch | DB hiện chỉ có dữ liệu mock/dev → xoá `data/` tạo lại; ghi rõ trong README |
| Stream sim ngốn CPU khi trình chiếu | `requestAnimationFrame` + giới hạn số hạt; thanh chỉnh tốc độ |
| M5 dựng bằng fixture lệch shape thật M3 | Fixture copy đúng từ response `SampleDetail` (SPEC §5.2) |

## 6. Không thuộc scope đợt này
Code frontend/backend thật (đang dừng ở spec+plan); detection thật/real-time (stream là mock); auth/multi-user; deploy internet-facing.
