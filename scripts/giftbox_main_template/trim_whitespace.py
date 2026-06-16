"""Trim white or transparent margins from a product image for main-image templates."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def is_foreground(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    if alpha <= 12:
        return False
    return not (red >= 245 and green >= 245 and blue >= 245)


def trim_image(input_path: Path, output_path: Path, margin: int = 16) -> None:
    image = Image.open(input_path).convert("RGBA")
    width, height = image.size
    pixels = image.load()
    min_x, min_y = width, height
    max_x, max_y = -1, -1

    for y in range(height):
        for x in range(width):
            if is_foreground(pixels[x, y]):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if max_x < min_x or max_y < min_y:
        image.save(output_path)
        return

    left = max(0, min_x - margin)
    top = max(0, min_y - margin)
    right = min(width, max_x + margin + 1)
    bottom = min(height, max_y + margin + 1)
    cropped = image.crop((left, top, right, bottom))
    cropped_pixels = cropped.load()
    cropped_width, cropped_height = cropped.size
    for y in range(cropped_height):
        for x in range(cropped_width):
            red, green, blue, alpha = cropped_pixels[x, y]
            if alpha > 0 and red >= 248 and green >= 248 and blue >= 248:
                cropped_pixels[x, y] = (red, green, blue, 0)
    cropped.save(output_path)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("Usage: trim_whitespace.py input output [margin]", file=sys.stderr)
        return 2

    margin = int(argv[3]) if len(argv) >= 4 else 16
    trim_image(Path(argv[1]), Path(argv[2]), margin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
