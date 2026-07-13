"""Train a compact object detector on a Roboflow-exported (YOLO format) dataset.

Phase B of ml/README.md — prototype shakedown on the public microplastics-m7mf5
fork, not a claim of real-world accuracy (that comes after Phase D, real rig images).

Usage:
    python ml/train_detector.py --data ml/datasets/<version>/data.yaml \
        --epochs 100 --imgsz 416 --model yolo11n.pt
"""
import argparse

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="Path to Roboflow-exported data.yaml")
    parser.add_argument("--model", default="yolo11n.pt", help="Base checkpoint to fine-tune from")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--batch", type=int, default=16)
    args = parser.parse_args()

    model = YOLO(args.model)
    model.train(data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch)
    metrics = model.val(data=args.data, split="test")
    print("Test-split metrics:", metrics.results_dict)


if __name__ == "__main__":
    main()
