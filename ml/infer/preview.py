"""Live annotated preview — VISUALIZATION ONLY. Never writes to the DB.

Why streaming is not the counting path: /stream is low-res MJPEG (particles
<2mm vanish) over flowing water (a moving particle would be double-counted
across frames). Counting/sizing is a single high-res still in the Stop-Flow
pump-off window (that is the /capture path). This tool only draws boxes for a
human to eyeball during a demo; the on-screen count is transient, not audited.

Structurally cannot write to the database — visualization only.

Usage:
    python -m ml.infer.preview --source webcam:0 --weights ml/models/best.pt --fps 2
    python -m ml.infer.preview --source http://<esp32-ip>/stream --weights ml/models/best.pt
    python -m ml.infer.preview --source path/to/video.mp4 --weights ml/models/best.pt
"""

import argparse
import sys
import time

from .detector import Detector


def annotate_frame(frame_bgr, detections):
    # cv2 imported inside function to allow `import ml.infer.preview` without opencv
    import cv2

    for d in detections:
        x, y, w, h = d.bbox_xywh
        cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(frame_bgr, f"{d.class_name} {d.confidence:.2f}",
                    (x, max(0, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 255, 0), 1)
    cv2.putText(frame_bgr, "PREVIEW - not logged", (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    return frame_bgr


def _open_capture(source):
    import cv2

    if source.startswith("webcam:"):
        return cv2.VideoCapture(int(source.split(":", 1)[1]))
    return cv2.VideoCapture(source)


def main(argv=None):
    import cv2

    p = argparse.ArgumentParser(prog="python -m ml.infer.preview")
    p.add_argument("--source", required=True,
                   help="webcam:<n> | <stream-url> | <video-file>")
    p.add_argument("--weights", default="ml/models/best.pt")
    p.add_argument("--fps", type=float, default=2.0,
                   help="Max detector passes per second (throttle)")
    args = p.parse_args(argv)

    cap = _open_capture(args.source)
    try:
        if not cap.isOpened():
            print(f"[error] cannot open source: {args.source}")
            return 1
        detector = Detector(args.weights)
        min_interval = 1.0 / args.fps if args.fps > 0 else 0.0
        last = 0.0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            now = time.time()
            if now - last >= min_interval:
                last = now
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = detector.run_array(rgb)
                annotate_frame(frame, result.detections)
            cv2.imshow("Aqua Scope preview (not logged)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        return 0
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    sys.exit(main())
