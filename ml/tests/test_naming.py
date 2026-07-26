from ml.infer.naming import (
    sample_code_from_filename,
    resolve_px_per_mm,
    DEFAULT_PX_PER_MM,
)


def test_sample_code_strips_unsafe_chars():
    assert sample_code_from_filename("my photo (1).JPG") == "my-photo--1"


def test_sample_code_handles_path_and_traversal():
    assert sample_code_from_filename("../../etc/passwd.png") == "passwd"


def test_sample_code_truncates_to_64():
    long_name = "a" * 100 + ".jpg"
    assert len(sample_code_from_filename(long_name)) == 64


def test_sample_code_never_empty():
    assert sample_code_from_filename("---.jpg") == "sample"


def test_resolve_px_per_mm_default():
    assert resolve_px_per_mm(None) == (DEFAULT_PX_PER_MM, True)


def test_resolve_px_per_mm_explicit():
    assert resolve_px_per_mm(20.0) == (20.0, False)


def test_resolve_px_per_mm_rejects_non_positive():
    assert resolve_px_per_mm(0) == (DEFAULT_PX_PER_MM, True)
    assert resolve_px_per_mm(-5) == (DEFAULT_PX_PER_MM, True)


from datetime import datetime, timezone

from ml.infer.naming import station_sample_code, unique_station_sample_code


def test_station_sample_code_format():
    dt = datetime(2026, 7, 26, 9, 5, 3, 456000, tzinfo=timezone.utc)
    assert station_sample_code(dt) == "S20260726-090503-456"


def test_unique_station_sample_code_suffixes_on_collision():
    # QUAN TRỌNG: ingest coi sample_code trùng là một bản RETRY và trả
    # already_exists KHÔNG báo lỗi. Hai khung trùng mã thì khung thứ hai biến
    # mất khỏi sổ audit mà không ai biết. Độ phân giải mili-giây của đồng hồ
    # KHÔNG đủ đảm bảo khác nhau, nên phải chống trùng bằng cấu trúc dữ liệu.
    dt = datetime(2026, 7, 26, 9, 5, 3, 456000, tzinfo=timezone.utc)
    used = set()

    a = unique_station_sample_code(dt, used)
    b = unique_station_sample_code(dt, used)
    c = unique_station_sample_code(dt, used)

    assert a == "S20260726-090503-456"
    assert b == "S20260726-090503-456-2"
    assert c == "S20260726-090503-456-3"
    assert used == {a, b, c}


def test_unique_station_sample_code_stays_ingest_safe():
    dt = datetime(2026, 7, 26, 9, 5, 3, 456000, tzinfo=timezone.utc)
    used = set()
    for _ in range(12):
        code = unique_station_sample_code(dt, used)
        assert 1 <= len(code) <= 64
        assert all(ch.isalnum() or ch in "._-" for ch in code)
