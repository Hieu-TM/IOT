"""Print the STRUCTURE of a real Roboflow workflow response - never its blobs.

The workflow's output names are chosen by whoever built the workflow, so they
cannot be known ahead of time. Run this once with real credentials to see them,
then set roboflow.predictions_key in ml/config.toml.

Usage:
    python -m ml.infer.probe path/to/image.jpg
"""

import argparse
import sys
from pathlib import Path

from . import config as config_mod
from .detector_roboflow import (
    RoboflowWorkflowDetector,
    extract_predictions,
    summarize_response,
)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m ml.infer.probe")
    parser.add_argument("image", help="A sample image to send to the workflow")
    parser.add_argument("--config", default=None,
                        help="Path to config.toml (default: ml/config.toml)")
    args = parser.parse_args(argv)

    cfg = config_mod.load(args.config)
    problems = cfg.missing_for("roboflow")
    if problems:
        print("Config NOT ready:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    rf = cfg.section("roboflow")
    detector = RoboflowWorkflowDetector(
        api_key=rf.get("api_key"),
        workspace=rf.get("workspace"),
        workflow_id=rf.get("workflow_id"),
        endpoint=rf.get("endpoint"),
        image_input_name=rf.get("image_input_name"),
        predictions_key=rf.get("predictions_key"),
        timeout=rf.get("timeout_s"),
        retries=rf.get("retries"),
    )

    raw = detector.fetch_raw(Path(args.image).read_bytes())
    print(f"POST {detector.url}")
    print("\n--- response structure (long values elided) ---")
    print(summarize_response(raw))

    entries = raw if isinstance(raw, list) else [raw]
    key = rf.get("predictions_key")
    found = extract_predictions(entries[0] if entries else {}, key)
    print(f"\nResolved {len(found)} prediction(s) with predictions_key={key!r}")
    if not found:
        print("No predictions resolved. Set roboflow.predictions_key to the key "
              "above that holds the bbox list (dotted paths supported).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
