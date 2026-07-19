import numpy as np

from ml.infer.detector import Detector, DetectionResult, Detection, _class_name


def test_class_name_dict_lookup():
    assert _class_name({0: "fiber", 1: "film"}, 1) == "film"


def test_class_name_list_lookup():
    assert _class_name(["fiber", "film"], 0) == "fiber"


def test_class_name_missing_key_falls_back_to_str():
    assert _class_name({0: "fiber"}, 5) == "5"


def test_class_name_out_of_range_falls_back_to_str():
    assert _class_name(["fiber"], 3) == "3"


def test_class_name_none_names_falls_back_to_str():
    assert _class_name(None, 2) == "2"


class _Cell:
    def __init__(self, v):
        self._v = v

    def tolist(self):
        return self._v

    def item(self):
        return self._v


class _Box:
    def __init__(self, xyxy, cls, conf):
        self.xyxy = [_Cell(xyxy)]
        self.cls = [_Cell(cls)]
        self.conf = [_Cell(conf)]


class _Result:
    def __init__(self, boxes):
        self.boxes = boxes


class _FakeModel:
    names = {0: "fiber", 1: "film"}

    def predict(self, arr, verbose=False):
        return [_Result([_Box([10, 20, 40, 60], 0, 0.9)])]


def _detector_with_fake_model():
    det = Detector.__new__(Detector)  # bypass __init__ so ultralytics is never imported
    det.model = _FakeModel()
    return det


def test_run_array_converts_xyxy_to_xywh_and_resolves_name():
    det = _detector_with_fake_model()
    result = det.run_array(np.zeros((100, 100, 3), dtype=np.uint8), width=100, height=100)
    assert isinstance(result, DetectionResult)
    assert result.image_width == 100 and result.image_height == 100
    assert len(result.detections) == 1
    d = result.detections[0]
    assert isinstance(d, Detection)
    assert d.bbox_xywh == (10, 20, 30, 40)   # x1=10,y1=20,w=40-10=30,h=60-20=40
    assert d.class_name == "fiber"
    assert d.confidence == 0.9


def test_run_array_infers_dims_from_array_when_missing():
    det = _detector_with_fake_model()
    result = det.run_array(np.zeros((30, 50, 3), dtype=np.uint8))  # H=30, W=50
    assert result.image_width == 50 and result.image_height == 30
