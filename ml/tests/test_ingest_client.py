import json

from ml.infer import ingest_client


class _Resp:
    def __init__(self, code, payload=None, text=""):
        self.status_code = code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _patch(monkeypatch, resp=None, exc=None):
    calls = {}

    def fake_post(url, files=None, data=None, timeout=None):
        calls["url"] = url
        calls["files"] = files
        calls["data"] = data
        if exc:
            raise exc
        return resp

    monkeypatch.setattr(ingest_client.requests, "post", fake_post)
    return calls


def test_post_created(monkeypatch):
    calls = _patch(monkeypatch, _Resp(201, {"status": "created"}))
    r = ingest_client.post("http://x", {"a": 1}, b"jpeg", "a.jpg")
    assert r.status == "created" and r.http_status == 201
    assert calls["url"] == "http://x/api/ingest"
    assert json.loads(calls["data"]["metadata"]) == {"a": 1}


def test_post_already_exists(monkeypatch):
    _patch(monkeypatch, _Resp(200, {"status": "already_exists"}))
    r = ingest_client.post("http://x/", {}, b"j", "a.jpg")
    assert r.status == "already_exists"


def test_post_validation_error(monkeypatch):
    _patch(monkeypatch, _Resp(422, {"detail": "bad"}))
    r = ingest_client.post("http://x", {}, b"j", "a.jpg")
    assert r.status == "failed" and r.http_status == 422 and "bad" in r.detail


def test_post_network_error(monkeypatch):
    _patch(monkeypatch, exc=ingest_client.requests.RequestException("boom"))
    r = ingest_client.post("http://x", {}, b"j", "a.jpg")
    assert r.status == "failed" and r.http_status == 0 and "boom" in r.detail
