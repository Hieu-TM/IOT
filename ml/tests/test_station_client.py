"""StationClient — tầng nói chuyện HTTP với board, tách khỏi vòng đếm khung.

Vì sao cần tách: Esp32CaptureSource trộn "cách nói chuyện với board" vào
"vòng lặp chụp N khung", nên không có cách nào lấy MỘT khung theo yêu cầu —
đó chính là lý do runner trên web không dùng lại được nó.
"""

import pytest

from ml.infer.station import StationClient, StationError
from ml.tests.fake_board import DEVICE_JSON, FakeBoard, jpeg_bytes


def test_read_device_returns_board_identity():
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(board.host)
        info = client.read_device()

    assert info["device_id"] == "aqua-cam-a1b2c3"
    assert info["pump"]["phase"] == "SETTLING"


def test_capture_once_returns_jpeg_bytes():
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        body = StationClient(board.host).capture_once()

    assert body[:2] == b"\xff\xd8"
    assert body.rstrip()[-2:] == b"\xff\xd9"


def test_html_with_http_200_is_rejected():
    # Captive portal của router trả HTML kèm HTTP 200. Đẩy HTML vào detector
    # sẽ ra lỗi khó hiểu ở tận cuối pipeline, nên phải chặn ngay đây.
    with FakeBoard([("html200", None)],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(board.host, retries=2)
        with pytest.raises(StationError):
            client.capture_once()
        assert board.capture_hits == 2   # đã thử lại đủ số lần


def test_truncated_jpeg_is_rejected():
    with FakeBoard([("jpeg_truncated", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(board.host, retries=2)
        with pytest.raises(StationError):
            client.capture_once()
        assert board.capture_hits == 2


def test_capture_retries_then_gives_up_on_503():
    with FakeBoard([("503", None)],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(board.host, retries=3)
        with pytest.raises(StationError):
            client.capture_once()
        assert board.capture_hits == 3


def test_capture_succeeds_after_one_failure():
    with FakeBoard([("503", None), ("jpeg", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        body = StationClient(board.host, retries=2).capture_once()

    assert body[:2] == b"\xff\xd8"


def test_device_json_not_an_object_raises_without_retrying():
    # JSON hợp lệ nhưng SAI HÌNH DẠNG không phải lỗi thoáng qua — firmware trả
    # sai thì thử lại không giúp gì.
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", [1, 2, 3])) as board:
        with pytest.raises(StationError) as exc:
            StationClient(board.host, retries=3).read_device()
    assert "không phải object" in str(exc.value)


def test_unreachable_board_raises_station_error():
    with pytest.raises(StationError) as exc:
        StationClient("127.0.0.1:1", timeout_s=1, retries=1).read_device()
    assert "/device" in str(exc.value)


def test_device_id_property_reads_lazily_and_caches():
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(board.host)
        assert client.device_id == "aqua-cam-a1b2c3"
        assert client.device_id == "aqua-cam-a1b2c3"   # lần 2 lấy từ cache


def test_device_id_is_none_when_firmware_omits_it():
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", {"firmware": "x"})) as board:
        assert StationClient(board.host).device_id is None


def test_host_with_scheme_is_accepted():
    with FakeBoard([("jpeg", jpeg_bytes())],
                   device_response=("json", DEVICE_JSON)) as board:
        client = StationClient(f"http://{board.host}")
        assert client.base_url == f"http://{board.host}"
        assert client.read_device()["device_id"] == "aqua-cam-a1b2c3"
