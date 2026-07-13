"""Export a trained Ultralytics detector to an int8-quantized TFLite model.

Phase C of ml/README.md — feeds the ESP32-CAM-detector vs Edge-Impulse-FOMO
deploy decision, which must be made from measured numbers (see benchmark_tflite.py),
not guessed.

Usage:
    python ml/export_tflite.py --weights runs/detect/train/weights/best.pt \
        --imgsz 192 --data ml/datasets/<version>/data.yaml
"""
import argparse

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", required=True, help="Path to trained .pt weights")
    parser.add_argument("--imgsz", type=int, default=192,
                         help="Lowest resolution that still resolves ~2mm particles at your px/mm")
    parser.add_argument("--data", required=True,
                         help="data.yaml used to build the int8 representative dataset")
    args = parser.parse_args()

    model = YOLO(args.weights)
    exported_path = model.export(format="tflite", int8=True, imgsz=args.imgsz, data=args.data)
    print(f"Exported int8 TFLite model to: {exported_path}")
    print("Next: python ml/benchmark_tflite.py --model", exported_path)


if __name__ == "__main__":
    main()
