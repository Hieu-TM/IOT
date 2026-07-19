"""CLI: run the detector over a folder/file and POST results to /api/ingest.

Usage:
    python -m ml.infer <image|folder> --weights ml/models/best.pt \
        --api-url http://localhost:8000 --device-id pc-infer --px-per-mm <n>
"""

import argparse
import sys

from . import config
from .detector import Detector
from .detector_roboflow import RoboflowWorkflowDetector
from .ingest_client import post
from .mapper import build_metadata
from .naming import resolve_px_per_mm
from .source import FolderSource


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="python -m ml.infer",
        description="Run the detector on images and POST count/size/label to "
                    "/api/ingest. Settings come from ml/config.toml unless a "
                    "flag overrides them.",
    )
    p.add_argument("input", nargs="?", help="Image file or folder of images")
    p.add_argument("--config", default=None,
                   help="Path to config.toml (default: ml/config.toml)")
    p.add_argument("--backend", choices=["local", "roboflow"], default=None,
                   help="local = self-trained .pt; roboflow = hosted API")
    p.add_argument("--weights", default=None)
    p.add_argument("--api-url", default=None)
    p.add_argument("--device-id", default=None)
    p.add_argument("--px-per-mm", type=float, default=None)
    p.add_argument("--batch-lot", default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="Detect and print only; do not POST to the API")
    p.add_argument("--check-config", action="store_true",
                   help="Validate the resolved config for the chosen backend and exit")
    return p


def build_detector(cfg, backend, weights):
    """Construct the detector for the chosen backend.

    Both backends return the identical DetectionResult contract, so everything
    downstream (mapper, ingest_client) is backend-agnostic.
    """
    if backend == "roboflow":
        rf = cfg.section("roboflow")
        return RoboflowWorkflowDetector(
            api_key=rf.get("api_key"),
            workspace=rf.get("workspace"),
            workflow_id=rf.get("workflow_id"),
            endpoint=rf.get("endpoint"),
            image_input_name=rf.get("image_input_name"),
            predictions_key=rf.get("predictions_key"),
            timeout=rf.get("timeout_s"),
            retries=rf.get("retries"),
            extra_inputs=rf.get("extra_inputs"),
        )
    return Detector(weights)


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    cfg = config.load(args.config)

    backend = args.backend if args.backend is not None else cfg.get("general", "backend")

    if args.check_config:
        problems = cfg.missing_for(backend)
        print(f"backend = {backend}")
        if problems:
            print("Config NOT ready:")
            for p in problems:
                print(f"  - {p}")
            return 1
        print("Config OK - ready to run.")
        return 0

    if not args.input:
        print("[error] missing input (image file or folder). See --help.")
        return 2

    api_url = args.api_url if args.api_url is not None else cfg.get("ingest", "api_url")
    device_id = args.device_id if args.device_id is not None else cfg.get("ingest", "device_id")
    batch_lot = args.batch_lot if args.batch_lot is not None else cfg.get("ingest", "batch_lot")
    weights = args.weights if args.weights is not None else cfg.get("local", "weights")

    px_setting = (args.px_per_mm if args.px_per_mm is not None
                  else cfg.get("calibration", "px_per_mm"))
    px, used_default = resolve_px_per_mm(px_setting)
    if used_default:
        print(f"[warn] px_per_mm not set; using default {px} px/mm. "
              "size_mm is a PLACEHOLDER, not a real calibration.")

    try:
        detector = build_detector(cfg, backend, weights)
    except Exception as exc:
        print(f"[error] cannot start backend={backend!r}: {exc}")
        for problem in cfg.missing_for(backend):
            print(f"  - {problem}")
        print("Run `python -m ml.infer --check-config` after fixing.")
        return 2
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
                device_id=device_id,
                px_per_mm=px,
                batch_lot=batch_lot,
            )
            if args.dry_run:
                print(f"[dry-run] {frame.source_name}: "
                      f"{len(metadata['particles'])} particles")
                continue
            res = post(api_url, metadata, frame.image_bytes,
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
