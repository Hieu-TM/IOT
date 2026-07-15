from PIL import Image

from ml.infer.source import FolderSource, Frame


def _write_jpeg(path):
    Image.new("RGB", (32, 32), (128, 128, 128)).save(path, format="JPEG")


def _write_png(path):
    Image.new("RGB", (32, 32), (128, 128, 128)).save(path, format="PNG")


def test_folder_source_yields_image_frames_only(tmp_path):
    _write_jpeg(tmp_path / "a.jpg")
    _write_png(tmp_path / "b.png")
    (tmp_path / "notes.txt").write_text("ignore me")

    frames = list(FolderSource(tmp_path).frames())

    assert len(frames) == 2
    assert {f.source_name for f in frames} == {"a.jpg", "b.png"}
    for f in frames:
        assert isinstance(f, Frame)
        assert f.image_bytes[:2] in (b"\xff\xd8", b"\x89P")  # jpeg / png magic
        assert f.captured_at.tzinfo is not None
        assert f.sample_code in ("a", "b")


def test_folder_source_accepts_single_file(tmp_path):
    _write_jpeg(tmp_path / "solo.jpg")
    frames = list(FolderSource(tmp_path / "solo.jpg").frames())
    assert len(frames) == 1
    assert frames[0].sample_code == "solo"
