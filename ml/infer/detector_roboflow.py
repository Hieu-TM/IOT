"""Direction 2 - Roboflow hosted WORKFLOW inference. Same contract as detector.Detector.

Why this exists: Roboflow's free tier does not let you download the TRAINED WEIGHTS
of a model trained on their platform, only run it. This backend needs no local
weights and no ultralytics - but it needs the network plus an API key, and it CANNOT
be exported to TFLite/on-chip. That is Direction 1's job.

Endpoint shape (a Workflow, not the simple detect API):
    POST {endpoint}/{workspace}/workflows/{workflow_id}
    {"api_key": ..., "inputs": {"<image_input_name>": {"type": "base64", "value": ...}}}

The response is a LIST (one entry per input image); each entry is a dict keyed by the
WORKFLOW'S OWN output names - there is no guaranteed "predictions" key, and the names
change per workflow. So predictions are located via the configured `predictions_key`
(dotted paths supported) or auto-detected. Nothing about a specific workspace,
workflow, or output name is hard-coded here.

Run `python -m ml.infer.probe <image>` once you have credentials to print the real
response structure, then pin roboflow.predictions_key in ml/config.toml.
"""

import base64
import time
from io import BytesIO

import requests
from PIL import Image

from .detector import Detection, DetectionResult

# A prediction dict is recognised by carrying a full bbox, whatever it is nested under.
_BBOX_KEYS = ("x", "y", "width", "height")


def _looks_like_predictions(value):
    return (isinstance(value, list) and value
            and isinstance(value[0], dict)
            and all(k in value[0] for k in _BBOX_KEYS))


def _dig(node, dotted):
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def extract_predictions(entry, predictions_key=""):
    """Locate the list of prediction dicts inside ONE workflow output entry.

    With `predictions_key` set, read exactly that path (and unwrap a nested
    "predictions" list if the path lands on a dict). With it empty, search
    breadth-first so the shallowest bbox-shaped list wins.
    """
    if predictions_key:
        node = _dig(entry, predictions_key)
        if isinstance(node, dict):
            node = node.get("predictions")
        return node if _looks_like_predictions(node) else []

    queue = [entry]
    while queue:
        node = queue.pop(0)
        if _looks_like_predictions(node):
            return node
        if isinstance(node, dict):
            queue.extend(v for v in node.values() if isinstance(v, (dict, list)))
        elif isinstance(node, list):
            queue.extend(v for v in node if isinstance(v, (dict, list)))
    return []


def _to_detection(pred):
    w = int(round(float(pred["width"])))
    h = int(round(float(pred["height"])))
    # Roboflow gives the bbox CENTER; Detection.bbox_xywh is TOP-LEFT.
    x = int(round(float(pred["x"]) - w / 2))
    y = int(round(float(pred["y"]) - h / 2))
    return Detection(
        bbox_xywh=(x, y, w, h),
        class_name=str(pred.get("class") or pred.get("class_name") or "unknown"),
        confidence=float(pred.get("confidence", 0.0)),
    )


def _describe(value):
    if isinstance(value, str):
        if len(value) > 200:
            return f"<blob elided, {len(value)} chars>"
        return f"str({value!r})"
    if isinstance(value, bool):
        return f"bool({value})"
    if isinstance(value, (int, float)):
        return f"{type(value).__name__}({value})"
    if isinstance(value, list):
        return f"list(len={len(value)})"
    if isinstance(value, dict):
        return f"dict(keys={list(value.keys())})"
    return type(value).__name__


def summarize_response(value, depth=0, max_depth=4):
    """Render a response's STRUCTURE (key names, types, lengths).

    Never emits raw values longer than 200 chars - workflow outputs can carry
    base64 images of hundreds of KB, which must not be logged.
    """
    pad = "  " * depth
    if isinstance(value, dict):
        if depth >= max_depth:
            return f"{pad}dict(keys={list(value.keys())})"
        parts = []
        for key, sub in value.items():
            parts.append(f"{pad}{key}: {_describe(sub)}")
            if isinstance(sub, (dict, list)) and sub:
                parts.append(summarize_response(sub, depth + 1, max_depth))
        return "\n".join(parts)
    if isinstance(value, list):
        if not value:
            return f"{pad}(empty list)"
        head = value[0]
        out = f"{pad}[0] {_describe(head)}"
        if isinstance(head, (dict, list)) and depth < max_depth:
            out += "\n" + summarize_response(head, depth + 1, max_depth)
        return out
    return f"{pad}{_describe(value)}"


class RoboflowWorkflowDetector:
    def __init__(self, api_key, workspace, workflow_id,
                 endpoint="https://serverless.roboflow.com",
                 image_input_name="image", predictions_key="",
                 timeout=30, retries=2):
        if not api_key:
            raise ValueError(
                "roboflow.api_key is required - set it in ml/config.local.toml "
                "or AQUA_ROBOFLOW_API_KEY")
        if not workspace:
            raise ValueError("roboflow.workspace is required")
        if not workflow_id:
            raise ValueError("roboflow.workflow_id is required")
        self.api_key = api_key
        self.workspace = workspace
        self.workflow_id = workflow_id
        self.endpoint = str(endpoint).rstrip("/")
        self.image_input_name = image_input_name or "image"
        self.predictions_key = predictions_key or ""
        self.timeout = timeout
        self.retries = retries

    @property
    def url(self):
        return f"{self.endpoint}/{self.workspace}/workflows/{self.workflow_id}"

    def fetch_raw(self, image_bytes):
        """POST the image and return the parsed JSON response (used by the probe)."""
        payload = {
            "api_key": self.api_key,
            "inputs": {
                self.image_input_name: {
                    "type": "base64",
                    "value": base64.b64encode(image_bytes).decode("ascii"),
                }
            },
        }
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                resp = requests.post(self.url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.5 * (2 ** attempt))  # backoff
        raise last_error

    def run(self, image_bytes):
        # Dimensions come from decoding locally: the workflow response may not carry them.
        width, height = Image.open(BytesIO(image_bytes)).size
        raw = self.fetch_raw(image_bytes)
        entries = raw if isinstance(raw, list) else [raw]
        entry = entries[0] if entries else {}
        predictions = extract_predictions(entry, self.predictions_key)
        return DetectionResult(
            detections=[_to_detection(p) for p in predictions],
            image_width=width,
            image_height=height,
        )

    def run_array(self, rgb_array, width=None, height=None):
        """Interface parity with Detector.run_array - encodes then delegates."""
        buf = BytesIO()
        Image.fromarray(rgb_array).save(buf, format="JPEG")
        return self.run(buf.getvalue())
