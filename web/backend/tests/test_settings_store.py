"""settings_store — tham số VẬN HÀNH (đổi theo ca), tách khỏi ml/config.toml.

Ranh giới: ml/config.toml giữ thứ lập trình viên sửa (backend suy luận, API
key, weights); file này giữ thứ người vận hành sửa qua web (IP board, lô, chế
độ). Hai file, hai người dùng, không chồng lấn.
"""

import json

import pytest

from app.settings_store import DEFAULTS, SettingsError, load, save


def test_load_returns_defaults_when_file_absent(tmp_path):
    assert load(tmp_path / "settings.json") == DEFAULTS


def test_save_merges_and_persists(tmp_path):
    path = tmp_path / "settings.json"

    out = save({"station_host": "192.168.1.50"}, path)

    assert out["station_host"] == "192.168.1.50"
    assert out["mode"] == DEFAULTS["mode"]        # khoá không đụng tới giữ nguyên
    assert load(path)["station_host"] == "192.168.1.50"


def test_save_twice_keeps_earlier_keys(tmp_path):
    path = tmp_path / "settings.json"
    save({"station_host": "10.0.0.9"}, path)
    save({"mode": "measure"}, path)

    out = load(path)
    assert out["station_host"] == "10.0.0.9"
    assert out["mode"] == "measure"


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    # Người dùng sửa tay hỏng file, hoặc mất điện giữa lúc ghi. Dashboard phải
    # mở được để họ nhập lại — sập ở đây là mất luôn đường sửa.
    path = tmp_path / "settings.json"
    path.write_text("{ this is not json", encoding="utf-8")

    assert load(path) == DEFAULTS


def test_unknown_key_is_rejected(tmp_path):
    with pytest.raises(SettingsError) as exc:
        save({"nope": 1}, tmp_path / "settings.json")
    assert "nope" in str(exc.value)


def test_invalid_mode_is_rejected(tmp_path):
    with pytest.raises(SettingsError):
        save({"mode": "turbo"}, tmp_path / "settings.json")


def test_negative_px_per_mm_is_rejected(tmp_path):
    # px_per_mm <= 0 chảy thẳng vào size_mm của mọi hạt — sai lặng lẽ.
    with pytest.raises(SettingsError):
        save({"px_per_mm": -3}, tmp_path / "settings.json")


def test_px_per_mm_can_be_cleared_to_none(tmp_path):
    path = tmp_path / "settings.json"
    save({"px_per_mm": 14.0}, path)
    assert save({"px_per_mm": None}, path)["px_per_mm"] is None


def test_capture_delay_out_of_range_is_rejected(tmp_path):
    with pytest.raises(SettingsError):
        save({"capture_delay_ms": -1}, tmp_path / "settings.json")
    with pytest.raises(SettingsError):
        save({"capture_delay_ms": 60001}, tmp_path / "settings.json")


def test_station_host_rejects_url_with_path(tmp_path):
    # Host là host, không phải URL tuỳ ý: /api/station/control ghép nó thành
    # địa chỉ để gọi, nên nhận cả path/query là mở đường bắn request đi đâu tuỳ.
    with pytest.raises(SettingsError):
        save({"station_host": "evil.example.com/x?y=1"}, tmp_path / "settings.json")


def test_station_host_accepts_ip_hostname_and_port(tmp_path):
    path = tmp_path / "settings.json"
    for host in ("192.168.1.50", "aqua-scope.local", "192.168.1.50:8080"):
        assert save({"station_host": host}, path)["station_host"] == host


def test_station_host_is_trimmed(tmp_path):
    path = tmp_path / "settings.json"
    assert save({"station_host": "  10.0.0.9  "}, path)["station_host"] == "10.0.0.9"


def test_written_file_is_valid_json(tmp_path):
    path = tmp_path / "settings.json"
    save({"batch_lot": "LOT-001"}, path)
    assert json.loads(path.read_text(encoding="utf-8"))["batch_lot"] == "LOT-001"
