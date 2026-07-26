"""Board / detector / poster / đồng hồ giả cho test của Runner.

Dùng chung bởi test_runner.py (máy trạng thái) và test_runner_thread.py (vòng
đời thread) — hai góc nhìn của cùng một đối tượng, cùng một bộ đồ giả.
"""


class FakeDetection:
    def __init__(self, label="fragment"):
        self.bbox_xywh = (10, 20, 30, 40)
        self.class_name = label
        self.confidence = 0.9


class FakeResult:
    def __init__(self, n=2):
        self.detections = [FakeDetection() for _ in range(n)]
        self.image_width = 1600
        self.image_height = 1200


class FakeDetector:
    def __init__(self, n=2, raises=False):
        self.n = n
        self.raises = raises
        self.calls = 0

    def run(self, image_bytes):
        self.calls += 1
        if self.raises:
            raise RuntimeError("detector nổ")
        return FakeResult(self.n)


class FakeStation:
    """Board giả ở mức đối tượng: test tự lái pha bơm qua .phase."""

    def __init__(self, phase="FILLING", auto=True, aec=0, agc=0, settle_ms=2000):
        self.phase = phase
        self.auto = auto
        self.aec = aec
        self.agc = agc
        self.settle_ms = settle_ms
        self.device_error = None
        self.capture_error = None
        self.captures = 0
        self.device_id = "aqua-cam-test"

    def read_device(self):
        if self.device_error:
            raise self.device_error
        return {
            "device_id": self.device_id,
            "firmware": "aqua_scope_station/1.0.0",
            "camera": {"aec": self.aec, "agc": self.agc,
                       "width": 1600, "height": 1200},
            "pump": {"auto": self.auto, "phase": self.phase, "pwm_ready": True,
                     "settle_ms": self.settle_ms, "cycle_count": 1},
        }

    def capture_once(self):
        if self.capture_error:
            raise self.capture_error
        self.captures += 1
        return b"\xff\xd8fake-jpeg\xff\xd9"


class FakePoster:
    class Result:
        def __init__(self, status="created"):
            self.status = status
            self.http_status = 201
            self.detail = ""

    def __init__(self, status="created"):
        self.status = status
        self.calls = []

    def __call__(self, api_url, metadata, image_bytes, image_name):
        self.calls.append((api_url, metadata, image_bytes, image_name))
        return self.Result(self.status)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds
