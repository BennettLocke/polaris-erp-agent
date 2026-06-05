"""Taobao detail-page export service."""

from __future__ import annotations

import html
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

import requests

from src.core.config import get_config
from src.utils import get_logger

from .products import get_product_service


logger = get_logger("sjagent.taobao_detail")

ImageFetcher = Callable[[str], bytes]
DimensionRecognizer = Callable[[list[str]], dict]

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_PATH = ROOT / "assets" / "taobao_detail" / "default-product-data.json"
TEMPLATE_PATH = ROOT / "assets" / "taobao_detail" / "detail-template.html"
RENDER_SCRIPT_PATH = ROOT / "scripts" / "taobao_detail" / "render_taobao_detail.mjs"

TAOBAO_IMAGE_WIDTH = 750
DETAIL_SLICE_NAMES = [
    "detail-01.jpg",
    "detail-02.jpg",
    "detail-03.jpg",
    "detail-04.jpg",
    "detail-05.jpg",
]
FIXED_CAPACITY = [
    "15CM款岩茶泡袋：30泡",
    "11CM款红茶泡袋：50泡",
]
FIXED_PROCESS = ["礼盒：全彩UV工艺制作", "提袋：丝网印刷制作"]
FIXED_ACCESSORIES = "礼盒、手提袋、礼盒膜"
TAOBAO_DETAIL_NAME_SUFFIX = "茶叶礼盒（空）"


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


def _taobao_detail_product_name(product: dict) -> str:
    raw = str(product.get("title") or product.get("name") or "商品").strip()
    match = re.match(r"^[【\[]\s*(?P<brand>[^】\]]+?)\s*[】\]]\s*(?P<spec>.*)$", raw)
    if match:
        base = f"{match.group('brand')}{match.group('spec')}"
    else:
        base = raw
    base = re.sub(r"\s+", "", base)
    base = re.sub(r"[【】\[\]]+", "", base)
    base = re.sub(r"(?:茶叶)?(?:包装)?礼盒(?:（空）)?$", "", base).strip()
    base = re.sub(r"（空）$", "", base).strip()
    return f"{base or '商品'}{TAOBAO_DETAIL_NAME_SUFFIX}"


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


def _strip_dimension_unit(value: Any) -> str:
    text = str(value or "").strip().upper()
    return re.sub(r"\s*(?:CM|厘米|公分)\s*$", "", text, flags=re.I).strip()


def _dimension_from_text(text: str) -> dict:
    clean = (
        str(text or "")
        .upper()
        .replace("厘米", "CM")
        .replace("公分", "CM")
        .replace("×", "X")
        .replace("＊", "*")
    )
    pattern = re.compile(
        r"(?P<l>\d+(?:\.\d+)?)\s*(?:CM)?\s*[X*]\s*"
        r"(?P<w>\d+(?:\.\d+)?)\s*(?:CM)?\s*[X*]\s*"
        r"(?P<h>\d+(?:\.\d+)?)\s*(?:CM)?",
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


def _dimension_text(dimensions: dict) -> str:
    text = str(dimensions.get("text") or "").strip()
    if text:
        parsed = _dimension_from_text(text)
        return str(parsed.get("text") or text.replace("X", "×").replace("x", "×")).strip()
    length = _strip_dimension_unit(dimensions.get("length"))
    width = _strip_dimension_unit(dimensions.get("width"))
    height = _strip_dimension_unit(dimensions.get("height"))
    if length and width and height:
        return f"{length}×{width}×{height}CM"
    return ""


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


class OriginalTaobaoDetailRenderer:
    """Render the original Taobao detail HTML template into the 5 fixed JPG slices."""

    def __init__(
        self,
        *,
        node_command: str = "node",
        script_path: Path = RENDER_SCRIPT_PATH,
        template_path: Path = TEMPLATE_PATH,
    ):
        self.node_command = node_command
        self.script_path = Path(script_path)
        self.template_path = Path(template_path)

    def render(self, product_data: dict) -> list[Path]:
        if not self.script_path.exists():
            raise RuntimeError(f"淘宝详情页渲染脚本不存在: {self.script_path}")
        if not self.template_path.exists():
            raise RuntimeError(f"淘宝详情页模板不存在: {self.template_path}")

        output_dir = Path(tempfile.mkdtemp(prefix="taobao_detail_render_"))
        data_path = output_dir / "product-data.json"
        render_data = {key: value for key, value in product_data.items() if not str(key).startswith("_")}
        data_path.write_text(json.dumps(render_data, ensure_ascii=False, indent=2), encoding="utf-8")

        command = [
            self.node_command,
            str(self.script_path),
            str(data_path),
            str(self.template_path),
            str(output_dir),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=str(ROOT),
                env=os.environ.copy(),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=120,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    "淘宝详情页渲染失败: "
                    f"stdout={completed.stdout.strip()} stderr={completed.stderr.strip()}"
                )
            paths = [output_dir / name for name in DETAIL_SLICE_NAMES]
            missing = [str(path) for path in paths if not path.exists()]
            if missing:
                raise RuntimeError(f"淘宝详情页渲染缺少切片: {', '.join(missing)}")
            return paths
        except Exception:
            shutil.rmtree(output_dir, ignore_errors=True)
            raise


class TaobaoDetailExportService:
    def __init__(
        self,
        *,
        product_service=None,
        uploader=None,
        renderer: OriginalTaobaoDetailRenderer | None = None,
        image_fetcher: ImageFetcher = _download_image,
        dimension_recognizer: DimensionRecognizer | None = None,
    ):
        self.product_service = product_service or get_product_service()
        self.uploader = uploader
        self.renderer = renderer or OriginalTaobaoDetailRenderer()
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

        template_data = self._template_data(product, color_items, dimensions)
        template_paths = self.renderer.render(template_data)
        try:
            template_urls = self._upload_detail_images(template_paths)
        finally:
            self._cleanup_render_paths(template_paths)

        detail_html = self._detail_html(template_urls, detail_urls)
        filename = f"{_safe_zip_name(product.get('title') or product.get('name') or '商品', '商品')}-淘宝详情页.zip"
        content = self._zip_package(main_urls, color_items, detail_html)
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

    def _template_data(self, product: dict, color_items: list[dict], dimensions: dict) -> dict:
        data = self._default_template_data()
        product_data = dict(data.get("product") or {})
        dimension_data = dict(data.get("dimensions") or {})

        colors = _unique(
            [item.get("color") for item in color_items]
            + _json_list(product.get("available_colors"))
            + [product.get("color_text"), product.get("color")]
        )
        size_text = _dimension_text(dimensions)
        if not size_text:
            size_text = str(product.get("size_label") or "").strip()
        if not size_text:
            size_text = "请以实物为准"

        parsed_dimensions = _dimension_from_text(size_text)
        dimension_data.update({
            "length": parsed_dimensions.get("length") or str(dimensions.get("length") or "").strip(),
            "width": parsed_dimensions.get("width") or str(dimensions.get("width") or "").strip(),
            "height": parsed_dimensions.get("height") or str(dimensions.get("height") or "").strip(),
            "note": str(dimension_data.get("note") or "*本产品符合新规包装空隙率标准"),
        })

        product_data.update({
            "name": _taobao_detail_product_name(product),
            "spec": self._spec_text(product),
            "capacity": FIXED_CAPACITY,
            "process": FIXED_PROCESS,
            "size": size_text,
            "colors": "/".join(colors) if colors else "默认颜色",
            "accessories": FIXED_ACCESSORIES,
        })
        data["product"] = product_data
        data["dimensions"] = dimension_data
        data.setdefault("page", {})
        data["page"]["width"] = 800
        data["page"]["taobaoWidth"] = TAOBAO_IMAGE_WIDTH
        return data

    def _default_template_data(self) -> dict:
        if not DEFAULT_DATA_PATH.exists():
            raise RuntimeError(f"淘宝详情页默认数据不存在: {DEFAULT_DATA_PATH}")
        return json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))

    def _spec_text(self, product: dict) -> str:
        for key in ("piece_text", "simple_desc", "spec"):
            text = str(product.get(key) or "").strip()
            if text:
                return text
        case_pack = str(product.get("case_pack_qty") or "").strip()
        if case_pack:
            return f"1件{case_pack}套"
        return "按商品规格页为准"

    def _upload_detail_images(self, paths: list[Path]) -> list[str]:
        uploader = self.uploader
        if uploader is None:
            from scripts.oss_uploader import OSSUploader

            uploader = OSSUploader(get_config().oss_config)
        urls: list[str] = []
        for path in paths:
            result = uploader.upload(str(path))
            if not isinstance(result, dict) or result.get("error"):
                raise RuntimeError(f"淘宝详情页切片上传失败: {result}")
            url = str(result.get("url") or result.get("full_url") or result.get("images") or result.get("path") or "").strip()
            if not url:
                raise RuntimeError("淘宝详情页切片上传未返回 URL")
            urls.append(url)
        return urls

    def _cleanup_render_paths(self, paths: list[Path]) -> None:
        directories: set[Path] = set()
        for path in paths:
            directories.add(path.parent)
            try:
                path.unlink(missing_ok=True)
            except Exception as exc:
                logger.info(f"淘宝详情页临时图清理跳过: path={path}, error={exc}")
        for directory in directories:
            if directory.exists() and directory.name.startswith("taobao_detail_render_"):
                shutil.rmtree(directory, ignore_errors=True)

    def _detail_html(self, template_urls: list[str], detail_urls: list[str]) -> str:
        lines = [f'<div style="width:{TAOBAO_IMAGE_WIDTH}px;margin:0 auto;padding:0;background:#ffffff;">']
        for index, url in enumerate(_unique(template_urls), start=1):
            clean = html.escape(url, quote=True)
            lines.append(
                f'  <img src="{clean}" alt="礼盒详情页{index:02d}" '
                f'style="display:block;width:{TAOBAO_IMAGE_WIDTH}px;height:auto;margin:0;padding:0;border:0;">'
            )
        for index, url in enumerate(_unique(detail_urls), start=1):
            clean = html.escape(url, quote=True)
            lines.append(
                f'  <img src="{clean}" alt="商品详情图{index:02d}" '
                f'style="display:block;width:{TAOBAO_IMAGE_WIDTH}px;height:auto;margin:0;padding:0;border:0;">'
            )
        lines.append("</div>")
        return "\n".join(lines) + "\n"

    def _zip_package(self, main_urls: list[str], color_items: list[dict], detail_html: str) -> bytes:
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
