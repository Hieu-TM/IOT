import importlib.util
from pathlib import Path


_HELPER = Path(__file__).resolve().parents[2] / "auto_detect_board.py"
_SPEC = importlib.util.spec_from_file_location("auto_detect_board", _HELPER)
auto_detect_board = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(auto_detect_board)


def test_parse_ip_from_ready_line():
    text = "San sang. Web UI:  http://192.168.1.50/\n"

    assert auto_detect_board.parse_ip_from_text(text) == "192.168.1.50"


def test_parse_ip_from_status_line():
    text = "[WiFi] OK | IP=10.10.0.23 | RSSI=-55 dBm | chup=7\n"

    assert auto_detect_board.parse_ip_from_text(text) == "10.10.0.23"


def test_parse_ip_skips_loopback_and_link_local():
    text = "debug 127.0.0.1 then 169.254.1.2 then IP: 192.168.4.1\n"

    assert auto_detect_board.parse_ip_from_text(text) == "192.168.4.1"
