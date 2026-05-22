"""Prepare sherpa-onnx local keyword spotting assets for the robot."""
from __future__ import annotations

import argparse
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
    # Keep the wake list strict for always-on listening. Near-sound aliases such
    # as "小心小心" are too easy to false-trigger on this small board mic.
    raw = models_dir / "xiaoxing_keywords_raw.txt"
    raw.write_text(
        "\u5c0f\u661f\u5c0f\u661f :3.5 #0.08 @\u5c0f\u661f\u5c0f\u661f\n"
        "\u5c0f\u661f\u5728\u5417 :3.4 #0.08 @\u5c0f\u661f\u5728\u5417\n"
        "\u6653\u661f\u6653\u661f :3.4 #0.08 @\u6653\u661f\u6653\u661f\n"
        "\u5c0f\u661f\u540c\u5b66 :3.4 #0.08 @\u5c0f\u661f\u540c\u5b66\n"
        "\u5c0f\u661f\u9192\u9192 :3.4 #0.08 @\u5c0f\u661f\u9192\u9192\n"
        "\u5c0f\u661f\u52a9\u624b :3.4 #0.08 @\u5c0f\u661f\u52a9\u624b\n"
        "\u5c0f\u5fc3\u5c0f\u5fc3 :3.6 #0.09 @\u5c0f\u5fc3\u5c0f\u5fc3\n"
        "\u5c0f\u5b81\u5c0f\u5b81 :3.6 #0.09 @\u5c0f\u5b81\u5c0f\u5b81\n"
        "\u5c0f\u65b0\u5c0f\u65b0 :3.8 #0.10 @\u5c0f\u65b0\u5c0f\u65b0\n",
        encoding="utf-8",
    )
    return raw


def encode_keywords(raw: Path, output: Path, model_dir: Path) -> None:
    from sherpa_onnx.utils import text2token

    lines: list[str] = []
    for line in raw.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        phrase, sep, suffix = line.partition(" :")
        encoded = text2token(
            [phrase.strip()],
            tokens=str(model_dir / "tokens.txt"),
            tokens_type="phone+ppinyin",
            lexicon=str(model_dir / "en.phone"),
        )[0]
        lines.append(" ".join(str(token) for token in encoded) + (f" :{suffix}" if sep else ""))
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", default=str(ROOT / "models"))
    args = parser.parse_args()

    models_dir = Path(args.models_dir)
    model_dir = ensure_model(models_dir)
    raw = write_keywords(models_dir)
    keywords = models_dir / "xiaoxing_keywords.txt"
    keywords.unlink(missing_ok=True)
    encode_keywords(raw, keywords, model_dir)
    print(f"model_dir={model_dir}")
    print(f"keywords_raw={raw}")
    print(f"keywords={keywords}")


if __name__ == "__main__":
    main()
