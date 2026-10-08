"""Export the YOLO model named in config.py to NCNN (faster on the Raspberry Pi CPU).

NCNN models have a fixed input size, so this exports at config.INFERENCE_IMAGE_SIZE.
Re-run it whenever you change the model or that size.
"""

import sys
from pathlib import Path

import config


def main():
    if config.MODEL_NAME.startswith("rfdetr-") or not config.MODEL_NAME.endswith(".pt"):
        sys.exit(f"MODEL_NAME={config.MODEL_NAME!r} is not a YOLO .pt file; nothing to export.")
    if config.INFERENCE_IMAGE_SIZE <= 0:
        sys.exit("Set INFERENCE_IMAGE_SIZE to a positive multiple of 32 before exporting.")

    from ultralytics import YOLO

    exported = Path(YOLO(config.MODEL_NAME).export(
        format="ncnn", imgsz=config.INFERENCE_IMAGE_SIZE))
    print(f"\nExported: {exported}")
    print(f'Set MODEL_NAME = "{exported.name}" in config.py (keep INFERENCE_IMAGE_SIZE = '
          f"{config.INFERENCE_IMAGE_SIZE}), then run ./run_benchmark.sh to compare.")


if __name__ == "__main__":
    main()
