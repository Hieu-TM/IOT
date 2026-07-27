"""Kiểm tra giao diện web nhúng trong firmware (index_ov2640.h / index_ov3660.h).

Hai file này là HTML+JS nằm trong header C, không có trình biên dịch nào soi
được: gõ sai một ID thì firmware vẫn compile sạch, vẫn nạp được, chỉ tới lúc
bấm nút mới phát hiện im ru. Các test này bắt đúng loại lỗi đó.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FIRMWARE_DIR = Path(__file__).resolve().parent.parent / "firmware"
INDEX_FILES = ["index_ov2640.h", "index_ov3660.h"]


def read_index(name: str) -> str:
    return (FIRMWARE_DIR / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", INDEX_FILES)
def test_every_getelementbyid_has_a_matching_html_id(name):
    """Mọi ID mà JS đi tìm đều phải tồn tại trong HTML."""
    text = read_index(name)

    html_ids = set(re.findall(r'\bid="([^"]+)"', text))
    js_ids = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", text))

    missing = js_ids - html_ids
    assert not missing, f"{name}: JS tìm ID không có trong HTML: {sorted(missing)}"


@pytest.mark.parametrize("name", INDEX_FILES)
def test_dataset_controls_are_present(name):
    """Bộ điều khiển thu dataset phải có đủ ở CẢ HAI giao diện.

    Giao diện được chọn theo sensor phát hiện lúc chạy. Chỉ thêm vào một file
    thì gặp board sensor khác là mất nút, mà lúc compile không hề báo gì.
    """
    text = read_index(name)

    for element_id in ["dataset-shot", "dataset-status", "dataset_host", "dataset_burst"]:
        assert f'id="{element_id}"' in text, f"{name}: thiếu phần tử #{element_id}"

    assert "/upload" in text, f"{name}: thiếu lời gọi POST /upload"
    assert "aquaDatasetHost" in text, f"{name}: không nhớ địa chỉ PC trong localStorage"


@pytest.mark.parametrize("name", INDEX_FILES)
def test_capture_url_is_cache_busted(name):
    """Thiếu cache-bust thì trình duyệt trả lại ảnh cũ trong cache.

    Dataset sẽ đầy ảnh trùng nhau mà nhìn log vẫn tưởng đang chụp mới — kiểu
    hỏng âm thầm, tới lúc train mới biết.
    """
    text = read_index(name)
    # Chỉ những chuỗi BẮT ĐẦU bằng ${baseHost}/capture mới thực sự là URL;
    # chuỗi tooltip cũng chứa "/capture" nhưng không phải lời gọi.
    capture_urls = re.findall(r"`\$\{baseHost\}/capture[^`]*`", text)

    assert capture_urls, f"{name}: không thấy lời gọi /capture nào"
    for url in capture_urls:
        assert "_cb=" in url, f"{name}: /capture thiếu cache-bust: {url}"


def test_both_indexes_share_the_same_dataset_logic():
    """Hai file phải cùng một logic — lệch nhau là nguồn bug về sau."""
    blocks = []
    for name in INDEX_FILES:
        text = read_index(name)
        start = text.index("// === THU DATASET")
        end = text.index("// Che do buong toi:", start)
        blocks.append(text[start:end])

    assert blocks[0] == blocks[1], "khối JS thu dataset ở 2 file index đã lệch nhau"
