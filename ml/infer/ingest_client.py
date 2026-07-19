"""POST one measurement to the web backend's /api/ingest contract.

Builds the multipart form the endpoint expects (a `metadata` JSON string field
+ an `image` file) and classifies the response. Never raises on HTTP/network
failure — returns a `failed` IngestResult so the CLI can tally and continue.
"""

import json
from dataclasses import dataclass

import requests


@dataclass
class IngestResult:
    status: str        # "created" | "already_exists" | "failed"
    http_status: int
    detail: str = ""


def post(api_url, metadata, image_bytes, image_name, timeout=30):
    url = api_url.rstrip("/") + "/api/ingest"
    files = {"image": (image_name, image_bytes, "image/jpeg")}
    data = {"metadata": json.dumps(metadata)}
    try:
        resp = requests.post(url, files=files, data=data, timeout=timeout)
    except requests.RequestException as exc:
        return IngestResult(status="failed", http_status=0, detail=str(exc))

    if resp.status_code == 201:
        return IngestResult(status="created", http_status=201)
    if resp.status_code == 200:
        return IngestResult(status="already_exists", http_status=200)
    return IngestResult(
        status="failed", http_status=resp.status_code, detail=_safe_detail(resp)
    )


def _safe_detail(resp):
    try:
        return json.dumps(resp.json())
    except ValueError:
        return resp.text[:500]
