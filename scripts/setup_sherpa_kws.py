"""Prepare sherpa-onnx local keyword spotting assets for the robot."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_NAME = "sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"
MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/"
    f"{MODEL_NAME}.tar.bz2"
)


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return
    print(f"download {url}")
    urllib.request.urlretrieve(url, target)


def ensure_model(models_dir: Path) -> Path:
    model_dir = models_dir / MODEL_NAME
    if model_dir.exists():
        return model_dir
    archive = models_dir / f"{MODEL_NAME}.tar.bz2"
    download(MODEL_URL, archive)
    print(f"extract {archive}")
    with tarfile.open(archive) as tar:
        tar.extractall(models_dir)
    return model_dir


def write_keywords(models_dir: Path) -> Path:
    # Keep near-sound aliases local-only. They make wake more forgiving while
    # cloud ASR remains disabled before wake, so they no longer trigger command
    # handling through the old ASR fallback.
    raw = models_dir / "xiaoxing_keywords_raw.txt"
    raw.write_text(
        "\u5c0f\u661f :4.0 #0.12 @\u5c0f\u661f\n"
        "\u6653\u661f :3.5 #0.12 @\u6653\u661f\n"
        "\u5c0f\u65b0 :2.5 #0.16 @\u5c0f\u65b0\n"
        "\u5c0f\u5fc3 :2.5 #0.16 @\u5c0f\u5fc3\n",
        encoding="utf-8",
    )
    return raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", default=str(ROOT / "models"))
    args = parser.parse_args()

    models_dir = Path(args.models_dir)
    model_dir = ensure_model(models_dir)
    raw = write_keywords(models_dir)
    keywords = models_dir / "xiaoxing_keywords.txt"
    keywords.unlink(missing_ok=True)
    cli_path = Path(sys.executable).resolve().parent / "sherpa-onnx-cli"
    cli = str(cli_path) if cli_path.exists() else shutil.which("sherpa-onnx-cli")
    cmd = [cli] if cli else [sys.executable, "-m", "sherpa_onnx.cli"]
    subprocess.run(
        cmd
        + [
            "text2token",
            "--tokens",
            str(model_dir / "tokens.txt"),
            "--tokens-type",
            "phone+ppinyin",
            "--lexicon",
            str(model_dir / "en.phone"),
            str(raw),
            str(keywords),
        ],
        check=True,
    )
    print(f"model_dir={model_dir}")
    print(f"keywords_raw={raw}")
    print(f"keywords={keywords}")


if __name__ == "__main__":
    main()
