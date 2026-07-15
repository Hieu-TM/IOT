import io
import os

import pytest


WEIGHTS = os.environ.get("AQUA_TEST_WEIGHTS", "ml/models/best.pt")


@pytest.mark.skipif(not os.path.exists(WEIGHTS), reason="no weights at ml/models/best.pt")
def test_detector_runs_on_blank_image():
    pytest.importorskip("ultralytics")
    from PIL import Image

    from ml.infer.detector import Detector, DetectionResult

    buf = io.BytesIO()
    Image.new("RGB", (320, 320), (128, 128, 128)).save(buf, format="JPEG")

    result = Detector(WEIGHTS).run(buf.getvalue())

    assert isinstance(result, DetectionResult)
    assert result.image_width == 320 and result.image_height == 320
    for d in result.detections:
        assert len(d.bbox_xywh) == 4
        assert 0.0 <= d.confidence <= 1.0
