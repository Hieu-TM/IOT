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

ASSUMPTION (unverified - needs a live workflow to confirm): predictions are returned
in the ORIGINAL image's coordinate space. If the workflow contains a resize/crop
block, coordinates may come back in the PROCESSED space while the dimensions used
here are the original, silently scaling every centroid and size_mm. Verify with
`python -m ml.infer.probe` against a real workflow before trusting measurements.
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


def response_entries(raw):
    """Normalise a workflow response into the per-image entry list.

    Roboflow serverless wraps results as {"outputs": [...], "profiler_trace": [...]}.
    Unwrapping `outputs` is what makes a configured predictions_key (the workflow's
    declared output name, e.g. "predictions") actually addressable - without it the
    whole envelope is treated as one entry and a correct key resolves nothing.
    Bare-list and bare-dict responses are still accepted.
    """
    if isinstance(raw, dict) and isinstance(raw.get("outputs"), list):
        return raw["outputs"]
    if isinstance(raw, list):
        return raw
    return [raw]


def response_image_dims(entry):
    """Return (width, height) reported by the workflow, or (None, None).

    Searched breadth-first because the image block's nesting depends on the
    workflow's own output names.
    """
    queue = [entry]
    while queue:
        node = queue.pop(0)
        if isinstance(node, dict):
            img = node.get("image")
            if isinstance(img, dict) and "width" in img and "height" in img:
                try:
                    return int(img["width"]), int(img["height"])
                except (TypeError, ValueError):
                    return None, None
            queue.extend(v for v in node.values() if isinstance(v, (dict, list)))
        elif isinstance(node, list):
            queue.extend(v for v in node if isinstance(v, (dict, list)))
    return None, None


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


def _to_detection(pred, image_width=None, image_height=None):
    """Convert one Roboflow prediction (CENTER x/y + size) to a Detection.

    Roboflow does not clamp boxes to the image, so an edge-touching particle can
    yield a negative top-left origin. The ingest schema declares bbox_x/bbox_y
    with ge=0 and validates the whole payload as a unit, so a single negative
    origin would reject the entire sample. Clamp to the image rectangle here.
    """
    cx, cy = float(pred["x"]), float(pred["y"])
    pw, ph = float(pred["width"]), float(pred["height"])
    x0, y0 = cx - pw / 2.0, cy - ph / 2.0
    x1, y1 = x0 + pw, y0 + ph
    x0, y0 = max(0.0, x0), max(0.0, y0)
    if image_width is not None:
        x1 = min(float(image_width), x1)
    if image_height is not None:
        y1 = min(float(image_height), y1)
    x, y = int(round(x0)), int(round(y0))
    w, h = int(round(x1)) - x, int(round(y1)) - y
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
                 timeout=30, retries=2, extra_inputs=None):
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
        self.extra_inputs = dict(extra_inputs or {})
        # Letting an extra input reuse the image key would silently replace the
        # image with a scalar and every frame would come back empty - a failure
        # that looks exactly like "clean water" in the audit log. Refuse instead.
        if self.image_input_name in self.extra_inputs:
            raise ValueError(
                f"roboflow.extra_inputs may not contain {self.image_input_name!r} - "
                "that key carries the image itself.")
        self.timeout = timeout
        self.retries = retries
        self._warned_no_predictions = False
        self._warned_bad_key = False
        self._warned_dims = False

    @property
    def url(self):
        return f"{self.endpoint}/{self.workspace}/workflows/{self.workflow_id}"

    def fetch_raw(self, image_bytes):
        """POST the image and return the parsed JSON response (used by the probe)."""
        inputs = {
            self.image_input_name: {
                "type": "base64",
                "value": base64.b64encode(image_bytes).decode("ascii"),
            }
        }
        inputs.update(self.extra_inputs)
        payload = {"api_key": self.api_key, "inputs": inputs}
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                resp = requests.post(self.url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                # Permanent client errors (bad api_key, unknown workflow) will not
                # fix themselves - fail fast rather than burn retries. 429 is the
                # exception: a rate limit IS worth backing off on.
                if status is not None and 400 <= status < 500 and status != 429:
                    raise
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.5 * (2 ** attempt))
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.5 * (2 ** attempt))
        raise last_error

    def run(self, image_bytes):
        # Dimensions come from decoding locally: the workflow response may not carry them.
        width, height = Image.open(BytesIO(image_bytes)).size
        raw = self.fetch_raw(image_bytes)
        entries = response_entries(raw)
        entry = entries[0] if entries else {}

        rw, rh = response_image_dims(entry)
        if rw and rh and (rw, rh) != (width, height) and not self._warned_dims:
            self._warned_dims = True
            print(f"[warn] workflow reports image {rw}x{rh} but the local image is "
                  f"{width}x{height}. Coordinates may be in a processed space; "
                  "every size_mm would be scaled wrong. Check the workflow for a "
                  "resize/crop block.")

        predictions = extract_predictions(entry, self.predictions_key)
        if not predictions and self.predictions_key:
            fallback = extract_predictions(entry, "")
            if fallback:
                if not self._warned_bad_key:
                    self._warned_bad_key = True
                    print(f"[warn] predictions_key={self.predictions_key!r} resolved 0 "
                          f"predictions but auto-detect found {len(fallback)}. Using "
                          "auto-detect. Fix roboflow.predictions_key "
                          "(run `python -m ml.infer.probe <image>`).")
                predictions = fallback
        if not predictions and entry:
            if not self._warned_no_predictions:
                self._warned_no_predictions = True
                print("[warn] no predictions resolved from the workflow response "
                      f"(predictions_key={self.predictions_key!r}). If the workflow "
                      "did detect something, run `python -m ml.infer.probe <image>` "
                      "to find the real output name and set roboflow.predictions_key.")
        detections = []
        for pred in predictions:
            try:
                detection = _to_detection(pred, width, height)
            except (KeyError, TypeError, ValueError):
                # The workflow's output shape is not guaranteed - one malformed
                # entry must not sink the whole frame.
                continue
            if detection.bbox_xywh[2] <= 0 or detection.bbox_xywh[3] <= 0:
                continue  # box lies entirely outside the image
            detections.append(detection)
        return DetectionResult(
            detections=detections,
            image_width=width,
            image_height=height,
        )

    def run_array(self, rgb_array, width=None, height=None):
        """Interface parity with Detector.run_array - encodes then delegates."""
        buf = BytesIO()
        Image.fromarray(rgb_array).save(buf, format="JPEG")
        return self.run(buf.getvalue())
