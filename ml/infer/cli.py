"""CLI: run the detector over a folder/file and POST results to /api/ingest.

Usage:
    python -m ml.infer <image|folder> --weights ml/models/best.pt \
        --api-url http://localhost:8000 --device-id pc-infer --px-per-mm <n>
"""

import argparse
import sys

from .detector import Detector
from .ingest_client import post
from .mapper import build_metadata
from .naming import resolve_px_per_mm
from .source import FolderSource


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="python -m ml.infer",
        description="Run the Roboflow-trained detector on images and POST "
                    "count/size/label to /api/ingest.",
    )
    p.add_argument("input", help="Image file or folder of images")
    p.add_argument("--weights", default="ml/models/best.pt")
    p.add_argument("--api-url", default="http://localhost:8000")
    p.add_argument("--device-id", default="pc-infer")
    p.add_argument("--px-per-mm", type=float, default=None)
    p.add_argument("--batch-lot", default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="Detect and print only; do not POST to the API")
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)

    px, used_default = resolve_px_per_mm(args.px_per_mm)
    if used_default:
        print(f"[warn] --px-per-mm not set; using default {px} px/mm. "
              "size_mm is a PLACEHOLDER, not a real calibration.")

    detector = Detector(args.weights)
    source = FolderSource(args.input)

    created = already = failed = 0
    collisions = 0
    failed_names = []
    collision_names = []
    seen_codes = {}  # sample_code -> first source_name this run
    for frame in source.frames():
        prior = seen_codes.get(frame.sample_code)
        if prior is not None:
            collisions += 1
            collision_names.append(
                f"{frame.source_name} collides with {prior} (both -> {frame.sample_code})")
            print(f"[warn] collision: {frame.source_name} -> {frame.sample_code} "
                  f"(already used by {prior}); not sent. Rename the file to store it.")
            continue
        seen_codes[frame.sample_code] = frame.source_name
        try:
            result = detector.run(frame.image_bytes)
            metadata = build_metadata(
                detections=result.detections,
                image_width=result.image_width,
                image_height=result.image_height,
                sample_code=frame.sample_code,
                captured_at=frame.captured_at,
                device_id=args.device_id,
                px_per_mm=px,
                batch_lot=args.batch_lot,
            )
            if args.dry_run:
                print(f"[dry-run] {frame.source_name}: "
                      f"{len(metadata['particles'])} particles")
                continue
            res = post(args.api_url, metadata, frame.image_bytes,
                       f"{frame.sample_code}.jpg")
            if res.status == "created":
                created += 1
            elif res.status == "already_exists":
                already += 1
            else:
                failed += 1
                failed_names.append(
                    f"{frame.source_name} ({res.http_status}: {res.detail})")
            print(f"[{res.status}] {frame.source_name} -> {frame.sample_code}")
        except Exception as exc:  # one image must never abort the whole batch
            failed += 1
            failed_names.append(f"{frame.source_name} ({exc})")
            print(f"[failed] {frame.source_name}: {exc}")

    summary = f"\nSummary: {created} created, {already} already_exists, {failed} failed"
    if collisions:
        summary += f", {collisions} collisions (not sent)"
    print(summary)
    if failed_names:
        print("Failed:")
        for n in failed_names:
            print(f"  - {n}")
    if collision_names:
        print("Collisions (rename to store):")
        for n in collision_names:
            print(f"  - {n}")
    return 1 if (failed or collisions) else 0


if __name__ == "__main__":
    sys.exit(main())
