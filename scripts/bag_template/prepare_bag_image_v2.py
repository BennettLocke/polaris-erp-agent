import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


DEFAULT_TARGET_W = 550
DEFAULT_TARGET_H = 1500


def load_image(path):
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def write_image(path, image, params=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix or ".png"
    ok, encoded = cv2.imencode(ext, image, params or [])
    if not ok:
        raise RuntimeError(f"Could not encode image: {path}")
    encoded.tofile(str(path))


def order_points(points):
    points = np.asarray(points, dtype="float32")
    rect = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1)
    rect[0] = points[np.argmin(sums)]
    rect[2] = points[np.argmax(sums)]
    rect[1] = points[np.argmin(diffs)]
    rect[3] = points[np.argmax(diffs)]
    return rect


def make_mask(image):
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    white_bg = np.mean((saturation < 35) & (value > 145)) > 0.28
    if white_bg:
        mask = ((saturation > 48) & (value > 50)).astype(np.uint8) * 255
    else:
        border = max(12, min(h, w) // 40)
        samples = np.concatenate(
            [
                image[:border, :, :].reshape(-1, 3),
                image[-border:, :, :].reshape(-1, 3),
                image[:, :border, :].reshape(-1, 3),
                image[:, -border:, :].reshape(-1, 3),
            ],
            axis=0,
        )
        bg = np.median(samples, axis=0).astype(np.float32)
        distance = np.linalg.norm(image.astype(np.float32) - bg, axis=2)
        mask = ((distance > 34) | (saturation > 45)).astype(np.uint8) * 255

    kernel = np.ones((9, 9), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise RuntimeError("No bag outline found.")
    contour = max(contours, key=cv2.contourArea)
    clean = np.zeros_like(mask)
    cv2.drawContours(clean, [contour], -1, 255, cv2.FILLED)
    return clean, contour


def raw_rect(contour):
    return order_points(cv2.boxPoints(cv2.minAreaRect(contour)).astype("float32"))


def contour_from_mask(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def axes_from_contour(contour):
    rect = raw_rect(contour)
    top_mid = (rect[0] + rect[1]) / 2
    bottom_mid = (rect[2] + rect[3]) / 2
    v = bottom_mid - top_mid
    length = np.linalg.norm(v)
    if length < 1:
        return None
    v = v / length
    u = np.array([v[1], -v[0]], dtype=np.float32)
    points = contour.reshape(-1, 2).astype(np.float32)
    center = points.mean(axis=0)
    rel = points - center
    s = rel @ u
    t = rel @ v
    return points, center, u, v, s, t


def fit_line_ts(t_values, s_values):
    if len(t_values) < 8:
        return None
    return np.polyfit(t_values, s_values, 1)


def linefit_rect(mask, contour):
    # Shrink the mask before fitting so edge hair, black rim, and tiny notch noise
    # do not dominate the fitted straight sides.
    eroded = cv2.erode(mask, np.ones((23, 23), np.uint8), iterations=1)
    eroded = cv2.morphologyEx(eroded, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8), iterations=1)
    inner_contour = contour_from_mask(eroded)
    if inner_contour is None:
        inner_contour = contour
    axes = axes_from_contour(inner_contour)
    if axes is None:
        return None

    points, center, u, v, s, t = axes
    top_t, bottom_t = np.percentile(t, [1.8, 98.2])
    fit_top_t, fit_bottom_t = np.percentile(t, [8, 92])
    bands = np.linspace(fit_top_t, fit_bottom_t, 70)
    rows = []
    for a, b in zip(bands[:-1], bands[1:]):
        row = (t >= a) & (t < b)
        if row.sum() < 4:
            continue
        rows.append(((a + b) / 2, np.percentile(s[row], 2.5), np.percentile(s[row], 97.5)))
    if len(rows) < 18:
        return None

    row_t = np.array([row[0] for row in rows], dtype=np.float32)
    left_s = np.array([row[1] for row in rows], dtype=np.float32)
    right_s = np.array([row[2] for row in rows], dtype=np.float32)
    left_fit = fit_line_ts(row_t, left_s)
    right_fit = fit_line_ts(row_t, right_s)
    if left_fit is None or right_fit is None:
        return None

    left_top = left_fit[0] * top_t + left_fit[1]
    right_top = right_fit[0] * top_t + right_fit[1]
    left_bottom = left_fit[0] * bottom_t + left_fit[1]
    right_bottom = right_fit[0] * bottom_t + right_fit[1]
    if min(right_top - left_top, right_bottom - left_bottom) < 20:
        return None

    # Restore most of the eroded border while keeping the fitted direction stable.
    expand_s = 13
    expand_bottom_t = 10
    # The top edge often has a black notch/opening from the original photo.
    # Pull the top slightly inward instead of expanding upward into that noise.
    inset_top_t = 13
    left_top -= expand_s
    left_bottom -= expand_s
    right_top += expand_s
    right_bottom += expand_s
    top_t += inset_top_t
    bottom_t += expand_bottom_t

    def xy(side_s, pos_t):
        return center + u * side_s + v * pos_t

    return order_points(
        np.array(
            [
                xy(left_top, top_t),
                xy(right_top, top_t),
                xy(right_bottom, bottom_t),
                xy(left_bottom, bottom_t),
            ],
            dtype=np.float32,
        )
    )


def warp_to_target(image, rect, target_w=DEFAULT_TARGET_W, target_h=DEFAULT_TARGET_H):
    rect = order_points(rect)
    dst = np.array(
        [[0, 0], [target_w - 1, 0], [target_w - 1, target_h - 1], [0, target_h - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(
        image,
        matrix,
        (target_w, target_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def prepare(image, debug_dir=None, target_w=DEFAULT_TARGET_W, target_h=DEFAULT_TARGET_H):
    mask, contour = make_mask(image)
    rect = linefit_rect(mask, contour)
    method = "linefit"
    if rect is None:
        rect = raw_rect(contour)
        method = "raw"
    warped = warp_to_target(image, rect, target_w=target_w, target_h=target_h)

    if debug_dir:
        debug = Path(debug_dir)
        debug.mkdir(parents=True, exist_ok=True)
        overlay = image.copy()
        cv2.polylines(overlay, [order_points(rect).astype(np.int32)], True, (0, 255, 255), 6)
        write_image(debug / f"corners-{method}.jpg", overlay)
        write_image(debug / "mask.png", mask)
    return warped, method


def main():
    parser = argparse.ArgumentParser(description="Prepare a tea bag photo using eroded mask + fitted edge lines.")
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--debug-dir")
    parser.add_argument("--target-width", type=int, default=DEFAULT_TARGET_W)
    parser.add_argument("--target-height", type=int, default=DEFAULT_TARGET_H)
    args = parser.parse_args()

    image = load_image(args.input)
    prepared, method = prepare(
        image,
        debug_dir=args.debug_dir,
        target_w=args.target_width,
        target_h=args.target_height,
    )
    output = Path(args.output)
    write_image(output, prepared, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    print(f"saved {output} {args.target_width}x{args.target_height} method={method}")


if __name__ == "__main__":
    main()
