"""Hợp đồng API điều khiển. Không đụng board thật, không đụng thread thật:
Runner giả tiêm qua dependency override.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import control
from app.runner import RunnerBusy, RunnerConfigError


class FakeRunner:
    def __init__(self):
        self.started = []
        self.stopped = 0
        self.start_error = None
        self.snap = {"running": False, "mode": None, "station_host": "",
                     "device": None, "phase": None,
                     "counters": {"cycles": 0, "captured": 0, "written": 0, "failed": 0},
                     "last": None, "error": None, "warnings": [], "has_preview": False}
        self._preview = None
        self.kept = 0

    def start(self, cfg, **kw):
        if self.start_error:
            raise self.start_error
        self.started.append(cfg)
        self.snap["running"] = True
        self.snap["mode"] = cfg.mode

    def stop(self):
        self.stopped += 1
        self.snap["running"] = False

    def snapshot(self):
        return dict(self.snap)

    def preview_jpeg(self):
        return self._preview

    def keep(self):
        if self._preview is None:
            raise RuntimeError("chưa có khung nào để lưu.")
        self.kept += 1
        return {"sample_code": "S-PREVIEW-1", "written": True}


@pytest.fixture
def runner():
    return FakeRunner()


@pytest.fixture
def client(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(control.settings_store, "SETTINGS_PATH",
                        tmp_path / "settings.json")
    app = FastAPI()
    app.include_router(control.router)
    app.dependency_overrides[control.get_runner] = lambda: runner
    return TestClient(app)


def test_status_returns_the_snapshot(client):
    r = client.get("/api/runner/status")
    assert r.status_code == 200
    assert r.json()["running"] is False
    assert r.json()["counters"]["written"] == 0


def test_start_measure_passes_mode_through(client, runner):
    client.post("/api/settings", json={"station_host": "192.168.1.50"})

    r = client.post("/api/runner/start", json={"mode": "measure"})

    assert r.status_code == 200
    assert runner.started[0].mode == "measure"
    assert runner.started[0].station_host == "192.168.1.50"


def test_start_without_host_is_400(client, runner):
    runner.start_error = RunnerConfigError("chưa có địa chỉ board.")
    r = client.post("/api/runner/start", json={"mode": "preview"})
    assert r.status_code == 400
    assert "board" in r.json()["detail"]


def test_start_while_running_is_409(client, runner):
    runner.start_error = RunnerBusy("runner đang chạy rồi.")
    r = client.post("/api/runner/start", json={"mode": "preview"})
    assert r.status_code == 409


def test_start_rejects_unknown_mode(client):
    r = client.post("/api/runner/start", json={"mode": "turbo"})
    assert r.status_code == 422


def test_stop_is_idempotent(client, runner):
    assert client.post("/api/runner/stop").status_code == 200
    assert client.post("/api/runner/stop").status_code == 200
    assert runner.stopped == 2


def test_preview_404_when_no_frame_yet(client):
    assert client.get("/api/runner/preview.jpg").status_code == 404


def test_preview_returns_jpeg_bytes(client, runner):
    runner._preview = b"\xff\xd8fake\xff\xd9"
    r = client.get("/api/runner/preview.jpg")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content == b"\xff\xd8fake\xff\xd9"


def test_keep_without_frame_is_409(client):
    assert client.post("/api/runner/keep").status_code == 409


def test_keep_writes_the_frame(client, runner):
    runner._preview = b"\xff\xd8fake\xff\xd9"
    r = client.post("/api/runner/keep")
    assert r.status_code == 200
    assert r.json()["sample_code"] == "S-PREVIEW-1"
    assert runner.kept == 1


def test_settings_roundtrip(client):
    client.post("/api/settings", json={"batch_lot": "LOT-9"})
    assert client.get("/api/settings").json()["batch_lot"] == "LOT-9"


def test_settings_rejects_bad_value_with_400(client):
    r = client.post("/api/settings", json={"capture_delay_ms": -5})
    assert r.status_code == 400
    assert "capture_delay_ms" in r.json()["detail"]


def test_settings_body_fields_match_settings_store_defaults():
    # Drift alarm: SettingsBody and settings_store.DEFAULTS are two
    # independent declarations of the same key set (see the module
    # docstrings). Nothing enforces they stay in sync except this test - if
    # someone adds a key to one and forgets the other, this is the thing that
    # notices instead of a silent 422/dropped-field bug reaching the operator.
    from app import settings_store

    assert set(control.SettingsBody.model_fields) == set(settings_store.DEFAULTS)


def test_control_rejects_var_outside_allowlist(client, monkeypatch):
    # Không allowlist thì đây là proxy mở: ai trong LAN cũng bắn được tham số
    # tuỳ ý vào firmware.
    called = []
    monkeypatch.setattr(control, "_board_get", lambda url, timeout=5: called.append(url))

    r = client.post("/api/station/control", json={"var": "framesize", "val": "13"})

    assert r.status_code == 400
    assert called == [], "không được gửi request nào tới board"


def test_control_forwards_allowed_var(client, monkeypatch):
    client.post("/api/settings", json={"station_host": "192.168.1.50"})
    called = []
    monkeypatch.setattr(control, "_board_get",
                        lambda url, timeout=5: called.append(url) or "OK")

    r = client.post("/api/station/control", json={"var": "darkmode", "val": "1"})

    assert r.status_code == 200
    assert called == ["http://192.168.1.50/control?var=darkmode&val=1"]


def test_control_without_configured_host_is_400(client, monkeypatch):
    monkeypatch.setattr(control, "_board_get", lambda url, timeout=5: "OK")
    r = client.post("/api/station/control", json={"var": "darkmode", "val": "1"})
    assert r.status_code == 400


def test_control_rejects_unsafe_val(client, monkeypatch):
    client.post("/api/settings", json={"station_host": "192.168.1.50"})
    called = []
    monkeypatch.setattr(control, "_board_get", lambda url, timeout=5: called.append(url))

    r = client.post("/api/station/control",
                    json={"var": "device_id", "val": "a&var=reset&val=1"})

    assert r.status_code == 422
    assert called == []


def test_probe_rejects_a_url_shaped_host(client, monkeypatch):
    monkeypatch.setattr(control, "_probe_host", lambda host: {"device_id": "x"})
    r = client.get("/api/station/probe", params={"host": "evil.example.com/x?y=1"})
    assert r.status_code == 400


def test_probe_returns_device_json(client, monkeypatch):
    monkeypatch.setattr(control, "_probe_host",
                        lambda host: {"device_id": "aqua-cam-1", "_host": host})
    r = client.get("/api/station/probe", params={"host": "aqua-scope.local"})
    assert r.status_code == 200
    assert r.json()["device_id"] == "aqua-cam-1"


def test_probe_unreachable_board_is_502(client, monkeypatch):
    def boom(host):
        raise RuntimeError("không tới được")

    monkeypatch.setattr(control, "_probe_host", boom)
    r = client.get("/api/station/probe", params={"host": "10.0.0.7"})
    assert r.status_code == 502
