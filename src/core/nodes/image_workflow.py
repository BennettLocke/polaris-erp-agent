"""
图片订单工作流节点（A流程 - 完整实现）
严格按 order-flow SKILL.md A 流程实现

流程：
A1. 检测黑框 → 裁切(1个外框=1张,N个=N张)
A2. RapidOCR 识别 → 提取备注区域文字
A3. 上传 OSS → 返回图片 URL
A4. 解析 OCR 文本 → 提取客户、商品、颜色、数量、工艺、是否含"开单"
A5. 查 MySQL → 获取 product_id、价格、件→套换算率(自动标准化商品名)
A6. 创建工作流订单 → WorkflowOrderSave
A7. 开单判断（先不执行，由 inventory_decision 处理）
"""
import re
import os
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Optional
from src.core.state import AgentState
from src.core.config import get_config
from src.core.tools.caller import get_tool_caller
from src.core.product_matcher import ProductMatcher
from src.core.product_name import PRODUCT_SPECS, normalize_product_name
from src.utils import get_logger
from scripts.image_processor import ImageProcessor
from scripts.common.color_filter import COLOR_ALIASES, STANDARD_COLORS, filter_uv, extract_color_from_text
from scripts.common.unit_converter import calculate_order_quantity, parse_unit_from_simple_desc

logger = get_logger("sjagent.nodes.image_workflow")
REMARK_OCR_TOP_RATIO = 0.22
CHINESE_NUMBER_PATTERN = r"[零〇一二两三四五六七八九十百千万]+"
QUANTITY_NUMBER_PATTERN = rf"(?:\d+|{CHINESE_NUMBER_PATTERN})"
QUANTITY_UNIT_PATTERN = r"(套|件|个|张|只|盒|捆)"


def _parse_quantity_number(value: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)

    digits = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    small_units = {"十": 10, "百": 100, "千": 1000}
    total = 0
    current = 0
    seen = False
    for char in text:
        if char in digits:
            current = digits[char]
            seen = True
            continue
        if char in small_units:
            unit = small_units[char]
            total += (current or 1) * unit
            current = 0
            seen = True
            continue
        if char == "万":
            total = (total + current or 1) * 10000
            current = 0
            seen = True
            continue
        return None
    if not seen:
        return None
    return total + current


def image_workflow_node(state: AgentState) -> AgentState:
    """
    图片订单工作流节点（完整实现）
    """
    user_input = state.get("input", "")
    state["node_name"] = "image_workflow"

    # 1. 提取图片路径/URL
    image_paths = extract_image_paths(user_input)
    state["image_paths"] = image_paths

    if not image_paths:
        state["output"] = "未检测到图片，请发送设计稿图片"
        return state

    caller = get_tool_caller()
    all_parsed = []
    all_workflow_orders = []
    has_any_kaipiao = False

    # 2. 逐图处理
    for img_path in image_paths:
        try:
            result = process_single_image(img_path, caller)
            if result.get("error"):
                logger.error(f"图片处理失败: {img_path}, error={result['error']}")
                continue

            parsed = result.get("parsed", {})
            all_parsed.append(parsed)

            if parsed.get("has_kaipiao"):
                has_any_kaipiao = True

            if result.get("workflow_order"):
                all_workflow_orders.append(result["workflow_order"])

        except Exception as e:
            logger.error(f"单图处理异常: {img_path}, error={e}")

    state["image_parsed"] = all_parsed
    state["workflow_orders"] = all_workflow_orders
    state["has_kaipiao"] = has_any_kaipiao

    logger.info(f"图片订单处理完成：{len(all_parsed)} 个订单")
    return state


def process_single_image(image_path: str, caller) -> dict:
    """
    处理单张图片的全流程

    Returns:
        {
            "parsed": {...},  # 解析结果
            "product_warning": [...],  # 商品未找到警告
            "workflow_order": {...},  # 创建的工作流订单
            "error": "..."  # 错误信息
        }
    """
    result = {
        "parsed": {},
        "product_warning": [],
        "workflow_order": None,
    }

    # 1. 下载图片（如果是URL）
    local_path = download_image_if_needed(image_path)
    if local_path is None:
        result["error"] = f"无法获取图片: {image_path}"
        return result

    cropped_images = []
    try:
        processor = ImageProcessor()

        # 2. 检测黑框
        frames = processor.detect_black_frames(local_path)
        logger.info(f"检测到 {len(frames)} 个外框")

        if frames:
            child_results = []
            for i, frame in enumerate(frames):
                cropped = processor.crop_frame(local_path, frame)
                if cropped is None:
                    continue
                temp_path = save_temp_image(cropped, i)
                cropped_images.append(temp_path)
                ocr_texts = recognize_remark_texts(processor, cropped)
                child_results.append(_process_ocr_order(ocr_texts, temp_path, caller))

            result["items"] = child_results
            propagate_batch_customer_context(child_results)
            result["workflow_orders"] = [item["workflow_order"] for item in child_results if item.get("workflow_order")]
            result["workflow_order_payloads"] = [
                item["workflow_order_payload"]
                for item in child_results
                if item.get("workflow_order_payload")
            ]
            result["parsed"] = {
                "full_text": "\n\n".join((item.get("parsed") or {}).get("full_text", "") for item in child_results).strip()
            }
            result["product_warning"] = [
                warning
                for item in child_results
                for warning in (item.get("product_warning") or [])
            ]
            errors = [item.get("error") for item in child_results if item.get("error")]
            if errors and not result["workflow_orders"]:
                result["error"] = "；".join(errors)
        else:
            ocr_texts = recognize_remark_texts(processor, local_path)
            result.update(_process_ocr_order(ocr_texts, local_path, caller))

    finally:
        # 清理临时裁切图
        for tmp in cropped_images:
            if os.path.exists(tmp):
                os.remove(tmp)
        # 清理下载的临时文件（如果是URL下载的）
        if local_path != image_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except OSError:
                pass

    return result


def recognize_remark_texts(processor: ImageProcessor, image) -> list[str]:
    """Run OCR on the remark area, widening once when the first pass is too sparse."""
    if isinstance(image, str):
        image = processor._load_image(image)
    texts: list[str] = []
    for ratio in (REMARK_OCR_TOP_RATIO, 0.38):
        _, text = processor.ocr_recognize(image, top_ratio=ratio)
        text = (text or "").strip()
        if text and text not in texts:
            texts.append(text)
        parsed = parse_ocr_text_list(texts)
        if parsed.get("goods_name") and (parsed.get("craft") or parsed.get("quantity", 1) != 1):
            break
    return texts or [""]


def _process_ocr_order(ocr_texts: list[str], image_path: str, caller) -> dict:
    item = {
        "parsed": {},
        "product_warning": [],
        "workflow_order": None,
        "workflow_order_payload": None,
    }
    oss_url = upload_to_oss(image_path, caller)
    item["image_url"] = oss_url
    item["image_source_path"] = image_path

    parsed = parse_ocr_text_list(ocr_texts)
    parsed = repair_ocr_parsed_fields(parsed, caller)
    item["parsed"] = parsed

    goods_name = parsed.get("goods_name", "")
    color = parsed.get("color", "")
    product_info = find_product_by_goods_name(goods_name, caller, color)
    case_pack_info = product_info
    if product_info is None and goods_name and color:
        # 颜色可能是定制色或 OCR 偏差；工作流仍要按同 SPU 件规换算数量。
        case_pack_info = find_case_pack_by_goods_name(goods_name, caller)
    if product_info is None:
        if goods_name:
            item["product_warning"].append(goods_name)
        logger.info(f"商品库未匹配，按识别礼盒名创建工作流: {goods_name}")
    else:
        parsed["product_id"] = product_info.get("id")
        parsed["product_info"] = product_info
    if case_pack_info is not None:
        order_qty = parsed.get("quantity", 1)
        reported_unit = parsed.get("unit") or "套"
        simple_desc = case_pack_info.get("simple_desc", "")
        per_piece = parse_per_piece(simple_desc)
        if per_piece > 1 and reported_unit == "件":
            order_qty = calculate_order_quantity(
                user_reported=f"{order_qty}{reported_unit}",
                quantity=order_qty,
                simple_desc=simple_desc,
            )
            parsed["quantity"] = order_qty
            parsed["unit"] = "套"
            parsed["per_piece"] = per_piece

    if not goods_name:
        item["error"] = "未识别到礼盒名称，未创建工作流订单"
    else:
        craft = parsed.get("craft", "")
        item["workflow_order_payload"] = {
            "customer": parsed.get("customer_name") or "散客",
            "goods_name": goods_name,
            "quantity": parsed.get("quantity", 1),
            "color": parsed.get("color", ""),
            "order_images": [oss_url] if oss_url else [],
            "is_screen_print": any(kw in craft for kw in ["丝印", "印刷"]),
            "remark": craft,
        }
    return item


def extract_image_paths(text: str) -> list[str]:
    """从文本中提取图片路径或URL"""
    paths = []

    # URL
    url_pattern = r"https?://[^\s<>\"']+\.(?:jpg|jpeg|png|gif|webp)"
    paths.extend(re.findall(url_pattern, text, re.IGNORECASE))

    # 本地路径
    local_pattern = r"[a-zA-Z]:\\[^\s<>\"']+\.(?:jpg|jpeg|png|gif|webp)"
    paths.extend(re.findall(local_pattern, text))

    # 去除重复
    return list(dict.fromkeys(paths))


def download_image_if_needed(image_path: str) -> Optional[str]:
    """如果是URL则下载到本地，否则直接返回路径"""
    if image_path.startswith("http://") or image_path.startswith("https://"):
        try:
            import requests
            response = requests.get(image_path, timeout=30)
            if response.status_code == 200:
                suffix = Path(image_path).suffix or ".jpg"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                    f.write(response.content)
                    return f.name
        except Exception as e:
            logger.error(f"图片下载失败: {e}")
            return None
    return image_path


def save_temp_image(img_array, index: int) -> str:
    """保存裁切图到临时文件"""
    import cv2
    import uuid
    temp_dir = tempfile.gettempdir()
    unique_id = uuid.uuid4().hex[:8]
    path = os.path.join(temp_dir, f"sjagent_crop_{index}_{unique_id}.jpg")
    cv2.imwrite(path, img_array)
    return path


def upload_to_oss(local_path: str, caller) -> str:
    """上传图片到 OSS"""
    try:
        upload_result = caller.call(
            "script_call",
            script_name="oss_uploader.py",
            args=[local_path],
        )
        if isinstance(upload_result, dict):
            if upload_result.get("url"):
                return upload_result["url"]
            data = upload_result.get("data")
            if isinstance(data, dict) and data.get("url"):
                return data["url"]
            raw = upload_result.get("raw")
            if raw:
                for line in reversed(str(raw).splitlines()):
                    line = line.strip()
                    if not (line.startswith("{") and line.endswith("}")):
                        continue
                    try:
                        raw_data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(raw_data, dict) and raw_data.get("url"):
                        return raw_data["url"]
            if upload_result.get("error"):
                logger.warning(f"OSS上传失败: {upload_result['error']}")
    except Exception as e:
        logger.warning(f"OSS上传失败: {e}")
    return ""


def _normalize_ocr_line(line: str) -> str:
    return (
        line.replace("：", ":")
        .replace("（", "(")
        .replace("）", ")")
        .replace("，", ",")
        .strip()
    )


def _clean_field_value(value: str) -> str:
    return value.strip(" \t:-：,，。;；")


def _extract_after_label(line: str, labels: tuple[str, ...]) -> str:
    text = _normalize_ocr_line(line)
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*:?\s*(.+)", text)
        if match:
            return _clean_field_value(match.group(1))
    return ""


def _parse_quantity(line: str) -> tuple[int, str] | None:
    text = _normalize_ocr_line(line).replace(" ", "")

    label_match = re.search(
        rf"(?:数量|订单数量|下单数量|做|要|订)\D{{0,6}}?({QUANTITY_NUMBER_PATTERN})\s*{QUANTITY_UNIT_PATTERN}?",
        text,
    )
    if label_match:
        quantity = _parse_quantity_number(label_match.group(1))
        if quantity is not None:
            return quantity, label_match.group(2) or "套"

    unit_match = re.search(rf"({QUANTITY_NUMBER_PATTERN})\s*{QUANTITY_UNIT_PATTERN}", text)
    if unit_match and not re.search(r"(电话|手机|编号|单号|日期|20\d{{2}})", text):
        quantity = _parse_quantity_number(unit_match.group(1))
        if quantity is not None:
            return quantity, unit_match.group(2)

    compact_match = re.search(rf"(?:UV|uv|丝印|印刷)?({QUANTITY_NUMBER_PATTERN}){QUANTITY_UNIT_PATTERN}", text)
    if compact_match:
        quantity = _parse_quantity_number(compact_match.group(1))
        if quantity is not None:
            return quantity, compact_match.group(2)

    return None


def _is_plausible_unlabeled_goods(value: str) -> bool:
    text = _clean_field_value(value)
    if not text or len(text) < 2:
        return False
    if re.fullmatch(r"(客户|客人|客户名称|下单|商品|产品|货品|品名|名称|H|h)", text):
        return False
    if re.search(r"(电话|手机|编号|单号|日期)", text):
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", text))


def _goods_word_pattern() -> str:
    return r"(五格\s*短\s*款?\s*半\s*斤|短\s*款?\s*半\s*斤|长\s*款\s*半\s*斤|长\s*半\s*斤|半\s*斤|[一二三四五六七八九十\d]+两|[一二三四五六七八九十\d]+小盒|小盒|中盒|大盒|礼盒|茶派|岩味|滋味|喜悦|生财)"


def _looks_like_goods_text(text: str) -> bool:
    return bool(re.search(_goods_word_pattern(), _normalize_ocr_line(text)))


def _is_invalid_customer(value: str | None) -> bool:
    text = _clean_field_value(str(value or ""))
    if not text or text in {"客户未识别", "未识别", "无", "暂无"}:
        return True
    if len(text) < 2:
        return True
    if re.fullmatch(r"[0-9A-Za-z_-]{1,2}", text):
        return True
    if re.search(r"\d", text):
        return True
    if _looks_like_goods_text(text) and not re.search(r"(公司|茶业|茶叶|店|商行|夷品|一枝一叶|客户)", text):
        return True
    return False


def _extract_goods_from_remark(line: str) -> str:
    text = _normalize_ocr_line(line)
    without_date = re.sub(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", "", text)
    without_prefix = re.sub(r"^(客户|下单)\s*:?\s*", "", without_date).strip()
    without_qty = re.sub(rf"(?:UV|uv)?{QUANTITY_NUMBER_PATTERN}\s*{QUANTITY_UNIT_PATTERN}", "", without_prefix)
    without_craft = re.sub(r"\([^)]*(丝印|印刷|提袋)[^)]*\)", "", without_qty)
    without_craft = re.sub(r"(提袋\s*)?(丝印|印刷|UV|uv|烫金|烫银|击凸|击凹)", "", without_craft)
    without_craft = re.sub(r"提袋", "", without_craft)
    goods = without_craft
    color_words = list(dict.fromkeys([*STANDARD_COLORS, *COLOR_ALIASES.keys()]))
    for color in sorted(color_words, key=len, reverse=True):
        goods = goods.replace(color, "")
    return _clean_field_value(goods)


def _looks_like_goods_line(line: str) -> bool:
    text = _normalize_ocr_line(line)
    if re.fullmatch(r"(客户|客人|客户名称|下单)\s*:?", text):
        return False
    if re.fullmatch(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", text):
        return False
    return bool(_parse_quantity(text) and _looks_like_goods_text(text))


def _clean_goods_value(value: str) -> str:
    return _extract_goods_from_remark(value) or _clean_field_value(value)


def _extract_craft_terms(line: str) -> list[str]:
    terms = []
    for term in re.findall(r"提袋|丝印|印刷|UV|uv|烫金|烫银|击凸|击凹", line):
        normalized = "UV" if term.lower() == "uv" else term
        if normalized not in terms:
            terms.append(normalized)
    return terms


def parse_ocr_text_list(ocr_texts: list[str]) -> dict:
    """
    解析 OCR 识别结果
    提取：客户名、商品名、颜色、数量、工艺、是否含"开单"

    按 order-flow 规则：
    - 客户：从"客户："后提取
    - 商品：从"商品："后提取（含【品牌】前缀）
    - 颜色：从"颜色："后提取
    - 数量：从"数量："后提取，支持"X件"格式
    - 工艺：从"工艺："后提取
    - has_kaipiao：文本中含"开单"则为 true
    """
    # 合并所有 OCR 文本
    full_text = "\n".join(ocr_texts)

    result = {
        "customer_name": "",
        "goods_name": "",
        "color": "",
        "quantity": 1,
        "unit": "件",
        "craft": "",
        "has_kaipiao": False,
        "full_text": full_text,
    }

    lines = full_text.split("\n")

    pending_label = ""

    for line in lines:
        line = _normalize_ocr_line(line)
        if not line:
            continue
        line_quantity = _parse_quantity(line)
        line_craft_terms = _extract_craft_terms(line)
        line_color = extract_color_from_text(line) or ""

        if pending_label == "customer":
            if not _looks_like_goods_text(line):
                customer_value = _clean_field_value(line)
                if not _is_invalid_customer(customer_value):
                    result["customer_name"] = customer_value
                pending_label = ""
                continue
            pending_label = ""

        # 客户
        if re.fullmatch(r"(客户|客人|客户名称)\s*:?", line):
            pending_label = "customer"
            continue
        customer_name = _extract_after_label(line, ("客户", "客人", "客户名称"))
        if customer_name:
            result["customer_name"] = customer_name
            continue

        # 商品（通用提取，不再门控在特定关键词上）
        goods_name = _extract_after_label(line, ("商品", "产品", "货品", "品名", "名称", "礼盒"))
        if goods_name:
            result["goods_name"] = _clean_goods_value(goods_name)
        elif "【" in line:
            # 直接是商品名称（含【品牌】前缀）
            match = re.search(r"【[^】]+】[^\s，,。]+", line)
            if match:
                result["goods_name"] = match.group()
        elif not result["goods_name"] and re.search(r"(五格\s*短\s*款?\s*半\s*斤|短\s*款?\s*半\s*斤|长\s*款\s*半\s*斤|长\s*半\s*斤|半\s*斤|小盒|中盒|大盒|礼盒|茶派|茶派长)", line):
            remark_goods = _extract_goods_from_remark(line)
            if remark_goods and not re.fullmatch(r"下单|客户", remark_goods):
                result["goods_name"] = remark_goods
        elif not result["goods_name"] and _looks_like_goods_line(line):
            remark_goods = _extract_goods_from_remark(line)
            if remark_goods and not re.fullmatch(r"下单|客户", remark_goods):
                result["goods_name"] = remark_goods
        elif not result["goods_name"] and (line_quantity or line_craft_terms or line_color):
            remark_goods = _extract_goods_from_remark(line)
            if _is_plausible_unlabeled_goods(remark_goods):
                result["goods_name"] = remark_goods

        # 颜色
        color = _extract_after_label(line, ("颜色", "色号"))
        if color:
            result["color"] = filter_uv(color)

        # 数量
        if line_quantity:
            result["quantity"], result["unit"] = line_quantity

        # 工艺
        craft = _extract_after_label(line, ("工艺", "做法"))
        if craft:
            result["craft"] = craft

        if line_craft_terms:
            existing = [item for item in re.split(r"[、,，/ ]+", result["craft"]) if item]
            for term in line_craft_terms:
                if term not in existing:
                    existing.append(term)
            result["craft"] = "、".join(existing)

    # 检测是否要求继续开销售单
    result["has_kaipiao"] = any(word in full_text for word in ("开单", "下单"))

    # 提取颜色（如果没有明确标注，尝试从商品描述中提取）
    if not result["color"]:
        result["color"] = extract_color_from_text(full_text) or ""

    return result


def repair_ocr_parsed_fields(parsed: dict, caller) -> dict:
    """
    Repair OCR structure with ERP data.

    Common design remarks often look like "客户：\n夷品锦程3小盒黄色".
    OCR got the text right, but the parser may put the whole line into customer.
    Here we verify possible splits against the customer table and product table.
    """
    parsed = dict(parsed or {})
    full_text = parsed.get("full_text", "")
    lines = [_normalize_ocr_line(line) for line in full_text.splitlines() if _normalize_ocr_line(line)]
    color = parsed.get("color", "")

    customer_name = _clean_field_value(parsed.get("customer_name", ""))
    goods_name = _clean_field_value(parsed.get("goods_name", ""))

    split_sources = []
    if customer_name and _looks_like_goods_text(customer_name):
        split_sources.append(customer_name)
    if goods_name and _looks_like_goods_text(goods_name):
        split_sources.append(goods_name)
    if not goods_name or split_sources:
        split_sources.extend(line for line in lines if _looks_like_goods_text(line))

    for source in dict.fromkeys(split_sources):
        split = _split_customer_goods_by_erp(source, caller, color)
        if not split:
            continue
        inferred_customer, inferred_goods = split
        if _is_invalid_customer(customer_name) or _looks_like_goods_text(customer_name):
            customer_name = inferred_customer
        if not goods_name or source == goods_name or _looks_like_goods_text(customer_name):
            goods_name = inferred_goods
        break

    if not goods_name:
        for line in lines:
            if _looks_like_goods_text(line):
                candidate = _extract_goods_from_remark(line)
                if candidate:
                    goods_name = candidate
                    break

    if _is_invalid_customer(customer_name):
        inferred = _infer_customer_from_ocr_lines(lines, goods_name, caller)
        customer_name = inferred or "散客"
        parsed["customer_inferred"] = bool(inferred)
        parsed["customer_missing"] = not bool(inferred)

    parsed["customer_name"] = customer_name
    parsed["goods_name"] = goods_name
    return parsed


def propagate_batch_customer_context(items: list[dict]) -> None:
    """Within one uploaded image, use the reliable customer for OCR-missed frames."""
    names: list[str] = []
    for item in items or []:
        parsed = item.get("parsed") or {}
        name = _clean_field_value(str(parsed.get("customer_name") or ""))
        if name and not _is_invalid_customer(name) and not parsed.get("customer_missing") and name not in names:
            names.append(name)
    if len(names) != 1:
        return

    batch_customer = names[0]
    for item in items or []:
        parsed = item.get("parsed") or {}
        name = _clean_field_value(str(parsed.get("customer_name") or ""))
        if parsed.get("customer_missing") or _is_invalid_customer(name):
            parsed["customer_name"] = batch_customer
            parsed["customer_inferred"] = True
            parsed["customer_missing"] = False
            payload = item.get("workflow_order_payload")
            if isinstance(payload, dict):
                payload["customer"] = batch_customer


def _split_customer_goods_by_erp(text: str, caller, color: str = "") -> tuple[str, str] | None:
    candidate = _extract_goods_from_remark(text)
    candidate = re.sub(r"^(客户|客人|客户名称)\s*:?", "", candidate).strip()
    if not candidate or not _looks_like_goods_text(candidate):
        return None

    max_customer_len = min(8, len(candidate) - 1)
    for idx in range(2, max_customer_len + 1):
        customer_part = _clean_field_value(candidate[:idx])
        goods_part = _clean_goods_value(candidate[idx:])
        if not customer_part or not goods_part or not _looks_like_goods_text(goods_part):
            continue
        customer_name = _find_exact_customer_name(customer_part, caller)
        if not customer_name:
            continue
        if find_product_by_goods_name(goods_part, caller, color):
            return customer_name, goods_part
    return None


def _find_exact_customer_name(keyword: str, caller) -> str:
    keyword = _clean_field_value(keyword)
    if _is_invalid_customer(keyword):
        return ""
    try:
        rows = caller.call("customer_query", keyword=keyword)
    except Exception as e:
        logger.warning(f"OCR客户纠错查询失败: {keyword}, error={e}")
        return ""
    for row in rows or []:
        name = _clean_field_value(str(row.get("name") or row.get("customer_name") or ""))
        if name == keyword:
            return name
    if len(rows or []) == 1:
        name = _clean_field_value(str((rows or [])[0].get("name") or (rows or [])[0].get("customer_name") or ""))
        if keyword in name or name in keyword:
            return name
    return ""


def _infer_customer_from_ocr_lines(lines: list[str], goods_name: str, caller) -> str:
    for line in lines:
        text = re.sub(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", "", line)
        text = _clean_field_value(re.sub(r"^(客户|客人|客户名称)\s*:?", "", text))
        if not text or _is_invalid_customer(text):
            continue
        if goods_name and goods_name.replace(" ", "") in text.replace(" ", ""):
            continue
        if _looks_like_goods_text(text) or _parse_quantity(text) or _extract_craft_terms(text):
            continue
        if re.fullmatch(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", text):
            continue
        customer_name = _find_exact_customer_name(text, caller)
        if customer_name:
            return customer_name
    return ""


def find_product_by_goods_name(goods_name: str, caller, color: str = "") -> dict | None:
    """
    在 ERP 商品库中查找唯一可信商品。
    """
    if not goods_name:
        return None

    matcher = ProductMatcher(caller, colors=list(STANDARD_COLORS))
    match = matcher.match(
        goods_name,
        color=color,
        use_inventory=True,
        allow_product_fallback=True,
        product_limit=100,
        inventory_limit=80,
        allow_llm=True,
    )
    if not match.product:
        return None
    product = match.product
    if not product.get("simple_desc"):
        try:
            detail = caller.call("product_info", product_id=int(product["id"]))
            if detail:
                product = {**product, **detail}
        except Exception as e:
            logger.warning(f"OCR商品详情补全失败: {e}")
    return product


def _case_pack_text_from_product(row: dict) -> str:
    simple_desc = str(row.get("simple_desc") or row.get("piece_text") or "").strip()
    if simple_desc:
        return simple_desc
    case_pack_qty = str(row.get("case_pack_qty") or "").strip()
    if case_pack_qty:
        return f"1件{case_pack_qty}套"
    return ""


def find_case_pack_by_goods_name(goods_name: str, caller) -> dict | None:
    """Find a reliable case-pack row by SPU name, even when OCR color is not a SKU color."""
    if not goods_name:
        return None
    terms = _keyword_terms(goods_name)
    for keyword in _product_search_keywords(goods_name):
        try:
            rows = caller.call("product_search", keyword=keyword) or []
        except Exception as e:
            logger.warning(f"OCR件规兜底查询失败: {goods_name}, error={e}")
            continue

        candidates = []
        for row in rows:
            title = str(row.get("title") or row.get("name") or "")
            normalized_title = _normalize_goods_keyword(title).replace(" ", "")
            if terms and not all(_normalize_goods_keyword(term).replace(" ", "") in normalized_title for term in terms):
                continue
            simple_desc = _case_pack_text_from_product(row)
            per_piece = parse_per_piece(simple_desc)
            if per_piece > 1:
                candidates.append({**row, "simple_desc": simple_desc})

        per_values = {parse_per_piece(str(row.get("simple_desc") or "")) for row in candidates}
        per_values.discard(1)
        if candidates and len(per_values) == 1:
            return candidates[0]
    return None


def _normalize_goods_keyword(goods_name: str) -> str:
    return normalize_product_name(goods_name, colors=STANDARD_COLORS, specs=PRODUCT_SPECS)


def _product_search_keywords(goods_name: str) -> list[str]:
    normalized = _normalize_goods_keyword(goods_name)
    specs = PRODUCT_SPECS
    keywords = [normalized]
    for spec in specs:
        if spec in normalized:
            brand = normalized.replace(spec, "").strip()
            if brand:
                keywords.append(f"{brand} {spec}")
                keywords.append(brand)
            keywords.append(spec)
            break
    compact = normalized.replace(" ", "")
    if compact != normalized:
        keywords.append(compact)
    return list(dict.fromkeys(k for k in keywords if k))


def _keyword_terms(keyword: str) -> list[str]:
    normalized = _normalize_goods_keyword(keyword)
    specs = PRODUCT_SPECS
    for spec in specs:
        if spec in normalized:
            brand = normalized.replace(spec, "").strip()
            return [term for term in (brand, spec) if term]
    return [normalized] if normalized else []


def _select_image_product(results: list[dict], keyword: str, color: str = "") -> dict | None:
    candidates = results or []
    if color:
        candidates = [row for row in candidates if color in str(row.get("spec", ""))]
    terms = _keyword_terms(keyword)
    if terms:
        candidates = [
            row for row in candidates
            if all(
                _normalize_goods_keyword(term).replace(" ", "")
                in _normalize_goods_keyword(str(row.get("title", ""))).replace(" ", "")
                for term in terms
            )
        ]
    return candidates[0] if len(candidates) == 1 else None


def _select_image_inventory_product(rows: list[dict], keyword: str, color: str = "") -> dict | None:
    candidates = rows or []
    if color:
        candidates = [row for row in candidates if color in str(row.get("【颜色】", ""))]
    terms = _keyword_terms(keyword)
    if terms:
        candidates = [
            row for row in candidates
            if all(
                _normalize_goods_keyword(term).replace(" ", "")
                in _normalize_goods_keyword(str(row.get("产品名称", ""))).replace(" ", "")
                for term in terms
            )
        ]
    seen = set()
    unique = []
    for row in candidates:
        key = (row.get("product_id"), row.get("【颜色】"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    if len(unique) != 1:
        return None
    row = unique[0]
    return {
        "id": row.get("product_id"),
        "title": row.get("产品名称"),
        "spec": row.get("【颜色】"),
        "simple_desc": row.get("simple_desc", ""),
        "price": 0,
    }


def create_workflow_order(parsed: dict, image_url: str, caller) -> dict | None:
    """
    创建工作流订单
    调用 WorkflowOrderSave
    """
    try:
        customer_name = parsed.get("customer_name") or "散客"
        if _is_invalid_customer(customer_name):
            customer_name = "散客"
        result = caller.call(
            "workflow_order_save",
            customer_name=customer_name,
            goods_name=parsed.get("goods_name", ""),
            order_quantity=parsed.get("quantity", 1),
            color=parsed.get("color", ""),
            order_images=[image_url] if image_url else [],
            is_screen_print=1 if any(kw in parsed.get("craft", "") for kw in ["丝印", "印刷"]) else 0,
            remark=parsed.get("craft", ""),
        )
        logger.info(f"工作流订单创建: {result}")
        return result
    except Exception as e:
        logger.error(f"工作流订单创建失败: {e}")
        return None


def parse_per_piece(simple_desc: str) -> int:
    """从 simple_desc 提取每件套数"""
    return parse_unit_from_simple_desc(simple_desc) or 1
