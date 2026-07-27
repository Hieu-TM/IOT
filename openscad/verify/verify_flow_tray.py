#!/usr/bin/env python3
"""verify_flow_tray.py — kiểm sâu hơn export-stl.sh cho openscad/print/print_flow_tray.stl.

export-stl.sh (OpenSCAD --export-format) chỉ đọc cảnh báo "non-manifold/self-intersect"
mà OpenSCAD tự in ra — 3 lỗi Critical ghi trong
docs/research/2026-07-23-khay-lang-song-nghien-cuu-hop-nhat.md PHAN D (thành mỏng
knife-edge 0.231mm, miệng loe bị bịt kín, vách baffle trôi nổi rời khối chính) đều
xuất STL "sạch" theo kiểm tra đó — vì manifold hợp lệ (mọi mặt khép kín) không nói lên
gì về việc 1 khối có TÁCH RỜI khỏi khối chính hay không, hay 1 vùng thành có ĐỦ DÀY để
in hay không.

2 kiểm tra bổ sung ở đây:
  1. body_count (số khối liên thông) — flow_tray() phải là 1 khối liền duy nhất.
     >1 nghĩa là có mảnh rời (đúng loại lỗi #5 PHAN D: vách trôi nổi).
  2. Quét độ dày thành bằng ray casting (điểm mẫu trên mặt ngoài, bắn tia pháp tuyến
     vào trong, đo khoảng cách tới mặt đối diện) — flag mọi điểm mỏng hơn ngưỡng in
     tối thiểu. Đây là kiểm tra XẤP XỈ (heuristic), không thay thế nhìn mặt cắt thật,
     nhưng bắt được đúng loại lỗi #6 PHAN D (thành 0.231mm).

Dùng: python openscad/verify/verify_flow_tray.py [đường_dẫn.stl]
"""
import sys
import numpy as np
import trimesh

MIN_WALL_MM = 0.5        # dưới mức này = chắc chắn không in được (< 2 lớp nozzle 0.4mm)
WARN_WALL_MM = 1.05      # dưới mức này (nhưng >= MIN_WALL_MM) = cảnh báo, sát ngưỡng thiết kế 1.2mm
SAMPLE_COUNT = 6000
ALIGN_MIN = 0.7           # lọc hit giả trên mặt cong nhiều facet — xem ghi chú dưới
MIN_HIT_DIST = 0.02       # bỏ hit tự-chạm gần như 0 tuyệt đối (nhiễu số học thuần)

# Vùng ĐÃ BIẾT là mỏng theo THIẾT KẾ (không phải lỗi mới):
#   - "gờ kê" đỡ đĩa acrylic dày đúng ledge_plate_t=1.0mm theo constants.scad,
#     ghi rõ "bậc nhỏ ... cho phép" — nằm ở vành khuyên bán kính quanh
#     pocket_d/2..tray_inner/2 (~20.0-20.7mm), z quanh đáy khay.
#   - Mép cắt phẳng z=0 tại miệng loe (bellmouth_boss() bị intersection() cắt
#     phẳng đúng sàn khay z=0 — đây là biên MỞ có chủ đích của khay (đáy hở,
#     xem đầu flow_tray_003.scad), không phải 1 bức thành.


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "openscad/print/print_flow_tray.stl"
    mesh = trimesh.load(path, force="mesh")

    print(f"== {path} ==")
    print(f"Faces: {len(mesh.faces)}  Vertices: {len(mesh.vertices)}")

    # --- 1. Số khối liên thông ---
    bodies = mesh.split(only_watertight=False)
    print(f"\n[1] Số khối liên thông (body_count): {len(bodies)}")
    if len(bodies) == 1:
        print("    OK — 1 khối liền duy nhất, không có mảnh rời.")
    else:
        print("    !!! CẢNH BÁO: >1 khối — có mảnh KHÔNG gắn liền vào thân chính.")
        for i, b in enumerate(bodies):
            print(f"      body[{i}]: {len(b.faces)} faces, bbox={b.bounds.tolist()}, "
                  f"volume={b.volume:.2f}mm3")

    # --- 2. Watertight tổng thể ---
    print(f"\n[2] Watertight: {mesh.is_watertight}")

    # --- 3. Quét độ dày thành bằng ray casting pháp tuyến ---
    print(f"\n[3] Quét độ dày thành ({SAMPLE_COUNT} điểm mẫu, ngưỡng "
          f"MIN={MIN_WALL_MM}mm / WARN={WARN_WALL_MM}mm)")
    points, face_idx = trimesh.sample.sample_surface(mesh, SAMPLE_COUNT)
    normals = mesh.face_normals[face_idx]

    # Bắn tia từ ngay trong mặt (lùi vào 1e-2mm theo pháp tuyến trong) theo hướng
    # pháp tuyến TRONG (−normal) để tìm mặt đối diện gần nhất.
    #
    # ⚠️ multiple_hits=False + lấy hit gần nhất là SAI trên mặt cong nhiều facet
    # (ví dụ vòng gai giữ ống — hose barb — trên ngạnh, dựng từ cone d1/d2 hẹp):
    # tia có thể "liếm" trúng 1 facet lân cận gần như đồng phẳng với facet xuất
    # phát, cho khoảng cách ~0.01-0.1mm GIẢ (không phải độ dày thật, đã xác nhận
    # bằng thực nghiệm: các hit giả này rơi đúng vào toạ độ X của 2 vòng gai trên
    # barb(), với giá trị "alignment" gần như HẰNG SỐ ~0.51 — đặc trưng của 1 góc
    # côn cố định, không phải độ dày thay đổi ngẫu nhiên). Lọc bằng điều kiện pháp
    # tuyến: mặt ĐỐI DIỆN thật của 1 vỏ mỏng có pháp tuyến hướng gần NHƯ SONG SONG
    # CÙNG CHIỀU tia (vì nó là mặt "trong" quay vào lòng rỗng), trong khi hit giả
    # trên cùng mặt lồi có alignment thấp hơn hẳn — ALIGN_MIN=0.7 cắt được đúng
    # cụm giả 0.51 mà không cắt các hit thật (đã kiểm bằng phân tích thủ công cụm
    # dữ liệu trước khi chốt ngưỡng này).
    origins = points - normals * 1e-2
    directions = -normals

    locations, index_ray, index_tri = mesh.ray.intersects_location(
        ray_origins=origins, ray_directions=directions, multiple_hits=True
    )

    thickness_by_ray = {}
    if len(locations):
        dists = np.linalg.norm(locations - origins[index_ray], axis=1)
        hit_normals = mesh.face_normals[index_tri]
        ray_dirs_per_hit = directions[index_ray]
        alignment = np.einsum("ij,ij->i", hit_normals, ray_dirs_per_hit)
        valid = (alignment > ALIGN_MIN) & (dists > MIN_HIT_DIST)
        for ray_i, d, ok in zip(index_ray, dists, valid):
            if not ok:
                continue
            if ray_i not in thickness_by_ray or d < thickness_by_ray[ray_i]:
                thickness_by_ray[ray_i] = d

    thin_min, thin_warn = [], []
    for i in range(len(points)):
        t = thickness_by_ray.get(i)
        if t is None:
            continue  # tia không trúng mặt nào (điểm ở mép hở/lỗ thiết kế — bỏ qua)
        if t < MIN_WALL_MM:
            thin_min.append((t, points[i]))
        elif t < WARN_WALL_MM:
            thin_warn.append((t, points[i]))

    hit_ratio = len(thickness_by_ray) / len(points)
    print(f"    Tia trúng mặt đối diện: {len(thickness_by_ray)}/{len(points)} "
          f"({hit_ratio:.0%}) — phần còn lại là điểm ở mép lỗ/khe hở (bình thường)")

    if thin_min:
        thin_min.sort(key=lambda x: x[0])
        print(f"    !!! {len(thin_min)} điểm DƯỚI {MIN_WALL_MM}mm (không in được):")
        for t, p in thin_min[:15]:
            print(f"        {t:.3f}mm tại {p.round(2).tolist()}")
        if len(thin_min) > 15:
            print(f"        ... và {len(thin_min) - 15} điểm khác")
    else:
        print(f"    OK — không có điểm nào dưới {MIN_WALL_MM}mm")

    if thin_warn:
        thin_warn.sort(key=lambda x: x[0])
        print(f"    ~ {len(thin_warn)} điểm trong dải cảnh báo [{MIN_WALL_MM},{WARN_WALL_MM})mm "
              f"(mỏng hơn thiết kế 1.2mm nhưng có thể vẫn in được):")
        for t, p in thin_warn[:8]:
            print(f"        {t:.3f}mm tại {p.round(2).tolist()}")
        if len(thin_warn) > 8:
            print(f"        ... và {len(thin_warn) - 8} điểm khác")

    if thin_min:
        print("\n    Gợi ý đọc kết quả: điểm nằm ở vành bán kính ~20.0-20.7mm gần đáy khay là")
        print("    'gờ kê' ledge_plate_t=1.0mm (mỏng CHỦ Ý theo constants.scad, không phải lỗi")
        print("    mới). Điểm ở z≈0 sát cổng ra (x≈17-20,y≈0) là mép cắt phẳng đáy hở CHỦ Ý")
        print("    của khay (xem đầu flow_tray_003.scad), không phải 1 bức thành. Điểm KHÁC")
        print("    2 vùng này mới đáng nghi — đối chiếu toạ độ với constants.scad thủ công.")

    print("\n== Kết luận ==")
    ok = len(bodies) == 1 and mesh.is_watertight and not thin_min
    print("PASS" if ok else "CẦN XEM LẠI — xem chi tiết ở trên")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
