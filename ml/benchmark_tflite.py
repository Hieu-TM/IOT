"""Measure the numbers Phase C's deploy decision depends on: model size (~flash),
a tensor-arena estimate (~RAM), and per-inference latency.

This runs on your PC, not the ESP32-CAM — treat the latency number as an optimistic
lower bound. ESP32-CAM (plain ESP32, no AI accelerator) will be substantially slower;
add a safety margin before concluding a real YOLO-style detector is feasible on-device.

Usage:
    python ml/benchmark_tflite.py --model best_int8.tflite --runs 50
"""
import argparse
import os
import time

import numpy as np

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    from tensorflow.lite.python.interpreter import Interpreter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Path to the .tflite model")
    parser.add_argument("--runs", type=int, default=50, help="Number of timed inference passes")
    args = parser.parse_args()

    size_kb = os.path.getsize(args.model) / 1024
    print(f"Model file size (~flash needed): {size_kb:.1f} KB")

    interpreter = Interpreter(model_path=args.model)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()
    shape = input_details["shape"]
    dtype = input_details["dtype"]

    tensor_details = interpreter.get_tensor_details()
    arena_estimate_kb = sum(
        np.prod(t["shape"]) * np.dtype(t["dtype"]).itemsize for t in tensor_details
    ) / 1024
    print(f"Rough tensor-arena estimate (sum of all tensor buffers): {arena_estimate_kb:.1f} KB")
    print("(This over-counts vs. the real arena allocator; treat as an upper-bound sanity check.)")

    rng = np.random.default_rng(0)
    if np.issubdtype(dtype, np.integer):
        sample = rng.integers(0, 255, size=shape, dtype=dtype)
    else:
        sample = rng.random(size=shape).astype(dtype)

    interpreter.set_tensor(input_details["index"], sample)
    interpreter.invoke()  # warm-up

    start = time.perf_counter()
    for _ in range(args.runs):
        interpreter.set_tensor(input_details["index"], sample)
        interpreter.invoke()
    elapsed = time.perf_counter() - start

    per_run_ms = (elapsed / args.runs) * 1000
    print(f"Avg latency on this PC over {args.runs} runs: {per_run_ms:.2f} ms/inference")
    print(f"Input shape: {shape}, dtype: {dtype}")
    print(f"Output tensors: {len(output_details)}")


if __name__ == "__main__":
    main()
