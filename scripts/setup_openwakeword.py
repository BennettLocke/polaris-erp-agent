"""Prepare openWakeWord runtime feature assets for the robot."""
from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", default=str(ROOT / "models" / "openwakeword"))
    args = parser.parse_args()

    from openwakeword.utils import download_models

    models_dir = Path(args.models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    download_models(model_names=["__feature_models_only__"], target_directory=str(models_dir))
    print(f"openwakeword_models={models_dir}")


if __name__ == "__main__":
    main()
