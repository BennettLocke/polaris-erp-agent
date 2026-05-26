"""泡袋新品上传流程。

当前只实现前置测试阶段：收集模板、商品名、图片，并按商品库的 SJ 自动编号规则生成预览，
不真正创建/上传商品。
"""
from __future__ import annotations

import html
import os
import posixpath
import re
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.services.business import get_product_service
from src.skills.base import BaseWorkflow
from src.utils import get_logger

logger = get_logger("sjagent.skills.bag_upload")


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BAG_TEMPLATE_DIR = PROJECT_ROOT / "scripts" / "bag_template"
BAG_PREPARE_SCRIPT = BAG_TEMPLATE_DIR / "prepare_bag_image_v2.py"
BAG_GENERATE_SCRIPT = BAG_TEMPLATE_DIR / "batch_generate.py"
BAG_GENERATED_DIR = PROJECT_ROOT / "data" / "generated" / "bag_upload"
WEB_IMAGE_DIR = PROJECT_ROOT / "data" / "uploads"
BAG_DEFAULT_PRICE = 18
BAG_UPLOAD_WORKERS = max(1, min(4, int(os.environ.get("BAG_UPLOAD_WORKERS", "3") or 3)))


BAG_TYPES = {
    "岩茶": {
        "suffix": "长泡袋",
        "template": "岩茶泡袋模板",
        "render_template": "rock-tea",
        "target_width": 550,
        "target_height": 1500,
        "price": 18,
    },
    "红茶": {
        "suffix": "短泡袋",
        "template": "红茶泡袋模板",
        "render_template": "black-tea",
        "target_width": 520,
        "target_height": 1100,
        "price": 10,
    },
    "宽版": {
        "suffix": "宽版泡袋",
        "template": "宽版泡袋模板",
        "render_template": "rock-tea",
        "target_width": 550,
        "target_height": 1500,
        "price": 18,
    },
}

BAG_CATEGORIES = [
    ("肉桂", 7, "肉桂泡袋"),
    ("水仙", 6, "水仙泡袋"),
    ("大红袍", 5, "大红袍泡袋"),
    ("金骏眉", 12, "红茶泡袋"),
    ("小种", 12, "红茶泡袋"),
    ("红茶", 12, "红茶泡袋"),
]


class BagUploadWorkflow(BaseWorkflow):
    """上传泡袋新品的分步流程。"""

    def execute(self, user_input: str, params: dict = None) -> dict:
        params = params or {}
        bag_type = self._normalize_bag_type(params.get("bag_type") or user_input)
        if bag_type:
            return self._ask_archive(bag_type)
        return self._ask(
            "开始上传泡袋。这个泡袋是岩茶、红茶，还是宽版？",
            {"pending_action": "collect_bag_type"},
        )

    def resume(self, user_input: str, state: dict) -> dict:
        action = state.get("pending_action")

        if action == "collect_bag_type":
            bag_type = self._normalize_bag_type(user_input)
            if not bag_type:
                return self._ask(
                    "我需要先确定模板：这个泡袋是岩茶、红茶，还是宽版？",
                    {"pending_action": "collect_bag_type"},
                )
            return self._ask_archive(bag_type)

        if action == "collect_bag_archive":
            upload = self._extract_upload_path(user_input)
            if not upload:
                return self._ask(
                    "请上传一个 zip 压缩包，里面放要处理的 PNG 图片；每张图片的文件名会作为商品库标题。",
                    state,
                )
            try:
                result = self._process_batch_upload(upload, state)
            except Exception as e:
                logger.error(f"泡袋批量上传失败: {e}")
                return self._ask(
                    f"泡袋批量处理失败：{e}\n请检查压缩包里是否都是 PNG 图片，或重新上传。",
                    state,
                )
            return self._reply(self._batch_done_text(result))

        if action == "collect_bag_name":
            name = self._clean_product_name(user_input)
            if not name:
                return self._ask(
                    "这个新品泡袋叫什么名字？例如：虎啸岩肉桂。",
                    state,
                )
            next_state = {**state, "product_name": name}
            category = self._classify_category(name, state.get("bag_type"))
            if not category:
                next_state["pending_action"] = "collect_bag_category"
                return self._ask(
                    f"“{name}”我还不能确定分类，请告诉我是肉桂泡袋、水仙泡袋、大红袍泡袋、红茶泡袋，还是宽版泡袋？",
                    next_state,
                )
            next_state.update(category)
            return self._ask_image(next_state)

        if action == "collect_bag_category":
            category = self._category_from_text(user_input)
            if not category:
                return self._ask(
                    "分类还没识别到，请直接说：肉桂泡袋、水仙泡袋、大红袍泡袋、红茶泡袋，或宽版泡袋。",
                    state,
                )
            next_state = {**state, **category}
            return self._ask_image(next_state)

        if action == "collect_bag_image":
            image = self._extract_image_path(user_input)
            if not image:
                return self._ask(
                    "请把泡袋 PNG 图片发给我。当前先做本地流程测试，不会上传商品。",
                    state,
                )
            draft = self._build_draft({**state, "image_path": image})
            try:
                assets = self._generate_preview_assets(
                    image_path=image,
                    code=draft["coding_preview"],
                    title=draft.get("product_name") or "",
                    bag_type=state.get("bag_type") or "岩茶",
                )
            except Exception as e:
                logger.error(f"泡袋图片生成失败: {e}")
                return self._ask(
                    f"图片已收到，但生成泡袋主图/详情页失败：{e}\n请换一张 PNG 重新上传，或稍后让我检查脚本。",
                    {**state, "pending_action": "collect_bag_image", "image_path": image},
                )
            draft.update(assets)
            return self._ask(
                self._draft_text(draft),
                {**draft, "pending_action": "confirm_bag_product_draft"},
            )

        if action == "confirm_bag_product_draft":
            if self._is_confirm(user_input):
                return self._reply(self._test_done_text(state))
            if self._is_cancel(user_input):
                return self._reply("已取消泡袋新品上传流程。")
            return self._ask(
                "现在还是测试模式。确认这个泡袋新品资料没问题吗？回复“确认”结束前置测试，回复“取消”放弃。",
                state,
            )

        return self._reply("泡袋上传流程状态已失效，请重新说“开始上传泡袋”。")

    def _ask_name(self, bag_type: str) -> dict:
        return self._ask(
            f"已选择{bag_type}模板。这个新品泡袋叫什么名字？",
            {"pending_action": "collect_bag_name", "bag_type": bag_type},
        )

    def _ask_archive(self, bag_type: str) -> dict:
        meta = BAG_TYPES.get(bag_type, BAG_TYPES["岩茶"])
        return self._ask(
            f"已选择{bag_type}模板（{meta['suffix']}）。请上传 zip 压缩包，里面放多个 PNG；每个 PNG 文件名会作为商品库标题，默认售价 {self._bag_price(bag_type)} 元。",
            {"pending_action": "collect_bag_archive", "bag_type": bag_type},
        )

    def _ask_image(self, state: dict) -> dict:
        name = state.get("product_name") or ""
        category = state.get("category_name") or ""
        return self._ask(
            f"已识别：{name}，分类：{category}。请上传这个泡袋的 PNG 图片。",
            {**state, "pending_action": "collect_bag_image"},
        )

    def _build_draft(self, state: dict) -> dict:
        bag_type = state.get("bag_type") or "岩茶"
        meta = BAG_TYPES.get(bag_type, BAG_TYPES["岩茶"])
        name = state.get("product_name") or ""
        code = self._next_sj_code()
        title = f"【{code}】{name}-{meta['suffix']}"
        return {
            **state,
            "coding_preview": code,
            "title": title,
            "template_name": meta["template"],
            "suffix": meta["suffix"],
            "upload_enabled": False,
        }

    def _draft_text(self, draft: dict) -> str:
        image_name = Path(draft.get("image_path") or "").name or "已收到图片"
        return (
            "泡袋新品前置资料已收齐，当前是本地测试模式，暂不上传产品。\n\n"
            f"模板：{draft.get('template_name')}\n"
            f"商品名：{draft.get('product_name')}\n"
            f"分类：{draft.get('category_name')}（ID {draft.get('category_id')}）\n"
            f"预计编号：{draft.get('coding_preview')}（正式创建时仍由商品库自动生成）\n"
            f"预计标题：{draft.get('title')}\n"
            f"图片：{image_name}\n\n"
            f"标准图：{draft.get('standard_url')}\n"
            f"主图：{draft.get('main_url')}\n"
            f"详情页：{draft.get('detail_url')}\n\n"
            "确认后本轮只结束前置测试，不会写入商品库。"
        )

    def _test_done_text(self, state: dict) -> str:
        return (
            "泡袋新品前置流程测试完成。\n"
            f"商品：{state.get('title') or state.get('product_name')}\n"
            f"分类：{state.get('category_name')}\n"
            f"编号预览：{state.get('coding_preview')}\n"
            f"主图：{state.get('main_url')}\n"
            f"详情页：{state.get('detail_url')}\n"
            "目前没有上传产品；下一步可以接生成主图/详情图和商品库新建商品。"
        )

    def _process_batch_upload(self, upload_path: str, state: dict) -> dict:
        source = Path(str(upload_path).strip().strip('"'))
        if not source.exists():
            raise FileNotFoundError(f"找不到上传文件：{source}")

        bag_type = state.get("bag_type") or "岩茶"
        batch_id = f"batch-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        batch_dir = BAG_GENERATED_DIR / batch_id
        source_dir = batch_dir / "_source"
        source_dir.mkdir(parents=True, exist_ok=True)

        try:
            source_images = self._collect_batch_images(source, source_dir)
            if not source_images:
                raise ValueError("压缩包里没有找到 PNG 图片")

            tasks = []
            next_number = None
            suffix = BAG_TYPES.get(bag_type, BAG_TYPES["岩茶"])["suffix"]
            price = self._bag_price(bag_type)
            for index, item in enumerate(source_images, start=1):
                raw_title = item["title"]
                title = self._display_title_from_filename(raw_title)
                existing_code = self._extract_sj_code(raw_title)
                if existing_code:
                    code = existing_code
                else:
                    code = self._next_sj_code(next_number or 506)
                    next_number = int(code[2:]) + 1 if re.match(r"^SJ\d+$", code) else None
                tasks.append({
                    "index": index,
                    "raw_title": raw_title,
                    "title": title,
                    "image_path": str(item["path"]),
                    "code": code,
                    "has_existing_code": bool(existing_code),
                    "suffix": suffix,
                    "bag_type": bag_type,
                    "price": price,
                })

            results = []
            failures = []
            workers = min(BAG_UPLOAD_WORKERS, len(tasks))
            logger.info(f"泡袋批量处理开始: total={len(tasks)}, workers={workers}, bag_type={bag_type}")
            if workers <= 1:
                for task in tasks:
                    self._process_batch_item(task, results, failures)
            else:
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    future_map = {executor.submit(self._process_batch_item_result, task): task for task in tasks}
                    for future in as_completed(future_map):
                        result = future.result()
                        if result.get("ok"):
                            results.append(result["item"])
                        else:
                            failures.append(result["item"])

            results.sort(key=lambda item: item["index"])
            failures.sort(key=lambda item: item["index"])

            return {
                "source": str(source),
                "bag_type": bag_type,
                "price": price,
                "total": len(source_images),
                "success": results,
                "failures": failures,
            }
        finally:
            self._delete_path(source, "泡袋压缩包")
            self._delete_path(batch_dir, "泡袋批处理目录")

    def _process_batch_item(self, task: dict, results: list[dict], failures: list[dict]) -> None:
        result = self._process_batch_item_result(task)
        if result.get("ok"):
            results.append(result["item"])
        else:
            failures.append(result["item"])

    def _process_batch_item_result(self, task: dict) -> dict:
        title = task["title"]
        code = task["code"]
        assets = None
        try:
            existing_product = None
            if task["has_existing_code"]:
                existing_product = self._find_existing_product_by_code(code)
                if not existing_product:
                    raise ValueError(f"文件名带编号 {code}，但商品库里没有找到对应商品；为避免重复创建，已跳过。")
                if title == "泡袋新品":
                    title = self._display_title_from_filename(
                        existing_product.get("title") or existing_product.get("name") or existing_product.get("product_name") or ""
                    )
                core_title = existing_product.get("title") or self._format_core_title(code, title, task["suffix"])
            else:
                core_title = self._format_core_title(code, title, task["suffix"])

            category = self._classify_category(title, task["bag_type"]) or self._default_category(task["bag_type"])
            assets = self._generate_preview_assets(
                image_path=task["image_path"],
                code=code,
                title=title,
                bag_type=task["bag_type"],
            )
            main_oss = self._upload_to_oss(Path(assets["main_path"]))
            detail_oss = self._upload_to_oss(Path(assets["detail_path"]))
            if existing_product:
                core_result = self._update_existing_product_images(
                    existing_product=existing_product,
                    code=code,
                    category_id=category["category_id"],
                    main_url=main_oss["url"],
                    detail_url=detail_oss["url"],
                    price=task["price"],
                )
                action = "更新"
            else:
                core_result = self._save_product_to_core(
                    title=core_title,
                    code=code,
                    category_id=category["category_id"],
                    main_url=main_oss["url"],
                    detail_url=detail_oss["url"],
                    price=task["price"],
                )
                action = "新增"
            return {
                "ok": True,
                "item": {
                    "index": task["index"],
                    "title": core_title,
                    "source_title": title,
                    "code": code,
                    "action": action,
                    "category_name": category["category_name"],
                    "main_url": main_oss["url"],
                    "detail_url": detail_oss["url"],
                    "core_result": core_result,
                },
            }
        except Exception as e:
            logger.error(f"泡袋商品上传失败: title={title}, error={e}")
            return {"ok": False, "item": {"index": task["index"], "title": title, "error": str(e)}}
        finally:
            if assets:
                self._cleanup_generated_assets(assets)

    def _batch_done_text(self, result: dict) -> str:
        success = result.get("success") or []
        failures = result.get("failures") or []
        lines = [
            f"泡袋批量处理完成：成功 {len(success)} 个，失败 {len(failures)} 个。",
            f"模板：{result.get('bag_type')}",
            f"默认售价：{result.get('price', BAG_DEFAULT_PRICE)} 元",
        ]
        if success:
            lines.append("\n已上传商品库：")
            for item in success[:20]:
                lines.append(f"{item['index']}. [{item.get('action', '新增')}] {item['title']} | {item['code']} | {item['category_name']}")
            if len(success) > 20:
                lines.append(f"...还有 {len(success) - 20} 个成功项")
        if failures:
            lines.append("\n失败项：")
            for item in failures[:20]:
                lines.append(f"{item['index']}. {item['title']}：{item['error']}")
            if len(failures) > 20:
                lines.append(f"...还有 {len(failures) - 20} 个失败项")
        return "\n".join(lines)

    def _collect_batch_images(self, source: Path, source_dir: Path) -> list[dict]:
        if source.suffix.lower() == ".zip" or self._is_zip_file(source):
            return self._extract_zip_images(source, source_dir)
        if source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            title = self._title_from_filename(source.name)
            copied = source_dir / f"001_{self._safe_filename(source.name)}"
            shutil.copy2(source, copied)
            return [{"title": title, "path": copied}]
        raise ValueError("只支持 zip 压缩包或单张图片")

    def _is_zip_file(self, path: Path) -> bool:
        try:
            with path.open("rb") as f:
                return f.read(4) == b"PK\x03\x04"
        except OSError:
            return False

    def _extract_zip_images(self, source: Path, source_dir: Path) -> list[dict]:
        images = []
        with zipfile.ZipFile(source) as zf:
            infos = [
                info for info in zf.infolist()
                if not info.is_dir() and Path(self._zip_member_name(info)).suffix.lower() == ".png"
            ]
            infos.sort(key=self._zip_member_name)
            for index, info in enumerate(infos, start=1):
                raw_name = posixpath.basename(self._zip_member_name(info).replace("\\", "/"))
                title = self._title_from_filename(raw_name)
                out_name = f"{index:03d}_{self._safe_filename(raw_name)}"
                out_path = source_dir / out_name
                with zf.open(info) as src, out_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                images.append({"title": title, "path": out_path})
        return images

    def _zip_member_name(self, info: zipfile.ZipInfo) -> str:
        name = info.filename or ""
        if info.flag_bits & 0x800:
            return name
        try:
            raw = name.encode("cp437")
        except UnicodeEncodeError:
            return name
        for encoding in ("gbk", "cp936", "utf-8"):
            try:
                decoded = raw.decode(encoding)
            except UnicodeDecodeError:
                continue
            if decoded:
                return decoded
        return name

    def _title_from_filename(self, filename: str) -> str:
        title = Path(filename).stem.strip()
        title = re.sub(r"^\d+[\s._-]+", "", title)
        return title[:120] or "泡袋新品"

    def _extract_sj_code(self, value: str) -> str:
        match = re.search(r"(?i)SJ[\s_-]*(\d{3,6})", str(value or ""))
        if not match:
            return ""
        return f"SJ{match.group(1)}".upper()

    def _display_title_from_filename(self, title: str) -> str:
        cleaned = str(title or "").strip()
        cleaned = re.sub(r"(?i)^【?\s*SJ[\s_-]*\d{3,6}\s*】?", "", cleaned).strip()
        cleaned = re.sub(r"(?i)[-_\s]*【?\s*SJ[\s_-]*\d{3,6}\s*】?$", "", cleaned).strip()
        cleaned = re.sub(r"^[\s._-]+", "", cleaned)
        cleaned = re.sub(r"[-_\s]*(长泡袋|短泡袋|宽版泡袋|泡袋)$", "", cleaned).strip()
        return cleaned[:120] or "泡袋新品"

    def _find_existing_product_by_code(self, code: str) -> dict | None:
        code = self._extract_sj_code(code) or str(code or "").strip().upper()
        if not code:
            return None
        try:
            rows = get_product_service().search(code, limit=20)
            for row in rows:
                row_code = self._extract_sj_code(row.get("sku_no") or row.get("coding") or "")
                title_code = self._extract_sj_code(row.get("title") or row.get("name") or row.get("product_name") or "")
                if row_code == code or title_code == code:
                    return row
        except Exception as e:
            logger.warning(f"按编号查询自有库商品失败: code={code}, error={e}")
        return None

    def _api_data_list(self, result) -> list[dict]:
        data = result.get("data") if isinstance(result, dict) else result
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("list", "data", "rows", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            if isinstance(data.get("data"), dict):
                return self._api_data_list(data["data"])
        return []

    def _format_core_title(self, code: str, name: str, suffix: str) -> str:
        cleaned = str(name or "").strip()
        cleaned = re.sub(r"(?i)^【?\s*SJ[\s_-]*\d{3,6}\s*】?", "", cleaned).strip()
        cleaned = re.sub(r"(?i)[-_\s]*【?\s*SJ[\s_-]*\d{3,6}\s*】?$", "", cleaned).strip()
        cleaned = re.sub(r"[-_\s]*(长泡袋|短泡袋|宽版泡袋|泡袋)$", "", cleaned).strip()
        return f"【{code}】{cleaned or '泡袋新品'}-{suffix}"

    def _safe_filename(self, filename: str) -> str:
        suffix = Path(filename).suffix.lower() or ".png"
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).stem).strip("._-") or uuid.uuid4().hex[:8]
        return f"{stem[:80]}{suffix}"

    def _upload_to_oss(self, path: Path) -> dict:
        from scripts.oss_uploader import OSSUploader
        from src.core.config import get_config

        result = OSSUploader(get_config().oss_config).upload(str(path))
        if not isinstance(result, dict) or result.get("error") or not result.get("url"):
            raise RuntimeError(f"OSS 上传失败：{result}")
        self._delete_path(path, "泡袋 OSS 图片")
        return result

    def _save_product_to_core(
        self,
        title: str,
        code: str,
        category_id: int,
        main_url: str,
        detail_url: str,
        price: int = BAG_DEFAULT_PRICE,
    ) -> dict:
        payload = {
            "title": title,
            "product_type": "bubble_bag",
            "bag_type": self._bag_type_from_title(title),
            "product_category_id": [category_id],
            "status": 0,
            "simple_desc": "",
            "content": f'<p><img src="{html.escape(detail_url, quote=True)}" /></p>',
            "main_images": [main_url],
            "base": {
                "new_0": {
                    "images": main_url,
                    "spec": "",
                    "coding": code,
                    "note": "",
                    "default_warehouse_position": "",
                    "unit": {
                        "new_0": {
                            "unit_id": 1,
                            "unit_number": 1,
                            "coding": code,
                            "barcode": "",
                            "weight": 0,
                            "volume": 0,
                            "price": price,
                            "cost_price": 0,
                            "extends": "",
                        }
                    },
                }
            },
        }
        return get_product_service().save(payload)

    def _update_existing_product_images(
        self,
        existing_product: dict,
        code: str,
        category_id: int,
        main_url: str,
        detail_url: str,
        price: int = BAG_DEFAULT_PRICE,
    ) -> dict:
        product_id = int(existing_product.get("id") or existing_product.get("product_id") or 0)
        if not product_id:
            raise ValueError(f"编号 {code} 找到的商品缺少 product_id")

        detail = self._load_product_for_edit(product_id)
        title = detail.get("title") or detail.get("name") or existing_product.get("title") or existing_product.get("name")
        category_ids = self._product_category_ids(detail) or self._product_category_ids(existing_product) or [category_id]
        if category_id and category_id not in category_ids:
            category_ids = [category_id]

        simple_desc = detail.get("simple_desc") or existing_product.get("simple_desc") or ""
        payload = {
            "id": product_id,
            "title": title or existing_product.get("title") or code,
            "product_type": "bubble_bag",
            "bag_type": self._bag_type_from_title(title or existing_product.get("title") or ""),
            "product_category_id": category_ids,
            "status": int(detail.get("status") if detail.get("status") not in (None, "") else existing_product.get("status") or 0),
            "content": f'<p><img src="{html.escape(detail_url, quote=True)}" /></p>',
            "main_images": [main_url],
            "base": self._product_base_payload(detail, existing_product, code, main_url, price, product_id),
        }
        if simple_desc:
            payload["simple_desc"] = simple_desc
        return get_product_service().save(payload)

    def _load_product_for_edit(self, product_id: int) -> dict:
        try:
            service = get_product_service()
            data = service.options(product_id).get("data") or service.info(product_id)
            if isinstance(data, dict):
                return data
        except Exception as e:
            logger.warning(f"读取自有库商品编辑资料失败: product_id={product_id}, error={e}")
        return {"id": product_id}

    def _bag_type_from_title(self, title: str) -> str:
        text = str(title or "")
        if "长泡袋" in text:
            return "长泡袋"
        if "短泡袋" in text:
            return "短泡袋"
        if "红茶袋" in text:
            return "红茶袋"
        if "宽版" in text:
            return "宽版"
        if "空白" in text:
            return "空白"
        return "长泡袋" if "泡袋" in text else ""

    def _unwrap_api_data(self, result) -> dict:
        data = result.get("data") if isinstance(result, dict) else result
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            merged = dict(data["data"])
            for key, value in data.items():
                if key not in {"data"} and key not in merged:
                    merged[key] = value
            if data.get("product_group_data") and not merged.get("product_group_data"):
                merged["product_group_data"] = data["product_group_data"]
            return merged
        return data if isinstance(data, dict) else {}

    def _product_category_ids(self, product: dict) -> list[int]:
        for key in ("product_category_ids", "product_category_id", "category_ids"):
            value = product.get(key)
            if isinstance(value, list):
                return [int(item) for item in value if str(item).isdigit()]
            if isinstance(value, str):
                return [int(item) for item in re.split(r"[,，\s]+", value) if item.isdigit()]
        return []

    def _product_base_payload(
        self,
        detail: dict,
        existing_product: dict,
        code: str,
        main_url: str,
        price: int,
        product_id: int,
    ) -> dict:
        rows = detail.get("product_group_data") if isinstance(detail.get("product_group_data"), list) else []
        if not rows:
            rows = [detail or existing_product]

        base_payload = {}
        for index, row in enumerate(rows):
            row_id = row.get("id") or row.get("product_id") or (product_id if index == 0 else None)
            product_key = str(row_id) if row_id else f"new_{index}"
            units = row.get("base") if isinstance(row.get("base"), list) else []
            unit = units[0] if units else {}
            unit_key = str(unit.get("id")) if unit.get("id") else "new_0"
            row_code = row.get("coding") or unit.get("coding") or code
            use_new_image = str(row_id or product_id) == str(product_id) or index == 0
            base_payload[product_key] = {
                "images": main_url if use_new_image else (row.get("images") or existing_product.get("images") or ""),
                "spec": row.get("spec") or "",
                "coding": row_code,
                "note": row.get("note") or "",
                "default_warehouse_position": row.get("default_warehouse_position") or "",
                "unit": {
                    unit_key: {
                        "unit_id": unit.get("unit_id") or row.get("unit_id") or 1,
                        "unit_number": unit.get("unit_number") or 1,
                        "coding": unit.get("coding") or row_code,
                        "barcode": unit.get("barcode") or "",
                        "weight": unit.get("weight") or 0,
                        "volume": unit.get("volume") or 0,
                        "price": price,
                        "cost_price": unit.get("cost_price") if unit.get("cost_price") not in (None, "") else row.get("cost_price") or 0,
                        "extends": unit.get("extends") or "",
                    }
                },
            }
        return base_payload

    def _cleanup_generated_assets(self, assets: dict) -> None:
        for key in ("standard_path", "web_standard_path", "web_main_path", "web_detail_path"):
            value = assets.get(key)
            if value:
                self._delete_path(Path(value), "泡袋本地图片")
        generated_dir = assets.get("generated_dir")
        if generated_dir:
            self._delete_path(Path(generated_dir), "泡袋生成目录")

    def _delete_path(self, path: Path, label: str) -> None:
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"{label} 删除失败: {path}, error={e}")

    def _generate_preview_assets(self, image_path: str, code: str, title: str, bag_type: str = "岩茶") -> dict:
        source = Path(str(image_path).strip().strip('"'))
        if not source.exists():
            raise FileNotFoundError(f"找不到图片：{source}")
        if not BAG_PREPARE_SCRIPT.exists():
            raise FileNotFoundError(f"找不到预处理脚本：{BAG_PREPARE_SCRIPT}")
        if not BAG_GENERATE_SCRIPT.exists():
            raise FileNotFoundError(f"找不到模板生成脚本：{BAG_GENERATE_SCRIPT}")

        run_id = f"{code}-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        output_dir = BAG_GENERATED_DIR / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        WEB_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        bag_meta = BAG_TYPES.get(bag_type, BAG_TYPES["岩茶"])

        prepared = output_dir / "_prepared" / f"{code}-standard.png"
        debug_dir = output_dir / "debug"
        self._run_command(
            [
                sys.executable,
                str(BAG_PREPARE_SCRIPT),
                str(source),
                str(prepared),
                "--debug-dir",
                str(debug_dir),
                "--target-width",
                str(bag_meta["target_width"]),
                "--target-height",
                str(bag_meta["target_height"]),
            ],
            cwd=BAG_TEMPLATE_DIR,
            timeout=120,
        )

        self._run_command(
            [
                sys.executable,
                str(BAG_GENERATE_SCRIPT),
                "--input",
                str(prepared),
                "--output",
                str(output_dir),
                "--start",
                code,
                "--title",
                title or "九龙窠肉桂",
                "--template",
                bag_meta["render_template"],
            ],
            cwd=BAG_TEMPLATE_DIR,
            timeout=180,
        )

        main_path, detail_path = self._find_generated_images(output_dir)
        web_token = uuid.uuid4().hex[:10]
        web_standard = WEB_IMAGE_DIR / f"{code}_{web_token}_standard.png"
        web_main = WEB_IMAGE_DIR / f"{code}_{web_token}_main.png"
        web_detail = WEB_IMAGE_DIR / f"{code}_{web_token}_detail.png"
        shutil.copy2(prepared, web_standard)
        shutil.copy2(main_path, web_main)
        shutil.copy2(detail_path, web_detail)

        return {
            "generated_dir": str(output_dir),
            "standard_path": str(prepared),
            "main_path": str(main_path),
            "detail_path": str(detail_path),
            "web_standard_path": str(web_standard),
            "web_main_path": str(web_main),
            "web_detail_path": str(web_detail),
            "standard_url": f"/api/images/file/{web_standard.name}",
            "main_url": f"/api/images/file/{web_main.name}",
            "detail_url": f"/api/images/file/{web_detail.name}",
        }

    def _run_command(self, cmd: list[str], cwd: Path, timeout: int) -> None:
        logger.info(f"执行泡袋脚本: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or f"脚本返回码 {result.returncode}").strip())

    def _find_generated_images(self, output_dir: Path) -> tuple[Path, Path]:
        main = None
        detail = None
        for path in output_dir.glob("*.png"):
            name = path.name
            if "主图" in name:
                main = path
            elif "详情页" in name:
                detail = path
        if not main or not detail:
            raise FileNotFoundError(f"没有在输出目录找到主图/详情页：{output_dir}")
        return main, detail

    def _normalize_bag_type(self, text: str) -> str:
        text = str(text or "")
        if "宽版" in text or "宽泡袋" in text:
            return "宽版"
        if "红茶" in text or "金骏眉" in text or "小种" in text:
            return "红茶"
        if "岩茶" in text or "肉桂" in text or "水仙" in text or "大红袍" in text:
            return "岩茶"
        return ""

    def _bag_price(self, bag_type: str) -> int:
        return int(BAG_TYPES.get(bag_type, BAG_TYPES["岩茶"]).get("price", BAG_DEFAULT_PRICE))

    def _clean_product_name(self, text: str) -> str:
        cleaned = str(text or "").strip()
        for word in ["商品名", "名字", "名称", "叫", "是", "泡袋", "新品"]:
            cleaned = cleaned.replace(word, " ")
        cleaned = re.sub(r"\s+", "", cleaned)
        cleaned = re.sub(r"^[：:，,。.\s]+|[：:，,。.\s]+$", "", cleaned)
        return cleaned[:80]

    def _classify_category(self, name: str, bag_type: str = "") -> dict | None:
        if bag_type == "宽版":
            return {"category_id": 21, "category_name": "宽版泡袋"}
        if bag_type == "红茶":
            return {"category_id": 12, "category_name": "红茶泡袋"}
        for key, cid, cname in BAG_CATEGORIES:
            if key in name:
                return {"category_id": cid, "category_name": cname}
        return None

    def _default_category(self, bag_type: str = "") -> dict:
        if bag_type == "红茶":
            return {"category_id": 12, "category_name": "红茶泡袋"}
        if bag_type == "宽版":
            return {"category_id": 21, "category_name": "宽版泡袋"}
        return {"category_id": 7, "category_name": "肉桂泡袋"}

    def _category_from_text(self, text: str) -> dict | None:
        text = str(text or "")
        mapping = {
            "肉桂": (7, "肉桂泡袋"),
            "水仙": (6, "水仙泡袋"),
            "大红袍": (5, "大红袍泡袋"),
            "红茶": (12, "红茶泡袋"),
            "宽版": (21, "宽版泡袋"),
        }
        for key, (cid, cname) in mapping.items():
            if key in text:
                return {"category_id": cid, "category_name": cname}
        return None

    def _extract_image_path(self, text: str) -> str:
        text = str(text or "").strip()
        match = re.search(r"(?:图片|image|path)[:：]?\s*(.+)$", text, re.I)
        if match:
            text = match.group(1).strip()
        for part in re.split(r"\s+", text):
            if re.search(r"\.(png|jpg|jpeg|webp|bmp)$", part, re.I) or part.startswith("/api/images/file/"):
                return part
        return text if Path(text).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"} else ""

    def _extract_upload_path(self, text: str) -> str:
        text = str(text or "").strip()
        match = re.search(r"(?:图片|文件|附件|image|path)[:：]?\s*(.+?)(?:\s+预览[:：].*)?$", text, re.I)
        if match:
            text = match.group(1).strip()
        for part in re.split(r"\s+", text):
            if re.search(r"\.(zip|png|jpg|jpeg|webp|bmp)$", part, re.I):
                return part.strip('"')
        return text.strip('"') if Path(text.strip('"')).suffix.lower() in {".zip", ".png", ".jpg", ".jpeg", ".webp", ".bmp"} else ""

    def _next_sj_code(self, start_number: int = 1001) -> str:
        try:
            return get_product_service().next_sku_no(
                start_number=max(int(start_number or 1001), 1001),
                compact_from_start=True,
            )
        except Exception as e:
            logger.warning(f"SJ code preview failed, using fallback SJ1001: {e}")
        return f"SJ{max(int(start_number or 1001), 1001):04d}"

    def _is_confirm(self, text: str) -> bool:
        return str(text or "").strip() in {"确认", "确定", "可以", "继续", "好", "没问题", "是"}

    def _is_cancel(self, text: str) -> bool:
        return any(word in str(text or "") for word in ["取消", "算了", "不要", "不用"])
