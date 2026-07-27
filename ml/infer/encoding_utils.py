"""Ép stdout/stderr sang UTF-8 trước khi in bất cứ gì có dấu.

QUYẾT ĐỊNH: NHÂN BẢN (không import chéo từ dataset_collector/collect_dataset.py,
nơi hàm này được viết lần đầu). ml/ và dataset_collector/ là hai công cụ độc
lập có chủ đích (mỗi bên có README riêng, không phụ thuộc lẫn nhau) - import
chéo sẽ biến một hàm 10 dòng thành một coupling thật giữa hai package, đổi lại
chẳng tiết kiệm được gì đáng kể. Nếu cách xử lý này đổi, sửa cả hai chỗ.
"""

import sys


def force_utf8_output() -> None:
    """Ép stdout/stderr sang UTF-8.

    Console Windows mặc định là cp1252, không mã hóa được tiếng Việt: các
    thông báo lỗi có dấu (StationError, v.v.) sẽ làm print() ném
    UnicodeEncodeError và che mất thông báo lỗi thật sau một traceback khó
    đọc. Gọi hàm này đầu main() để mọi print() sau đó an toàn.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass  # stream đã bị thay thế/đóng - không đáng để chết vì chuyện này
