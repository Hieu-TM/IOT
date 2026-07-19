"""Map detector output to the /api/ingest `metadata` dict (IngestPayload shape).

Honesty notes carried in the values themselves:
  * size_mm = max(w, h) / px_per_mm  — approx Feret diameter via calibration.
  * area_px = w * h                  — BBOX area, NOT true blob area (a plain
    detector has no mask). Documented approximation; replace with real blob
    area only if a CV/segmentation stage is added later.
  * device       — khối /device của board (firmware, thiết lập camera lúc chụp),
    chỉ có khi chụp từ board. Đi vào raw_metadata_json để truy xuất nguồn gốc.
"""

from .naming import resolve_px_per_mm


def build_metadata(*, detections, image_width, image_height, sample_code,
                   captured_at, device_id, px_per_mm, batch_lot=None,
                   device_info=None):
    px, _ = resolve_px_per_mm(px_per_mm)  # tolerate None; CLI resolves+warns first
    particles = []
    for i, d in enumerate(detections):
        x, y, w, h = d.bbox_xywh
        particles.append({
            "blob_index": i,
            "centroid_x": x + w / 2,
            "centroid_y": y + h / 2,
            "bbox_x": int(x),
            "bbox_y": int(y),
            "bbox_w": int(w),
            "bbox_h": int(h),
            "area_px": float(w * h),
            "size_mm": (max(w, h) / px) if px else 0.0,
            "label": d.class_name,
            "confidence": float(d.confidence),
        })
    metadata = {
        "device_id": device_id,
        "sample_code": sample_code,
        "batch_lot": batch_lot,
        "captured_at": captured_at.isoformat(),
        "px_per_mm": px,
        "image_width": image_width,
        "image_height": image_height,
        "particles": particles,
    }
    if device_info:
        # IngestPayload bỏ qua khóa lạ, nhưng ingest.py lưu nguyên văn chuỗi
        # metadata vào raw_metadata_json — nên khối này vẫn tới được sổ audit
        # mà không phải sửa gì bên web.
        metadata["device"] = device_info
    return metadata
