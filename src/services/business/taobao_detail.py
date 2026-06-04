"""Taobao detail-page export service."""

from __future__ import annotations

import html
import io
import json
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont
from src.core.config import get_config
from src.utils import get_logger

from .products import get_product_service


logger = get_logger("sjagent.taobao_detail")

ImageFetcher = Callable[[str], bytes]
DimensionRecognizer = Callable[[list[str]], dict]

DETAIL_IMAGE_WIDTH = 750
DETAIL_IMAGE_HEIGHT = 1122
DETAIL_IMAGE_COUNT = 4
FIXED_PROCESS = ["礼盒：全彩UV工艺制作", "提袋：丝网印刷制作"]
FIXED_ACCESSORIES = "礼盒、手提袋、礼盒膜"


@dataclass
class TaobaoDetailExportResult:
    filename: str
    content: bytes
    template_image_urls: list[str]
    detail_image_urls: list[str]
    dimensions: dict


def _unique(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _json_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return _unique(value)
    if isinstance(value, tuple):
        return _unique(value)
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return _unique(parsed)
        except Exception:
            pass
    return [text]


def _image_extension(url: str, content_type: str = "") -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    content = str(content_type or "").lower()
    if "png" in content:
        return ".png"
    if "webp" in content:
        return ".webp"
    if "bmp" in content:
        return ".bmp"
    return ".jpg"


def _safe_zip_name(value: str, fallback: str) -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n]+', "-", str(value or "").strip()).strip(" .")
    return text or fallback


def _download_image(url: str) -> bytes:
    response = requests.get(
        url,
        timeout=25,
        headers={"User-Agent": "sjagent-taobao-detail/1.0"},
    )
    response.raise_for_status()
    content_type = str(response.headers.get("Content-Type") or "")
    if content_type and not content_type.lower().split(";", 1)[0].startswith("image/"):
        raise ValueError(f"图片响应类型无效: {url}")
    return response.content


def _font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if weight == "bold" else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf" if weight == "bold" else "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if weight == "bold" else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        try:
            if path and Path(path).exists():
                return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_lines(draw: ImageDraw.ImageDraw, xy: tuple[int, int], lines: Iterable[str], *, font, fill="#111", line_gap=10) -> int:
    x, y = xy
    for line in lines:
        text = str(line or "").strip()
        if not text:
            continue
        draw.text((x, y), text, font=font, fill=fill)
        bbox = draw.textbbox((x, y), text, font=font)
        y = bbox[3] + line_gap
    return y


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    clean = str(text or "").strip()
    if not clean:
        return []
    lines: list[str] = []
    current = ""
    for char in clean:
        candidate = f"{current}{char}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def _dimension_text(dimensions: dict) -> str:
    text = str(dimensions.get("text") or "").strip()
    if text:
        return text
    parts = [dimensions.get("length"), dimensions.get("width"), dimensions.get("height")]
    parts = [str(item or "").strip() for item in parts if str(item or "").strip()]
    return " × ".join(parts)


def _dimension_from_text(text: str) -> dict:
    clean = str(text or "").upper().replace("厘米", "CM").replace("公分", "CM")
    pattern = re.compile(
        r"(?P<l>\d+(?:\.\d+)?)\s*(?:CM|厘米|公分)?\s*[X×*＊]\s*"
        r"(?P<w>\d+(?:\.\d+)?)\s*(?:CM|厘米|公分)?\s*[X×*＊]\s*"
        r"(?P<h>\d+(?:\.\d+)?)\s*(?:CM|厘米|公分)?",
        re.I,
    )
    match = pattern.search(clean)
    if not match:
        return {}
    length = match.group("l")
    width = match.group("w")
    height = match.group("h")
    return {
        "length": f"{length}CM",
        "width": f"{width}CM",
        "height": f"{height}CM",
        "text": f"{length}×{width}×{height}CM",
    }


def recognize_dimensions_from_images(image_urls: list[str], image_fetcher: ImageFetcher = _download_image) -> dict:
    """Recognize only product size text from product images via OCR."""
    try:
        from scripts.image_processor import ImageProcessor
    except Exception as exc:
        logger.warning(f"尺寸识别 OCR 初始化失败: {exc}")
        return {}

    processor = ImageProcessor()
    with tempfile.TemporaryDirectory(prefix="taobao_detail_ocr_") as tmp_dir:
        for index, url in enumerate(_unique(image_urls)[:8], start=1):
            try:
                data = image_fetcher(url)
                path = Path(tmp_dir) / f"source_{index}.jpg"
                path.write_bytes(data)
                image = processor._load_image(str(path))
                _results, text = processor.ocr_recognize(image, top_ratio=1.0)
                parsed = _dimension_from_text(text)
                if parsed:
                    parsed["source_url"] = url
                    return parsed
            except Exception as exc:
                logger.info(f"尺寸识别跳过图片: url={url}, error={exc}")
    return {}


class TaobaoDetailExportService:
    def __init__(
        self,
        *,
        product_service=None,
        uploader=None,
        image_fetcher: ImageFetcher = _download_image,
        dimension_recognizer: DimensionRecognizer | None = None,
    ):
        self.product_service = product_service or get_product_service()
        self.uploader = uploader
        self.image_fetcher = image_fetcher
        self.dimension_recognizer = dimension_recognizer or (
            lambda urls: recognize_dimensions_from_images(urls, image_fetcher=self.image_fetcher)
        )

    def export_zip(self, product_id: int) -> TaobaoDetailExportResult:
        product = self.product_service.info(product_id)
        if not product:
            raise ValueError("商品不存在")

        main_assets = self._media_assets(product, "main_image")
        color_assets = self._media_assets(product, "color_image")
        detail_assets = self._media_assets(product, "detail_image")
        main_urls = _unique([item.get("url") for item in main_assets])
        if not main_urls:
            main_urls = _unique(_json_list(product.get("main_images_list")) + [product.get("images")])
        color_items = self._color_items(color_assets, product)
        detail_urls = _unique([item.get("url") for item in detail_assets] + _json_list(product.get("detail_image_urls")))
        recognition_urls = _unique(main_urls + [item["url"] for item in color_items] + detail_urls)
        dimensions = dict(self.dimension_recognizer(recognition_urls) or {})
        if not _dimension_text(dimensions):
            fallback = _dimension_from_text(product.get("size_label") or product.get("title") or "")
            dimensions.update(fallback)

        template_paths = self._render_template_images(product, color_items, dimensions)
        try:
            template_urls = self._upload_template_images(template_paths)
        finally:
            self._cleanup_template_paths(template_paths)
        detail_html = self._detail_html(template_urls, detail_urls, dimensions)
        filename = f"{_safe_zip_name(product.get('title') or product.get('name') or '商品', '商品')}-淘宝详情页.zip"
        content = self._zip_package(filename, main_urls, color_items, detail_html)
        return TaobaoDetailExportResult(
            filename=filename,
            content=content,
            template_image_urls=template_urls,
            detail_image_urls=detail_urls,
            dimensions=dimensions,
        )

    def _media_assets(self, product: dict, media_type: str) -> list[dict]:
        return self.product_service.media_assets(
            spu_id=int(product.get("spu_id") or 0) or None,
            sku_ids=[int(product.get("id") or product.get("product_id") or 0)] if product.get("id") else None,
            media_type=media_type,
            include_pending=False,
            limit=6000,
        )

    def _color_items(self, color_assets: list[dict], product: dict) -> list[dict]:
        items: list[dict] = []
        for index, asset in enumerate(color_assets, start=1):
            url = str(asset.get("url") or "").strip()
            if not url:
                continue
            color = str(asset.get("sku_color") or asset.get("color") or "").strip()
            if not color:
                colors = product.get("available_colors") or []
                color = str(colors[index - 1]).strip() if index <= len(colors) else f"颜色{index}"
            items.append({"url": url, "color": color, "index": index})
        seen: set[str] = set()
        unique_items: list[dict] = []
        for item in items:
            key = item["url"]
            if key in seen:
                continue
            seen.add(key)
            unique_items.append(item)
        return unique_items

    def _render_template_images(self, product: dict, color_items: list[dict], dimensions: dict) -> list[Path]:
        base = Path(tempfile.mkdtemp(prefix="taobao_detail_render_"))
        paths = []
        section_drawers = [
            self._draw_product_params,
            self._draw_dimension_section,
            self._draw_customization_section,
            self._draw_instruction_section,
        ]
        for index, drawer in enumerate(section_drawers, start=1):
            image = Image.new("RGB", (DETAIL_IMAGE_WIDTH, DETAIL_IMAGE_HEIGHT), "#f8f8f8")
            draw = ImageDraw.Draw(image)
            drawer(draw, product, color_items, dimensions)
            path = base / f"taobao-detail-{index}.jpg"
            image.save(path, "JPEG", quality=92, optimize=True)
            paths.append(path)
        return paths

    def _draw_header(self, draw: ImageDraw.ImageDraw, title_lines: list[str], english: list[str] | None = None):
        if english:
            _draw_lines(draw, (48, 54), english, font=_font(30, "bold"), fill="#111", line_gap=4)
        _draw_lines(draw, (48, 170 if english else 68), title_lines, font=_font(48, "bold"), fill="#111", line_gap=8)
        draw.line((48, 300, DETAIL_IMAGE_WIDTH - 48, 300), fill="#d8d8d8", width=3)

    def _draw_field(self, draw, label: str, value: str | list[str], x: int, y: int, width: int = 290):
        label_font = _font(22)
        value_font = _font(28, "bold")
        draw.text((x, y), label, font=label_font, fill="#555")
        lines = value if isinstance(value, list) else [value]
        line_y = y + 44
        for raw in lines:
            for line in _wrap_text(draw, str(raw or ""), value_font, width):
                draw.text((x, line_y), line, font=value_font, fill="#050505")
                line_y += 38

    def _draw_product_params(self, draw, product: dict, color_items: list[dict], dimensions: dict):
        self._draw_header(draw, ["产品参数", "详情请阅读"], ["PACKAGING DETAILS", "PRODUCT PROFILE"])
        colors = _unique([item.get("color") for item in color_items] + _json_list(product.get("available_colors")))
        colors_text = " / ".join(colors) if colors else str(product.get("color_text") or product.get("color") or "")
        self._draw_field(draw, "产品名称", str(product.get("title") or product.get("name") or "商品"), 48, 350, 360)
        self._draw_field(draw, "产品规格", str(product.get("piece_text") or product.get("simple_desc") or ""), 455, 350, 210)
        self._draw_field(draw, "可装容量", self._capacity_lines(product), 48, 555, 310)
        self._draw_field(draw, "制作工艺", FIXED_PROCESS, 455, 555, 230)
        self._draw_field(draw, "产品尺寸", _dimension_text(dimensions), 48, 775, 310)
        self._draw_field(draw, "产品颜色", colors_text, 455, 775, 230)
        self._draw_field(draw, "产品配件", FIXED_ACCESSORIES, 48, 965, 560)

    def _draw_dimension_section(self, draw, product: dict, color_items: list[dict], dimensions: dict):
        self._draw_header(draw, ["产品尺寸", "规格信息"], ["PRODUCT SIZE", "SPECIFICATION"])
        self._draw_field(draw, "尺寸", _dimension_text(dimensions) or "请以实物为准", 48, 350, 520)
        self._draw_field(draw, "件规", str(product.get("piece_text") or product.get("simple_desc") or ""), 48, 515, 520)
        self._draw_field(draw, "颜色", " / ".join(_unique([item.get("color") for item in color_items])), 48, 680, 520)
        note_font = _font(22)
        notes = [
            "* 本产品符合新规包装空隙率标准",
            "* 尺寸信息由商品图片标注识别，实际以实物为准",
        ]
        y = 880
        for note in notes:
            draw.text((48, y), note, font=note_font, fill="#222")
            y += 42

    def _draw_customization_section(self, draw, product: dict, color_items: list[dict], dimensions: dict):
        self._draw_header(draw, ["可定制范围", "免费排版设计"], ["CUSTOM SERVICE", "FREE LAYOUT"])
        box_font = _font(24, "bold")
        captions = [
            ("礼盒正面定制", 48, 370),
            ("礼盒背面定制", 390, 370),
            ("手提袋双面定制", 48, 690),
        ]
        for text, x, y in captions:
            draw.rectangle((x, y, x + 290, y + 210), outline="#000", width=2)
            draw.text((x + 58, y + 232), text, font=box_font, fill="#111")
        draw.text((390, 710), "可提供设计稿定制", font=_font(28, "bold"), fill="#111")
        _draw_lines(draw, (392, 760), ["支持格式：PNG、JPG、PSD、", "AI、PDF等设计软件格式。"], font=_font(20), fill="#111", line_gap=8)
        _draw_lines(draw, (392, 900), ["如盒子内小盒", "包含内小盒设计定制"], font=_font(26), fill="#111", line_gap=10)

    def _draw_instruction_section(self, draw, product: dict, color_items: list[dict], dimensions: dict):
        self._draw_header(draw, ["定制说明", "请您认真阅读"], ["CUSTOM NOTES", "PLEASE READ"])
        title_font = _font(24, "bold")
        text_font = _font(18)
        draw.text((48, 342), "关于颜色差异", font=title_font, fill="#111")
        color_text = (
            "色差客观存在。不同显示设备、材质、印刷工艺及拍摄光线会导致设计稿与实物存在合理色差，"
            "最终颜色效果以实际收到的实物为准。"
        )
        y = 390
        for line in _wrap_text(draw, color_text, text_font, 640):
            draw.text((48, y), line, font=text_font, fill="#111")
            y += 28
        draw.line((48, 560, DETAIL_IMAGE_WIDTH - 48, 560), fill="#d8d8d8", width=2)
        draw.text((48, 610), "设计稿信息核对责任", font=title_font, fill="#111")
        proof_text = (
            "请在提交生产前仔细核对文字、图案、排版、规格、颜色等信息。我们将按照最终确认的设计稿生产，"
            "因设计稿本身错误造成的损失由客户自行承担。"
        )
        y = 660
        for line in _wrap_text(draw, proof_text, text_font, 640):
            draw.text((48, y), line, font=text_font, fill="#111")
            y += 28
        draw.line((48, 940, DETAIL_IMAGE_WIDTH - 48, 940), fill="#d8d8d8", width=2)
        _draw_lines(draw, (48, 985), ["产品展示", "专注品质包装"], font=_font(40, "bold"), fill="#111", line_gap=8)

    def _capacity_lines(self, product: dict) -> list[str]:
        text = str(product.get("size_label") or "").strip()
        if text:
            return [text]
        piece = str(product.get("piece_text") or product.get("simple_desc") or "").strip()
        return [piece] if piece else ["按商品规格页为准"]

    def _upload_template_images(self, paths: list[Path]) -> list[str]:
        uploader = self.uploader
        if uploader is None:
            from scripts.oss_uploader import OSSUploader

            uploader = OSSUploader(get_config().oss_config)
        urls: list[str] = []
        for path in paths:
            result = uploader.upload(str(path))
            if not isinstance(result, dict) or result.get("error"):
                raise RuntimeError(f"淘宝详情页模板图上传失败: {result}")
            url = str(result.get("url") or result.get("full_url") or result.get("images") or result.get("path") or "").strip()
            if not url:
                raise RuntimeError("淘宝详情页模板图上传未返回 URL")
            urls.append(url)
        return urls

    def _cleanup_template_paths(self, paths: list[Path]) -> None:
        directories: set[Path] = set()
        for path in paths:
            directories.add(path.parent)
            try:
                path.unlink(missing_ok=True)
            except Exception as exc:
                logger.info(f"淘宝详情页临时图清理跳过: path={path}, error={exc}")
        for directory in directories:
            try:
                directory.rmdir()
            except Exception:
                pass

    def _detail_html(self, template_urls: list[str], detail_urls: list[str], dimensions: dict) -> str:
        lines = [
            "<!-- 北极星淘宝详情页导出代码：复制到淘宝详情页源码区域 -->",
            f"<!-- 尺寸识别：{html.escape(_dimension_text(dimensions) or '未识别到尺寸')} -->",
        ]
        for url in _unique(template_urls + detail_urls):
            clean = html.escape(url, quote=True)
            lines.append(f'<p><img src="{clean}" style="display:block;width:100%;height:auto;" /></p>')
        return "\n".join(lines) + "\n"

    def _zip_package(self, filename: str, main_urls: list[str], color_items: list[dict], detail_html: str) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("detail.html", detail_html.encode("utf-8"))
            for index, url in enumerate(main_urls, start=1):
                self._write_image(archive, url, f"主图/main-{index}")
            for index, item in enumerate(color_items, start=1):
                color = _safe_zip_name(item.get("color") or f"颜色{index}", f"颜色{index}")
                self._write_image(archive, item["url"], f"颜色图/{color}-{index}")
        return buffer.getvalue()

    def _write_image(self, archive: zipfile.ZipFile, url: str, stem: str) -> None:
        data = self.image_fetcher(url)
        suffix = _image_extension(url)
        safe_parts = [
            _safe_zip_name(part, f"image-{index}")
            for index, part in enumerate(stem.split("/"), start=1)
        ]
        safe_stem = "/".join(safe_parts)
        archive.writestr(f"{safe_stem}{suffix}", data)
