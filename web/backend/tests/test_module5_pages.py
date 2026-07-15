"""Module 5 acceptance test — the server-rendered dashboard pages.

Mirrors test_module3_read_api's setup (StaticPool in-memory SQLite seeded
directly, get_session overridden), but mounts the *pages* router and asserts on
rendered HTML rather than JSON. Run from web/backend/:  pytest -q

Covers the four routes (/, /history, /samples/{id}, /stream) plus the missing-
sample 404, and guards two hardening fixes:
  * stored-XSS via a free-form particle `label` embedded in the overlay's
    <script type="application/json"> block (must be \\uXXXX-escaped, no
    </script> breakout);
  * mobile navigation (the sidebar is hidden ≤900px, so a .mobile-nav strip
    must carry the same links).
"""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.models import Particle, Sample
from app.routers.pages import router

XSS_LABEL = "</script><img src=x onerror=alert(1)>"


def _mk_particle(blob_index, size_mm, label):
    return Particle(
        blob_index=blob_index,
        centroid_x=100.0 + blob_index,
        centroid_y=50.0 + blob_index,
        bbox_x=90,
        bbox_y=40,
        bbox_w=20,
        bbox_h=20,
        area_px=size_mm * 100.0,
        size_mm=size_mm,
        label=label,
        confidence=0.9,
    )


def _make_client(seed=True):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    if seed:
        with Session(engine) as s:
            # captured_at = now (naive-UTC) so this is the "latest" sample.
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            sample = Sample(
                sample_code="S-PAGE-1",
                batch_lot="LOT-A",
                device_id="aquascope-01",
                captured_at=now,
                particle_count=2,
                image_path="images/S-PAGE-1.jpg",
                image_width=640,
                image_height=480,
                px_per_mm=14.0,
                raw_metadata_json='{"sample_code":"S-PAGE-1"}',
            )
            s.add(sample)
            s.commit()
            s.refresh(sample)
            parts = [
                _mk_particle(0, 1.2, "plastic"),
                _mk_particle(1, 2.4, XSS_LABEL),  # malicious free-form label
            ]
            for p in parts:
                p.sample_id = sample.id
            s.add_all(parts)
            s.commit()

    app = FastAPI()
    app.include_router(router)

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    return TestClient(app)


@pytest.fixture
def client():
    with _make_client(seed=True) as c:
        yield c


def _first_sample_id(client):
    # /history links each row to /samples/{id}; scrape the id from the HTML.
    import re

    html = client.get("/history").text
    m = re.search(r"/samples/(\d+)", html)
    assert m, "history page should link to at least one sample"
    return int(m.group(1))


def test_all_pages_render_ok(client):
    for path in ["/", "/history", "/stream"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert "text/html" in r.headers["content-type"]
    sid = _first_sample_id(client)
    assert client.get(f"/samples/{sid}").status_code == 200


def test_missing_sample_returns_404(client):
    r = client.get("/samples/999999")
    assert r.status_code == 404
    assert "Không tìm thấy mẫu" in r.text


def test_empty_dashboard_renders_empty_state():
    with _make_client(seed=False) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "Chưa có mẫu nào" in r.text


def test_particle_label_cannot_break_out_of_script(client):
    """XSS regression: a label containing '</script>' must not appear verbatim
    (that would close the JSON <script> block and inject the <img onerror>).
    It must be \\uXXXX-escaped instead, and still round-trip as JSON data."""
    sid = _first_sample_id(client)
    html = client.get(f"/samples/{sid}").text
    assert XSS_LABEL not in html  # no raw breakout
    assert "<img src=x onerror" not in html  # injected markup never materializes
    assert "\\u003c/script\\u003e" in html  # escaped, so JSON.parse restores it


def test_mobile_nav_present_on_every_page(client):
    """The sidebar is display:none ≤900px; the .mobile-nav strip must carry the
    same three destinations so navigation survives on phones."""
    for path in ["/", "/history", "/stream"]:
        html = client.get(path).text
        assert "mobile-nav" in html, path
        assert 'class="mnav-link' in html, path
        for href in ('href="/"', 'href="/history"', 'href="/stream"'):
            assert href in html, f"{path} missing {href}"
