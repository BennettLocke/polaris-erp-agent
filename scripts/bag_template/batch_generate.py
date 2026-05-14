import argparse
import base64
import html
import mimetypes
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
RENDERER = ROOT / "render_svg_resvg.js"
BACKGROUND = "#f8f8f8"
RATIO_H_OVER_W = 1500 / 550


TEMPLATE_CONFIGS = {
    "rock-tea": {
        "aliases": {"rock-tea", "yancha", "岩茶", "长泡袋"},
        "color_name": "九龙窠肉桂",
        "subtitle": "雅致非凡，尽显格调",
        "category": "武夷岩茶",
        "target_width": 550,
        "target_height": 1500,
        "spec": "55MMx150MM",
        "width_label": "55MM",
        "height_label": "150MM",
        "product_image": "SJ0506-raw-standard.png",
        "embed_scale": 1.02,
        "embed_x": 0,
        "embed_y": 0,
        "main_left": {"x": 68, "y": 96, "w": 220, "h": 600},
        "main_right": {"x": 388, "y": 318, "angle": -22, "w": 258, "h": 704},
        "main_scene": {"x": 360, "y": 205, "w": 440, "h": 595},
        "top_left": {"x": 58, "y": 104, "size": 430},
        "top_right": {"x": 520, "y": 492, "size": 430},
        "corner": {"x": 45, "y": 1608, "angle": 48, "w": 800, "h": 1080, "scale": 1.0},
        "big": {"x": 1200, "y": 1800, "angle": 49, "w": 800},
    },
    "black-tea": {
        "aliases": {"black-tea", "hongcha", "红茶", "短泡袋"},
        "color_name": "红茶",
        "subtitle": "雅致非凡，尽显格调",
        "category": "红茶泡袋",
        "target_width": 520,
        "target_height": 1100,
        "spec": "52MMx110MM",
        "width_label": "52MM",
        "height_label": "110MM",
        "product_image": "SJ0506-raw-standard.png",
        "embed_scale": 1.02,
        "embed_x": 0,
        "embed_y": 0,
        "main_left": {"x": 45, "y": 100, "w": 305, "h": 646},
        "main_right": {"x": 430, "y": 245, "angle": 0, "w": 300, "h": 635},
        "main_scene": {"x": 400, "y": 236, "w": 400, "h": 564},
        "main_text": {
            "code_x": 432,
            "code_y": 65,
            "code_size": 20,
            "title_x": 430,
            "title_y": 146,
            "title_size": 76,
            "subtitle_x": 432,
            "subtitle_y": 190,
            "subtitle_size": 24,
            "category_x": 432,
            "category_y": 224,
            "category_size": 22,
            "category_letter_spacing": 2,
        },
        "main_spec": {"x": 555, "y": 207, "w": 134, "text_x": 622, "text_y": 222, "size": 11},
        "top_left": {"x": 58, "y": 120, "size": 430},
        "top_right": {"x": 520, "y": 460, "size": 430},
        "detail_text": {"category_y": 430},
        "detail_spec": {"y": 403, "text_y": 425},
        "detail_height": 3380,
        "detail_callout": {"x": 238, "y": 1362, "angle": 50},
        "corner": {"x": 45, "y": 1325, "angle": 48, "w": 800, "h": 940, "scale": 1.0},
        "big": {"x": 900, "y": 1870, "angle": 49, "w": 800},
    },
}


CONFIG = TEMPLATE_CONFIGS["rock-tea"].copy()


def apply_template(template_name):
    global CONFIG, RATIO_H_OVER_W
    key = normalize_template_name(template_name)
    CONFIG = TEMPLATE_CONFIGS[key].copy()
    RATIO_H_OVER_W = CONFIG["target_height"] / CONFIG["target_width"]
    return key


def font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default(size=size)


def text_width(text, size, bold=True):
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    return draw.textlength(text, font=font(size, bold))


def sanitize_name(value):
    return re.sub(r'[\\/:*?"<>|]+', "-", value).strip() or "未命名"


def normalize_template_name(value):
    value = (value or "rock-tea").strip()
    for key, config in TEMPLATE_CONFIGS.items():
        if value == key or value in config["aliases"]:
            return key
    raise ValueError(f"未知泡袋模板：{value}")


def next_code(start, offset):
    match = re.match(r"^([A-Za-z]+)(\d+)$", start)
    if not match:
        raise ValueError("起始编码格式请用 SJ01001 这种形式")
    prefix, number = match.groups()
    return f"{prefix}{int(number) + offset:0{len(number)}d}"


def input_files(path):
    path = Path(path)
    if path.is_file():
        return [path]
    return sorted(
        p
        for p in path.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".png"
        and "contact-sheet" not in p.stem.lower()
    )


def image_data_uri(path):
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def esc(value):
    return html.escape(str(value), quote=True)


def embedded(base_x, base_y, base_w, base_h):
    scale = CONFIG["embed_scale"]
    width = base_w * scale
    height = base_h * scale
    x = base_x + (base_w - width) / 2 + CONFIG["embed_x"]
    y = base_y + (base_h - height) / 2 + CONFIG["embed_y"]
    return x, y, width, height


def notch_points(x, y, width):
    cx = x + width * 0.75
    notch_w = max(7, width * 0.045)
    notch_h = max(8, width * 0.055)
    return f"{cx - notch_w / 2},{y} {cx + notch_w / 2},{y} {cx},{y + notch_h}"


def notched_clip_path(width, height, radius):
    cx = width * 0.75
    notch_w = max(7, width * 0.045)
    notch_h = max(8, width * 0.055)
    left = cx - notch_w / 2
    right = cx + notch_w / 2
    return (
        f"M {radius} 0 "
        f"H {left} L {cx} {notch_h} L {right} 0 "
        f"H {width - radius} "
        f"Q {width} 0 {width} {radius} "
        f"V {height - radius} "
        f"Q {width} {height} {width - radius} {height} "
        f"H {radius} "
        f"Q 0 {height} 0 {height - radius} "
        f"V {radius} "
        f"Q 0 0 {radius} 0 Z"
    )


def split_subtitle(value):
    text = (value or CONFIG["subtitle"]).strip()
    parts = [p for p in re.split(r"[，,、;；\s]+", text) if p]
    if len(parts) >= 2:
        return parts[0], "".join(parts[1:])
    if len(text) > 5:
        midpoint = (len(text) + 1) // 2
        return text[:midpoint], text[midpoint:]
    return text, ""


def main_spec_layout(subtitle, spec_text):
    sub_size = 22 if len(subtitle) > 7 else 28
    spec_text_width = text_width(spec_text, 11)
    width = max(132, min(178, spec_text_width + 22))
    subtitle_end = 376 + text_width(subtitle, sub_size)
    box_x = min(760 - width, subtitle_end + 14)
    return box_x, 185, width, box_x + width / 2, sub_size, 10 if spec_text_width > 150 else 11


def detail_spec_layout(category, spec_text):
    spec_text_width = text_width(spec_text, 18)
    width = max(168, min(230, spec_text_width + 30))
    box_x = min(930 - width, 530 + text_width(category, 36) + 18)
    return box_x, 421, width, box_x + width / 2, 16 if spec_text_width > 205 else 18


def font_family():
    return "Microsoft YaHei, PingFang SC, Arial, sans-serif"


def bag_image_element(id_, href, base_x, base_y, base_w, base_h, mask):
    x, y, w, h = embedded(base_x, base_y, base_w, base_h)
    return (
        f'<image id="{id_}" href="{href}" x="{x:.2f}" y="{y:.2f}" '
        f'width="{w:.2f}" height="{h:.2f}" preserveAspectRatio="none" mask="url(#{mask})" />'
    )


def main_svg(image_href, code, title):
    left = CONFIG["main_left"]
    right = CONFIG["main_right"]
    scene = CONFIG["main_scene"]
    subtitle = CONFIG["subtitle"]
    category = CONFIG["category"]
    spec_text = f"规格：{CONFIG['spec']}"
    if "main_spec" in CONFIG:
        spec = CONFIG["main_spec"]
        spec_x, spec_y, spec_w = spec["x"], spec["y"], spec["w"]
        spec_text_x = spec["text_x"]
        spec_text_y = spec["text_y"]
        spec_size = spec["size"]
        sub_size = CONFIG.get("main_text", {}).get("subtitle_size", 28)
    else:
        spec_x, spec_y, spec_w, spec_text_x, sub_size, spec_size = main_spec_layout(subtitle, spec_text)
        spec_text_y = 200
    right_img_x, right_img_y, right_img_w, right_img_h = embedded(0, 0, right["w"], right["h"])
    text = CONFIG.get("main_text", {})
    code_x = text.get("code_x", 376)
    code_y = text.get("code_y", 76)
    code_size = text.get("code_size", 16)
    title_x = text.get("title_x", 374)
    title_y = text.get("title_y", 158)
    title_size = text.get("title_size", 76)
    subtitle_x = text.get("subtitle_x", 376)
    subtitle_y = text.get("subtitle_y", 201)
    category_x = text.get("category_x", 376)
    category_y = text.get("category_y", 236)
    category_size = text.get("category_size", 28)
    category_letter_spacing = text.get("category_letter_spacing", 0)
    guide_right = left["x"] + left["w"]
    guide_bottom = left["y"] + left["h"]
    guide_mid_x = left["x"] + left["w"] / 2
    guide_mid_y = left["y"] + left["h"] / 2
    guide_side_x = guide_right + 24
    guide_side_text_x = guide_side_x + 15

    return f'''<svg width="1600" height="1600" viewBox="0 0 800 800" role="img" aria-label="泡袋主图预览" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="leftBagShadow" x="-30%" y="-25%" width="160%" height="160%">
      <feDropShadow dx="0" dy="16" stdDeviation="10" flood-color="#111820" flood-opacity="0.16" />
      <feDropShadow dx="-3" dy="4" stdDeviation="4" flood-color="#111820" flood-opacity="0.12" />
    </filter>
    <filter id="rightBagShadow" x="-35%" y="-30%" width="175%" height="175%">
      <feDropShadow dx="12" dy="18" stdDeviation="13" flood-color="#111820" flood-opacity="0.2" />
      <feDropShadow dx="2" dy="5" stdDeviation="5" flood-color="#111820" flood-opacity="0.12" />
    </filter>
    <clipPath id="rightSceneClip"><rect x="{scene['x']}" y="{scene['y']}" width="{scene['w']}" height="{scene['h']}" /></clipPath>
    <mask id="leftBagMask" maskUnits="userSpaceOnUse" x="-2000" y="-2000" width="6000" height="8000">
      <rect x="{left['x']}" y="{left['y']}" width="{left['w']}" height="{left['h']}" rx="{round(min(left['w'], left['h']) * 0.08)}" fill="#fff" />
      <polygon points="{notch_points(left['x'], left['y'], left['w'])}" fill="#000" />
    </mask>
    <mask id="rightBagMask" maskUnits="userSpaceOnUse" x="-2000" y="-2000" width="6000" height="8000">
      <rect x="0" y="0" width="{right['w']}" height="{right['h']}" rx="{round(min(right['w'], right['h']) * 0.085)}" fill="#fff" />
      <polygon points="{notch_points(0, 0, right['w'])}" fill="#000" />
    </mask>
  </defs>
  <rect width="800" height="800" fill="{BACKGROUND}" />
  <g stroke="#bfc3c8" stroke-width="2" fill="none">
    <path d="M{left['x']} {left['y'] - 18} H{guide_right}" />
    <path d="M{left['x']} {left['y'] - 26} V{left['y'] - 10} M{guide_right} {left['y'] - 26} V{left['y'] - 10}" />
    <path d="M{guide_side_x} {left['y']} V{guide_bottom}" />
    <path d="M{guide_side_x - 8} {left['y']} H{guide_side_x + 8} M{guide_side_x - 8} {guide_bottom} H{guide_side_x + 8}" />
  </g>
  <text x="{guide_mid_x:.2f}" y="{left['y'] - 26}" fill="#9a9da3" font-family="{font_family()}" font-size="16" font-weight="700" text-anchor="middle" letter-spacing="1">{esc(CONFIG['width_label'])}</text>
  <text x="{guide_side_text_x:.2f}" y="{guide_mid_y:.2f}" fill="#9a9da3" font-family="{font_family()}" font-size="16" font-weight="700" text-anchor="middle" transform="rotate(90 {guide_side_text_x:.2f} {guide_mid_y:.2f})" letter-spacing="1">{esc(CONFIG['height_label'])}</text>
  <g filter="url(#leftBagShadow)">
    {bag_image_element('leftProductImage', image_href, left['x'], left['y'], left['w'], left['h'], 'leftBagMask')}
  </g>
  <g clip-path="url(#rightSceneClip)">
    <g transform="translate({right['x']} {right['y']}) rotate({right['angle']})" filter="url(#rightBagShadow)">
      <image href="{image_href}" x="{right_img_x:.2f}" y="{right_img_y:.2f}" width="{right_img_w:.2f}" height="{right_img_h:.2f}" preserveAspectRatio="none" mask="url(#rightBagMask)" />
    </g>
  </g>
  <g font-family="{font_family()}">
    <text x="{code_x}" y="{code_y}" font-size="{code_size}" font-weight="700" fill="#6d7178">编号：{esc(code)}</text>
    <text x="{title_x}" y="{title_y}" font-size="{title_size}" font-weight="900" fill="#080808">{esc(title)}</text>
    <text x="{subtitle_x}" y="{subtitle_y}" font-size="{sub_size}" font-weight="900" fill="#080808">{esc(subtitle)}</text>
    <rect x="{spec_x:.2f}" y="{spec_y}" width="{spec_w:.2f}" height="20" rx="3" fill="{BACKGROUND}" stroke="#bfc3c8" />
    <text x="{spec_text_x:.2f}" y="{spec_text_y}" font-size="{spec_size}" font-weight="700" fill="#62666e" text-anchor="middle">{esc(spec_text)}</text>
    <text x="{category_x}" y="{category_y}" font-size="{category_size}" font-weight="900" fill="#6a6d73" letter-spacing="{category_letter_spacing}">{esc(category)}</text>
  </g>
</svg>'''


def detail_svg(image_href, code, title):
    subtitle_a, subtitle_b = split_subtitle(CONFIG["subtitle"])
    category = CONFIG["category"]
    spec_text = f"规格：{CONFIG['spec']}"
    spec_x, spec_y, spec_w, spec_text_x, spec_size = detail_spec_layout(category, spec_text)
    detail_spec = CONFIG.get("detail_spec", {})
    spec_y = detail_spec.get("y", spec_y)
    spec_text_y = detail_spec.get("text_y", 443)
    detail_text = CONFIG.get("detail_text", {})
    category_y = detail_text.get("category_y", 448)
    callout = CONFIG.get("detail_callout", {"x": 236, "y": 1662, "angle": 50})
    top_left = CONFIG["top_left"]
    top_right = CONFIG["top_right"]
    left_scale = top_left["size"] / 350
    right_scale = top_right["size"] / 350
    corner = CONFIG["corner"]
    big = CONFIG["big"]
    detail_height = CONFIG.get("detail_height", 3591)
    corner_img_w = corner["w"] * corner["scale"]
    corner_img_h = corner_img_w * RATIO_H_OVER_W
    corner_img_x, corner_img_y, corner_img_w2, corner_img_h2 = embedded(
        (corner["w"] - corner_img_w) / 2,
        corner["h"] * -0.02,
        corner_img_w,
        corner_img_h,
    )
    big_img_x, big_img_y, big_img_w, big_img_h = embedded(0, 0, big["w"], big["w"] * RATIO_H_OVER_W)
    top_base_w = 350
    top_base_h = top_base_w * RATIO_H_OVER_W
    top_img_x, top_img_y, top_img_w, top_img_h = embedded(0, 0, top_base_w, top_base_h)

    return f'''<svg width="1000" height="{detail_height}" viewBox="0 0 1000 {detail_height}" role="img" aria-label="泡袋详情页预览" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="detailBagShadow" x="-28%" y="-18%" width="160%" height="145%">
      <feDropShadow dx="0" dy="22" stdDeviation="18" flood-color="#111820" flood-opacity="0.18" />
      <feDropShadow dx="-5" dy="6" stdDeviation="7" flood-color="#111820" flood-opacity="0.1" />
    </filter>
    <filter id="detailSliceShadow" x="-20%" y="-20%" width="150%" height="150%">
      <feDropShadow dx="0" dy="16" stdDeviation="14" flood-color="#111820" flood-opacity="0.16" />
    </filter>
    <clipPath id="detailCornerClip" clipPathUnits="userSpaceOnUse">
      <path d="{notched_clip_path(corner['w'], corner['h'], round(min(corner['w'], corner['h']) * 0.075))}" />
    </clipPath>
    <mask id="detailFullMask" maskUnits="userSpaceOnUse" x="-2000" y="-2000" width="6000" height="8000">
      <rect x="0" y="0" width="{top_base_w}" height="{top_base_h:.2f}" rx="28" fill="#fff" />
      <polygon points="{notch_points(0, 0, top_base_w)}" fill="#000" />
    </mask>
    <mask id="detailCornerMask" maskUnits="userSpaceOnUse" x="-2000" y="-2000" width="6000" height="8000">
      <rect x="0" y="0" width="{corner['w']}" height="{corner['h']}" rx="{round(min(corner['w'], corner['h']) * 0.075)}" fill="#fff" />
      <polygon points="{notch_points(0, 0, corner['w'])}" fill="#000" />
    </mask>
    <mask id="detailBigMask" maskUnits="userSpaceOnUse" x="-2000" y="-2000" width="6000" height="8000">
      <rect x="0" y="0" width="{big['w']}" height="{big['w'] * RATIO_H_OVER_W:.2f}" rx="{round(big['w'] * 0.08)}" fill="#fff" />
      <polygon points="{notch_points(0, 0, big['w'])}" fill="#000" />
    </mask>
    <clipPath id="detailBigClip" clipPathUnits="userSpaceOnUse">
      <path d="{notched_clip_path(big['w'], big['w'] * RATIO_H_OVER_W, round(big['w'] * 0.08))}" />
    </clipPath>
  </defs>
  <rect width="1000" height="{detail_height}" fill="{BACKGROUND}" />
  <g transform="translate({top_left['x']} {top_left['y']}) scale({left_scale})" filter="url(#detailBagShadow)">
    <image href="{image_href}" x="{top_img_x:.2f}" y="{top_img_y:.2f}" width="{top_img_w:.2f}" height="{top_img_h:.2f}" preserveAspectRatio="none" mask="url(#detailFullMask)" />
  </g>
  <g font-family="{font_family()}">
    <text x="530" y="178" font-size="86" font-weight="900" fill="#050505">{esc(subtitle_a)}</text>
    <text x="530" y="292" font-size="86" font-weight="900" fill="#050505">{esc(subtitle_b)}</text>
    <text x="530" y="384" font-size="44" font-weight="800" fill="#6d7178">编号：{esc(code)}</text>
    <text x="530" y="{category_y}" font-size="36" font-weight="900" fill="#6a6d73">{esc(category)}</text>
    <rect x="{spec_x:.2f}" y="{spec_y}" width="{spec_w:.2f}" height="28" rx="3" fill="{BACKGROUND}" stroke="#9fa4aa" />
    <text x="{spec_text_x:.2f}" y="{spec_text_y}" font-size="{spec_size}" font-weight="700" fill="#62666e" text-anchor="middle">{esc(spec_text)}</text>
  </g>
  <g transform="translate({top_right['x']} {top_right['y']}) scale({right_scale})" filter="url(#detailBagShadow)">
    <image href="{image_href}" x="{top_img_x:.2f}" y="{top_img_y:.2f}" width="{top_img_w:.2f}" height="{top_img_h:.2f}" preserveAspectRatio="none" mask="url(#detailFullMask)" />
  </g>
  <g transform="translate({big['x']} {big['y']}) rotate({big['angle']})" filter="url(#detailSliceShadow)" clip-path="url(#detailBigClip)">
    <image href="{image_href}" x="{big_img_x:.2f}" y="{big_img_y:.2f}" width="{big_img_w:.2f}" height="{big_img_h:.2f}" preserveAspectRatio="none" />
  </g>
  <g transform="translate({corner['x']} {corner['y']}) rotate({corner['angle']})" filter="url(#detailSliceShadow)" clip-path="url(#detailCornerClip)">
    <image href="{image_href}" x="{corner_img_x:.2f}" y="{corner_img_y:.2f}" width="{corner_img_w2:.2f}" height="{corner_img_h2:.2f}" preserveAspectRatio="none" />
  </g>
  <g transform="translate({callout['x']} {callout['y']}) rotate({callout['angle']})" font-family="{font_family()}">
    <text x="0" y="0" font-size="56" font-weight="900" fill="#777d84">易撕拉满！！</text>
    <text x="-28" y="72" font-size="70" font-weight="900" fill="#050505">边缘开口设计</text>
  </g>
</svg>'''


def render_svg(svg_text, output_png, keep_svg=False):
    output_png.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        svg_path = Path(tmp) / f"{output_png.stem}.svg"
        svg_path.write_text(svg_text, encoding="utf-8")
        subprocess.run(["node", str(RENDERER), str(svg_path), str(output_png)], cwd=str(ROOT), check=True)
        if keep_svg:
            shutil.copy2(svg_path, output_png.with_suffix(".svg"))


def generate_one(input_path, output_root, code, title, keep_svg=False):
    title = title or CONFIG["color_name"]
    output_root.mkdir(parents=True, exist_ok=True)
    image_href = image_data_uri(input_path)
    safe_code = sanitize_name(code)
    standard_path = output_root / f"{safe_code}-standard.png"
    main_path = output_root / f"{safe_code}-泡袋主图.png"
    detail_path = output_root / f"{safe_code}-泡袋详情页.png"

    shutil.copy2(input_path, standard_path)
    render_svg(main_svg(image_href, code, title), main_path, keep_svg)
    render_svg(detail_svg(image_href, code, title), detail_path, keep_svg)
    return standard_path, main_path, detail_path


def main():
    parser = argparse.ArgumentParser(description="批量生成泡袋主图和详情页，使用网页同款 SVG 模板和 resvg 渲染")
    parser.add_argument("--input", required=True, help="单张 PNG 或 PNG 文件夹")
    parser.add_argument("--output", default="batch-output", help="输出文件夹")
    parser.add_argument("--start", required=True, help="起始编码，例如 SJ01001")
    parser.add_argument("--title", help="统一标题；不填则使用网页版默认标题")
    parser.add_argument("--title-from-filename", action="store_true", help="多张批量时用文件名作为标题")
    parser.add_argument("--template", default="rock-tea", help="模板：rock-tea/岩茶 或 black-tea/红茶")
    parser.add_argument("--keep-svg", action="store_true", help="同时保留中间 SVG，便于检查")
    args = parser.parse_args()
    template_key = apply_template(args.template)

    output_root = Path(args.output)
    files = input_files(args.input)
    if not files:
        raise SystemExit("没有找到 PNG 图片")

    results = []
    for index, input_path in enumerate(files):
        code = next_code(args.start, index)
        title = input_path.stem if args.title_from_filename else args.title
        results.append(generate_one(input_path, output_root, code, title, args.keep_svg))

    print(f"OK {output_root} template={template_key} spec={CONFIG['spec']}")
    for standard_path, main_path, detail_path in results:
        print(f"  {standard_path.name}")
        print(f"  {main_path.name}")
        print(f"  {detail_path.name}")


if __name__ == "__main__":
    main()
