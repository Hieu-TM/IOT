from ml.infer.naming import (
    sample_code_from_filename,
    resolve_px_per_mm,
    DEFAULT_PX_PER_MM,
)


def test_sample_code_strips_unsafe_chars():
    assert sample_code_from_filename("my photo (1).JPG") == "my-photo--1"


def test_sample_code_handles_path_and_traversal():
    assert sample_code_from_filename("../../etc/passwd.png") == "passwd"


def test_sample_code_truncates_to_64():
    long_name = "a" * 100 + ".jpg"
    assert len(sample_code_from_filename(long_name)) == 64


def test_sample_code_never_empty():
    assert sample_code_from_filename("---.jpg") == "sample"


def test_resolve_px_per_mm_default():
    assert resolve_px_per_mm(None) == (DEFAULT_PX_PER_MM, True)


def test_resolve_px_per_mm_explicit():
    assert resolve_px_per_mm(20.0) == (20.0, False)
