import numpy as np
import pytest

from ml.infer.detector import Detection


def test_annotate_frame_draws_without_error():
    pytest.importorskip("cv2")
    from ml.infer.preview import annotate_frame

    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    out = annotate_frame(frame, [Detection((5, 5, 10, 10), "film", 0.7)])

    assert out.shape == (64, 64, 3)
    assert out.sum() > 0  # boxes/labels were drawn onto the black frame


def test_preview_never_imports_ingest_client():
    import ml.infer.preview as preview
    import inspect

    src = inspect.getsource(preview)
    assert "ingest_client" not in src
