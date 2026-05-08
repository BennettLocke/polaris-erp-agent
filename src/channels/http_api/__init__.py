"""
HTTP API 渠道（预留 WebUI 和外部调用）
提供 RESTful API 供前端或外部系统调用 Agent
"""
import json
import os
import uuid
import time
from pathlib import Path
from urllib.parse import urlencode
from flask import Flask, request, jsonify, Response, send_from_directory
from werkzeug.utils import secure_filename
from src.core.agent import Agent
from src.utils import get_logger

logger = get_logger("sjagent.http_api")

app = Flask(__name__)
_agent: Agent | None = None
UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "data" / "uploads"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}
SHOPXO_AUTH_CACHE: dict[str, tuple[float, dict]] = {}
SHOPXO_AUTH_CACHE_TTL = 86400 * 30


def _api_exception_response(e: Exception):
    response = getattr(e, "response", None)
    if isinstance(response, dict) and response:
        return jsonify(response)
    return jsonify({"code": 500, "msg": str(e)}), 500


def _shopxo_base_url() -> str:
    try:
        from src.core.config import get_config
        configured = get_config().get("shopxo.base_url", "") or ""
        erp_api_base = get_config().erp_api_base or ""
    except Exception:
        configured = ""
        erp_api_base = ""
    base = os.environ.get("SHOPXO_BASE_URL") or configured
    if not base and erp_api_base:
        base = erp_api_base.split("/api.php", 1)[0]
    return (base or "https://shop.513sjbz.com").rstrip("/")


def _shopxo_api_url(
    controller: str,
    action: str,
    token: str = "",
    uuid_value: str = "",
    extra_params: dict | None = None,
) -> str:
    application = os.environ.get("SHOPXO_APPLICATION", "app")
    client_type = os.environ.get("SHOPXO_CLIENT_TYPE", "weixin")
    client_brand = os.environ.get("SHOPXO_CLIENT_BRAND", "WeChat")
    uuid_value = uuid_value or f"sjagent_{uuid.uuid4().hex}"
    params = (
        f"s={controller}/{action}"
        f"&application={application}"
        f"&application_client_type={client_type}"
        f"&application_client_brand={client_brand}"
        f"&uuid={uuid_value}"
        f"&ajax=ajax"
    )
    if token:
        params += f"&token={token}"
    if extra_params:
        params += f"&{urlencode(extra_params)}"
    return f"{_shopxo_base_url()}/api.php?{params}"


def _shopxo_post(controller: str, action: str, data: dict | None = None, token: str = "", uuid_value: str = "") -> dict:
    import requests
    resp = requests.post(
        _shopxo_api_url(controller, action, token=token, uuid_value=uuid_value),
        data=data or {},
        timeout=15,
    )
    resp.raise_for_status()
    result = resp.json()
    return result if isinstance(result, dict) else {"code": -1, "msg": "商城返回格式异常", "data": result}


def _shopxo_get(controller: str, action: str, token: str = "", uuid_value: str = "", extra_params: dict | None = None):
    import requests
    resp = requests.get(
        _shopxo_api_url(controller, action, token=token, uuid_value=uuid_value, extra_params=extra_params),
        timeout=15,
    )
    resp.raise_for_status()
    return resp


def _nested_token(value) -> str:
    if isinstance(value, dict):
        for key in ("token", "user_token", "access_token"):
            if value.get(key):
                return str(value.get(key))
        for item in value.values():
            token = _nested_token(item)
            if token:
                return token
    if isinstance(value, list):
        for item in value:
            token = _nested_token(item)
            if token:
                return token
    return ""


def _shopxo_user_by_account(accounts: str) -> dict | None:
    """Resolve a ShopXO user after ShopXO itself has already accepted the login."""
    try:
        from src.engine.db_client import get_db_client
        db = get_db_client()
        rows = db.query(
            """
            SELECT
                u.id, u.username, u.nickname, u.mobile, u.email, u.avatar,
                u.status, u.user_role,
                up.token AS platform_token
            FROM sxo_user u
            LEFT JOIN sxo_user_platform up
                ON up.user_id = u.id AND up.platform = %s
            WHERE u.is_delete_time = 0
              AND u.is_logout_time = 0
              AND (u.username = %s OR u.mobile = %s OR u.email = %s OR u.number_code = %s)
            ORDER BY up.token DESC
            LIMIT 1
            """,
            (
                os.environ.get("SHOPXO_CLIENT_TYPE", "weixin"),
                accounts,
                accounts,
                accounts,
                accounts,
            ),
        )
    except Exception as e:
        logger.warning(f"商城登录用户资料兜底查询失败: {e}")
        return None
    if not rows:
        return None
    row = dict(rows[0])
    token = row.pop("platform_token", "") or f"sj_local_{uuid.uuid4().hex}"
    return _normalize_shopxo_user(row, token)


def _shopxo_user_permission(user_id) -> dict:
    if not user_id:
        return {"status": None, "user_role": None, "is_admin": False, "miniapp_allowed": False}
    try:
        from src.engine.db_client import get_db_client
        db = get_db_client()
        rows = db.query(
            """
            SELECT id, status, user_role
            FROM sxo_user
            WHERE id = %s
              AND is_delete_time = 0
              AND is_logout_time = 0
            LIMIT 1
            """,
            (user_id,),
        )
    except Exception as e:
        logger.warning(f"商城用户权限查询失败: {e}")
        return {"status": None, "user_role": None, "is_admin": False, "miniapp_allowed": False}
    if not rows:
        return {"status": None, "user_role": None, "is_admin": False, "miniapp_allowed": False}
    row = rows[0]
    status = int(row.get("status") or 0)
    user_role = int(row.get("user_role") or 0)
    is_admin = status == 0 and user_role == 0
    return {
        "status": status,
        "user_role": user_role,
        "is_admin": is_admin,
        "miniapp_allowed": is_admin,
    }


def _auth_token_from_request() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return request.headers.get("X-Shopxo-Token", "") or request.args.get("token", "")


def _normalize_shopxo_user(user: dict, token: str = "") -> dict:
    if not isinstance(user, dict):
        user = {}
    user_id = user.get("id") or user.get("user_id") or ""
    display_name = (
        user.get("user_name_view")
        or user.get("nickname")
        or user.get("username")
        or user.get("mobile")
        or user.get("email")
        or (f"用户{user_id}" if user_id else "商城用户")
    )
    normalized = {
        "id": user_id,
        "token": token or user.get("token") or "",
        "display_name": display_name,
        "nickname": user.get("nickname") or "",
        "username": user.get("username") or "",
        "mobile": user.get("mobile") or "",
        "email": user.get("email") or "",
        "avatar": user.get("avatar") or "",
        "raw": user,
    }
    normalized.update(_shopxo_user_permission(user_id))
    return normalized


def _shopxo_user_can_access_miniapp(user: dict | None) -> bool:
    return bool(isinstance(user, dict) and user.get("miniapp_allowed") is True)


def _verify_shopxo_token(token: str, force: bool = False) -> dict | None:
    if not token:
        return None
    now = time.time()
    cached = SHOPXO_AUTH_CACHE.get(token)
    if cached and not force and cached[0] > now:
        return cached[1]
    if token.startswith("sj_local_"):
        return cached[1] if cached and cached[0] > now else None
    result = _shopxo_post("user", "tokenuserinfo", token=token)
    if int(result.get("code", -1)) != 0 or not isinstance(result.get("data"), dict):
        SHOPXO_AUTH_CACHE.pop(token, None)
        return None
    user = _normalize_shopxo_user(result.get("data") or {}, token)
    SHOPXO_AUTH_CACHE[token] = (now + 300, user)
    return user


@app.before_request
def _miniapp_auth_guard():
    if request.method == "OPTIONS":
        return None
    path = request.path or ""
    if not path.startswith("/api/"):
        return None
    if path.startswith("/api/auth/"):
        return None
    if request.headers.get("X-SJ-Client") != "miniapp":
        return None
    token = _auth_token_from_request()
    try:
        user = _verify_shopxo_token(token)
    except Exception as e:
        logger.warning(f"商城用户 token 校验异常: {e}")
        user = None
    if not user:
        return jsonify({"code": 401, "msg": "请先登录商城账号"}), 401
    if not _shopxo_user_can_access_miniapp(user):
        return jsonify({"code": 401, "msg": "当前账号不是管理员，暂无小程序业务权限"}), 401
    request.shopxo_user = user
    return None


def _request_user_id(default: str = "http_user") -> str:
    user = getattr(request, "shopxo_user", None)
    if isinstance(user, dict) and user.get("id"):
        return f"shopxo_{user.get('id')}"
    return default


def _session_snapshot(session_id: str) -> dict:
    """Return lightweight session state for the WebUI."""
    from src.core.session import SessionManager
    session = SessionManager(session_id)
    state = session.get_state() if session.has_pending() else None
    pending_intent = session.get_pending_intent() if session.has_pending() else None
    pending_action = ""
    if isinstance(state, dict):
        pending_action = state.get("pending_action", "")
    return {
        "has_pending": session.has_pending(),
        "pending_intent": pending_intent,
        "pending_action": pending_action,
        "state": state or {},
        "last_extraction": session.get_meta("last_extraction", {}),
    }


def _extract_list_rows(result: dict) -> list[dict]:
    """Extract list rows from the ERP API's common response shapes."""
    if not isinstance(result, dict) or result.get("error"):
        return []
    data = result.get("data", result)
    if isinstance(data, dict):
        return data.get("list") or data.get("data") or data.get("rows") or []
    return data if isinstance(data, list) else []


def _sales_detail_data(result: dict) -> dict:
    """Extract the most useful sales detail object from SalesDetail."""
    if not isinstance(result, dict) or result.get("error"):
        return {}
    data = result.get("data", result)
    if not isinstance(data, dict):
        return {}
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    merged = dict(data)
    merged.update({k: v for k, v in info.items() if k not in merged or not merged.get(k)})
    return merged


def _first_text_value(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _customer_name_from_id(caller, customer_id, cache: dict) -> str:
    """Resolve a customer id to a display name via CompanyList/customer_query."""
    if not customer_id:
        return ""
    key = str(customer_id)
    if key in cache:
        return cache[key]

    def pick(rows: list[dict]) -> str:
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_id = row.get("id") or row.get("customer_id") or row.get("company_id")
            if str(row_id or "") != key:
                continue
            return _first_text_value(
                row,
                ("name", "customer_name", "company_name", "title", "contacts_name"),
            )
        return ""

    name = ""
    try:
        rows = caller.call("customer_query", keyword=key)
    except Exception as e:
        logger.warning(f"客户名称补充失败: customer_id={customer_id}, error={e}")
        rows = []
    if isinstance(rows, list):
        name = pick(rows)

    if not name:
        if "__all_customers_by_id" not in cache:
            try:
                all_rows = caller.call("customer_query", keyword="")
            except Exception as e:
                logger.warning(f"客户列表补充失败: {e}")
                all_rows = []
            customer_map = {}
            for row in all_rows if isinstance(all_rows, list) else []:
                if not isinstance(row, dict):
                    continue
                row_id = row.get("id") or row.get("customer_id") or row.get("company_id")
                row_name = _first_text_value(
                    row,
                    ("name", "customer_name", "company_name", "title", "contacts_name"),
                )
                if row_id and row_name:
                    customer_map[str(row_id)] = row_name
            cache["__all_customers_by_id"] = customer_map
        name = cache["__all_customers_by_id"].get(key, "")

    cache[key] = name
    return name


def _enrich_sales_rows(caller, rows: list[dict]) -> list[dict]:
    """SalesList often returns only customer_id; enrich recent rows with SalesDetail."""
    enriched = []
    customer_cache = {}
    for row in rows:
        item = dict(row)
        sid = item.get("id") or item.get("sales_id") or item.get("sales_no")
        detail = {}
        if sid:
            try:
                detail = _sales_detail_data(caller.call("sales_detail", sales_id=int(sid)))
            except Exception as e:
                logger.warning(f"销售单详情补充失败: sales_id={sid}, error={e}")
                detail = {}
        customer_name = (
            _first_text_value(detail, ("customer_name", "company_name", "customer", "name"))
            or _first_text_value(item, ("customer_name", "company_name", "customer", "name"))
        )
        customer_id = item.get("customer_id") or item.get("company_id") or detail.get("customer_id") or detail.get("company_id")
        if customer_name and customer_name.isdigit() and customer_id:
            customer_name = ""
        if not customer_name:
            customer_name = _customer_name_from_id(caller, customer_id, customer_cache)
        if customer_name:
            item["customer_name"] = customer_name
            item["customer_display"] = customer_name
        else:
            item["customer_display"] = "客户未识别"
        if detail.get("total_price") and not item.get("total_price"):
            item["total_price"] = detail.get("total_price")
        enriched.append(item)
    return enriched


def _safe_json(data):
    """Make nested data safe for Flask JSON responses."""
    return json.loads(json.dumps(data, ensure_ascii=False, default=str))


def _as_money(value) -> str:
    if value in (None, ""):
        return "0.00"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _date_text(timestamp) -> str:
    try:
        ts = int(timestamp or 0)
    except (TypeError, ValueError):
        ts = 0
    if not ts:
        return ""
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _sales_status_text(status) -> str:
    labels = {
        0: "待提交",
        1: "待审核",
        2: "审核失败",
        3: "待发货",
        4: "部分发货",
        5: "已完成",
        6: "已取消",
        7: "已关闭",
    }
    try:
        return labels.get(int(status), f"状态{status}")
    except (TypeError, ValueError):
        return "未知状态"


def _first_product_line(detail: list[dict]) -> str:
    if not detail:
        return "暂无商品明细"
    item = detail[0] if isinstance(detail[0], dict) else {}
    title = item.get("title") or item.get("product_title") or item.get("name") or "商品"
    spec = item.get("spec") or ""
    qty = item.get("buy_number") or item.get("quantity") or item.get("number") or ""
    price = _as_money(item.get("price"))
    unit = "套"
    line = f"{title}{(' ' + spec) if spec else ''}"
    if qty != "":
        line += f" x{qty}{unit}"
    if price and price != "0.00":
        line += f"  ¥{price}"
    return line


def _sales_card(caller, row: dict, customer_cache: dict) -> dict:
    sid = row.get("id") or row.get("sales_id") or row.get("sales_no")
    detail_result = {}
    if sid:
        try:
            detail_result = caller.call("sales_detail", sales_id=int(sid))
        except Exception as e:
            logger.warning(f"销售单卡片详情查询失败: sales_id={sid}, error={e}")

    detail_data = _sales_detail_data(detail_result)
    detail_rows = []
    if isinstance(detail_result, dict):
        data = detail_result.get("data") if isinstance(detail_result.get("data"), dict) else {}
        detail_rows = data.get("detail") or detail_data.get("detail") or []
    info = detail_data or row
    customer_id = info.get("customer_id") or row.get("customer_id")
    customer_name = (
        _first_text_value(info, ("customer_name", "company_name", "customer", "name"))
        or _first_text_value(row, ("customer_display", "customer_name", "company_name", "customer", "name"))
        or _customer_name_from_id(caller, customer_id, customer_cache)
        or "客户未识别"
    )
    sales_no = info.get("sales_no") or row.get("sales_no") or str(sid or "")
    products = []
    for item in detail_rows if isinstance(detail_rows, list) else []:
        if not isinstance(item, dict):
            continue
        products.append({
            "title": item.get("title") or item.get("product_title") or item.get("name") or "商品",
            "spec": item.get("spec") or "",
            "quantity": item.get("buy_number") or item.get("number") or 0,
            "price": _as_money(item.get("price")),
            "total_price": _as_money(item.get("total_price")),
            "image": item.get("images") or item.get("image") or "",
            "warehouse_id": item.get("warehouse_id"),
        })

    return {
        "id": sid,
        "sales_no": sales_no,
        "customer_name": customer_name,
        "status": info.get("status", row.get("status")),
        "status_text": _sales_status_text(info.get("status", row.get("status"))),
        "pay_status": info.get("pay_status", row.get("pay_status")),
        "total_price": _as_money(info.get("total_price", row.get("total_price"))),
        "buy_number_count": info.get("buy_number_count", row.get("buy_number_count", 0)),
        "date_text": _date_text(info.get("add_time", row.get("add_time"))),
        "product_summary": _first_product_line(products),
        "products": products,
        "note": info.get("note") or info.get("admin_note") or "",
    }


def _workflow_card(row: dict) -> dict:
    if not isinstance(row, dict):
        row = {}
    order_time = row.get("order_time_text") or _date_text(row.get("order_time") or row.get("add_time"))
    images = row.get("order_images") or []
    if isinstance(images, str):
        images = [images] if images else []
    status = row.get("order_type_text")
    if not status:
        status = "完成" if int(row.get("order_type") or 0) == 1 else "待完成"
    return {
        "id": row.get("id"),
        "customer_name": row.get("customer_name") or "客户未填写",
        "customer_phone": row.get("customer_phone") or "",
        "goods_name": row.get("goods_name") or "商品未填写",
        "goods_color": row.get("goods_color") or "",
        "order_quantity": row.get("order_quantity") or 0,
        "is_screen_print": int(row.get("is_screen_print") or 0),
        "is_screen_print_text": row.get("is_screen_print_text") or ("是" if int(row.get("is_screen_print") or 0) else "否"),
        "is_made": int(row.get("is_made") or 0),
        "is_delivered": int(row.get("is_delivered") or 0),
        "order_type": int(row.get("order_type") or 0),
        "status_text": status,
        "order_time_text": order_time,
        "complete_time_text": row.get("complete_time_text") or "",
        "order_images": images,
    }


def _clean_product_title(title: str) -> str:
    return str(title or "商品").replace("【", "").replace("】", "")


def _compact_product_title(title: str) -> str:
    return (
        _clean_product_title(title)
        .replace(" ", "")
        .replace("　", "")
        .replace("-", "")
        .replace("_", "")
    )


def _product_series_keyword(title: str) -> str:
    text = _compact_product_title(title)
    markers = (
        "短半斤",
        "长款半斤",
        "五格短半斤",
        "二三两",
        "2大盒",
        "二大盒",
        "两大盒",
        "三小盒",
        "六小盒",
        "3小盒",
        "6小盒",
        "半斤",
        "三两",
        "二两",
        "一两",
        "3两",
        "2两",
        "1两",
    )
    positions = [text.find(marker) for marker in markers if text.find(marker) > 0]
    if not positions:
        return text
    return text[:min(positions)]


def _normalize_warehouse_name(name: str) -> str:
    text = str(name or "")
    if "百鑫" in text:
        return "百鑫仓库"
    if "自己" in text or "店" in text:
        return "店里仓库"
    return text or "仓库"


def _is_gift_box_title(title: str) -> bool:
    text = _clean_product_title(title)
    keywords = (
        "半斤",
        "3两",
        "三两",
        "2两",
        "二两",
        "1两",
        "一两",
        "2大盒",
        "二大盒",
        "两大盒",
        "3小盒",
        "三小盒",
        "6小盒",
        "六小盒",
    )
    return any(keyword in text for keyword in keywords)


def _piece_text(simple_desc: str) -> str:
    text = str(simple_desc or "").strip()
    if not text:
        return ""
    import re
    match = re.search(r"(\d+)\s*(?:套|个|张)?\s*/\s*件", text)
    if match:
        return f"1件{match.group(1)}个"
    match = re.search(r"(\d+)\s*(?:套|个|张)", text)
    if match:
        return f"1件{match.group(1)}个"
    return text.replace("规格：", "")


def _inventory_cards(rows: list[dict], limit: int) -> list[dict]:
    cards: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        product_id = row.get("product_id") or row.get("产品ID") or row.get("id")
        title = row.get("产品名称") or row.get("title") or row.get("name") or "商品"
        if not _is_gift_box_title(title):
            continue
        color = row.get("【颜色】") or row.get("spec") or row.get("color") or ""
        key = _clean_product_title(title)
        stock = row.get("库存数量") or row.get("inventory") or row.get("stock") or 0
        try:
            stock = int(float(stock))
        except (TypeError, ValueError):
            stock = 0
        if stock <= 0:
            continue
        warehouse = _normalize_warehouse_name(row.get("【仓库】") or row.get("warehouse_name") or row.get("warehouse") or "仓库")
        if key not in cards:
            cards[key] = {
                "product_id": product_id,
                "title": key,
                "piece_text": _piece_text(row.get("simple_desc") or row.get("simple_desc_text") or ""),
                "total_stock": 0,
                "status_text": "有库存",
                "colors": [],
                "_color_map": {},
            }
        cards[key]["total_stock"] += stock
        if not cards[key].get("piece_text"):
            cards[key]["piece_text"] = _piece_text(row.get("simple_desc") or "")
        color_key = str(color or "默认")
        if color_key not in cards[key]["_color_map"]:
            cards[key]["_color_map"][color_key] = {
                "product_id": product_id,
                "color": color_key,
                "total_stock": 0,
                "warehouses": {
                    "百鑫仓库": 0,
                    "店里仓库": 0,
                },
            }
            cards[key]["colors"].append(cards[key]["_color_map"][color_key])
        color_row = cards[key]["_color_map"][color_key]
        if not color_row.get("product_id") and product_id:
            color_row["product_id"] = product_id
        color_row["total_stock"] += stock
        color_row["warehouses"][warehouse] = color_row["warehouses"].get(warehouse, 0) + stock
    result = list(cards.values())
    for card in result:
        card.pop("_color_map", None)
        card["colors"] = [item for item in card.get("colors", []) if item.get("total_stock", 0) > 0]
        total = card["total_stock"]
        if total <= 0:
            card["status_text"] = "缺货"
        elif total <= 10:
            card["status_text"] = "库存紧张"
        else:
            card["status_text"] = "有库存"
    result.sort(key=lambda item: item.get("total_stock", 0), reverse=True)
    return result[:limit]


def _merge_product_color_options(card: dict, products: list[dict]) -> None:
    """Add same-product color options that currently have no stock rows."""
    color_map = {item.get("color"): item for item in card.get("colors", [])}
    card_title = _compact_product_title(card.get("title") or "")
    for product in products:
        title = _compact_product_title(product.get("title") or product.get("产品名称") or product.get("name") or "")
        if title != card_title and card_title not in title and title not in card_title:
            continue
        color = str(product.get("spec") or product.get("【颜色】") or product.get("color") or "默认")
        product_id = product.get("id") or product.get("product_id") or product.get("产品ID")
        if color in color_map:
            if product_id and not color_map[color].get("product_id"):
                color_map[color]["product_id"] = product_id
            continue
        color_row = {
            "product_id": product_id,
            "color": color,
            "total_stock": 0,
            "warehouses": {
                "百鑫仓库": 0,
                "店里仓库": 0,
            },
        }
        card.setdefault("colors", []).append(color_row)
        color_map[color] = color_row


def _load_product_color_options(caller, card: dict) -> list[dict]:
    keywords = []
    title = card.get("title") or ""
    series = _product_series_keyword(title)
    for keyword in (title, series):
        keyword = str(keyword or "").strip()
        if keyword and keyword not in keywords:
            keywords.append(keyword)
    rows: list[dict] = []
    seen_ids: set[str] = set()
    for keyword in keywords:
        result = caller.call("product_search", keyword=keyword)
        if not isinstance(result, list):
            continue
        for item in result:
            product_id = str(item.get("id") or item.get("product_id") or item.get("产品ID") or "")
            key = product_id or f"{item.get('title')}|{item.get('spec')}"
            if key in seen_ids:
                continue
            seen_ids.add(key)
            rows.append(item)
    return rows


def _allowed_image(filename: str) -> bool:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return suffix in ALLOWED_IMAGE_EXTENSIONS


def _format_image_result(result: dict) -> str:
    items = result.get("items") or []
    if items:
        workflow_ids = []
        for item in items:
            workflow = item.get("workflow_order") or {}
            if isinstance(workflow, dict) and (workflow.get("id") or workflow.get("data")):
                data = workflow.get("data") if isinstance(workflow.get("data"), dict) else workflow
                order_id = data.get("id") or data.get("order_id") or data.get("workflow_order_id")
                if order_id:
                    workflow_ids.append(str(order_id))

        lines = [f"图片识别完成，共 {len(items)} 个设计稿。"]
        if workflow_ids:
            lines.append("已创建工作流订单：" + "、".join(workflow_ids))
        for idx, item in enumerate(items, 1):
            parsed = item.get("parsed") or {}
            workflow = item.get("workflow_order") or {}
            order_id = ""
            if isinstance(workflow, dict) and (workflow.get("id") or workflow.get("data")):
                data = workflow.get("data") if isinstance(workflow.get("data"), dict) else workflow
                order_id = data.get("id") or data.get("order_id") or data.get("workflow_order_id") or ""

            summary = [
                parsed.get("customer_name") or "客户未识别",
                (parsed.get("goods_name") or "礼盒未识别") + (f" {parsed.get('color')}" if parsed.get("color") else ""),
                f"{parsed.get('quantity') or 1}{parsed.get('unit') or '套'}",
            ]
            if parsed.get("craft"):
                summary.append(parsed.get("craft"))
            if order_id:
                summary.append(f"工作流{order_id}")
            lines.append(f"{idx}. " + " | ".join(summary))

            if item.get("error"):
                lines.append(f"   提示：{item['error']}")
        warnings = [
            warning
            for item in items
            for warning in (item.get("product_warning") or [])
        ]
        if warnings:
            lines.append(f"提示：{len(warnings)} 个商品暂未精确匹配商品库，确认开单时会继续自动匹配；仍找不到再问你。")
        if result.get("error"):
            lines.append(f"\n整体处理提示：{result['error']}")
        return "\n".join(lines)

    parsed = result.get("parsed") or {}
    workflow = result.get("workflow_order") or {}
    warnings = result.get("product_warning") or []
    lines = ["图片识别完成。"]

    extracted = []
    if parsed.get("customer_name"):
        extracted.append(f"客户：{parsed.get('customer_name')}")
    if parsed.get("goods_name"):
        extracted.append(f"礼盒：{parsed.get('goods_name')}")
    if parsed.get("color"):
        extracted.append(f"颜色：{parsed.get('color')}")
    if parsed.get("quantity"):
        extracted.append(f"数量：{parsed.get('quantity')}{parsed.get('unit') or ''}")
    if parsed.get("craft"):
        extracted.append(f"工艺：{parsed.get('craft')}")
    if extracted:
        lines.append("\n提取结果：")
        lines.extend(extracted)

    if isinstance(workflow, dict) and (workflow.get("id") or workflow.get("data")):
        data = workflow.get("data") if isinstance(workflow.get("data"), dict) else workflow
        order_id = data.get("id") or data.get("order_id") or data.get("workflow_order_id")
        if order_id:
            lines.append(f"\n已创建工作流订单：{order_id}")
        else:
            lines.append("\n已提交工作流订单。")
    elif workflow:
        lines.append("\n已提交工作流订单。")

    if warnings:
        lines.append("\n提示：商品暂未精确匹配商品库，确认开单时会继续自动匹配；仍找不到再问你。")
    if result.get("error"):
        lines.append(f"\n处理提示：{result['error']}")

    return "\n".join(lines)


def _image_items(result: dict) -> list[dict]:
    items = result.get("items") or []
    if items:
        return [item for item in items if isinstance(item, dict)]
    return [result]


def _order_params_from_image_result(result: dict) -> dict:
    products = []
    customers = []
    for item in _image_items(result):
        parsed = item.get("parsed") or {}
        goods_name = parsed.get("goods_name") or ""
        if not goods_name:
            continue
        customer = parsed.get("customer_name") or ""
        if customer and customer not in customers:
            customers.append(customer)
        products.append({
            "name": goods_name,
            "qty": int(parsed.get("quantity") or 1),
            "quantity": int(parsed.get("quantity") or 1),
            "unit": parsed.get("unit") or "套",
            "color": parsed.get("color") or "",
        })
    return {
        "customer": customers[0] if customers else "",
        "customers": customers,
        "products": products,
    }


def _image_has_open_order_marker(result: dict) -> bool:
    return any((item.get("parsed") or {}).get("has_kaipiao") for item in _image_items(result))


def _handle_image_sales_flow(result: dict, session, response_text: str) -> str:
    params = _order_params_from_image_result(result)
    products = params.get("products") or []
    customers = params.get("customers") or []
    if not products:
        return response_text
    if len(customers) > 1:
        return (
            response_text
            + "\n\n开单提示：识别到多个客户，不能合并成一张销售单。请分别确认每个客户的开单内容。"
        )

    if _image_has_open_order_marker(result):
        from src.skills.order_flow.workflow import OrderFlowWorkflow
        order_result = OrderFlowWorkflow().execute("图片识别结果自动开单", params=params)
        if order_result.get("status") == "ask":
            session.save_pending("order", order_result["state"])
            return response_text + "\n\n开单需要确认：\n" + order_result["question"]
        return response_text + "\n\n" + order_result.get("reply", "开单流程已处理。")

    session.save_pending("order", {
        "pending_action": "confirm_image_sales",
        "order_params": params,
    })
    lines = [
        response_text,
        "",
        "备注里没有看到「开单」或「下单」，是否需要继续开销售单？",
        "回复「确认」继续开单，回复「取消」只保留工作流订单。",
    ]
    return "\n".join(lines)


def init_api(agent: Agent):
    """初始化 HTTP API"""
    global _agent
    _agent = agent
    try:
        from src.services.aliyun_asr import start_hotword_scheduler
        if start_hotword_scheduler():
            logger.info("阿里云 ASR 热词每日同步任务已启动")
    except Exception as e:
        logger.warning(f"阿里云 ASR 热词同步任务未启动: {e}")


@app.route("/web", methods=["GET"])
def webui():
    """WebUI 聊天界面"""
    from src.channels.http_api.webui import get_webui_html
    return Response(get_webui_html(), content_type="text/html; charset=utf-8")


@app.route("/api/images/file/<path:filename>", methods=["GET"])
def image_file(filename: str):
    """Serve locally uploaded images for WebUI preview."""
    safe_name = secure_filename(filename)
    if not safe_name:
        return jsonify({"code": 400, "msg": "invalid filename"}), 400
    return send_from_directory(UPLOAD_DIR, safe_name)


@app.route("/api/agent/chat", methods=["POST"])
def chat():
    """
    对话接口
    POST /api/agent/chat
    {
        "message": "客户银茗，要1件喜悦三小盒",
        "user_id": "user_001",
        "session_id": "session_001"  // 可选
    }

    Response:
    {
        "code": 0,
        "data": {
            "response": "处理结果...",
            "session_id": "xxx"
        }
    }
    """
    global _agent

    if _agent is None:
        return jsonify({"code": 500, "msg": "Agent not initialized"}), 500

    body = request.get_json()
    message = body.get("message", "")
    user_id = _request_user_id(body.get("user_id", "http_user"))
    session_id = body.get("session_id", f"http_{int(time.time())}")

    if not message:
        return jsonify({"code": 400, "msg": "message is required"}), 400

    try:
        response = _agent.run(
            user_input=message,
            user_id=user_id,
            session_id=session_id,
        )
        return jsonify({
            "code": 0,
            "data": {
                "response": response,
                "session_id": session_id,
                "session": _session_snapshot(session_id),
            }
        })
    except Exception as e:
        logger.error(f"Agent 调用异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/agent/chat/stream", methods=["POST"])
def chat_stream():
    """
    流式对话接口（SSE）
    POST /api/agent/chat/stream
    {
        "message": "你好",
        "user_id": "user_001",
        "session_id": "session_001"
    }

    Response: SSE stream
    data: {"type": "token", "text": "你"}
    data: {"type": "token", "text": "好"}
    data: {"type": "done", "session_id": "xxx"}
    """
    global _agent

    if _agent is None:
        return jsonify({"code": 500, "msg": "Agent not initialized"}), 500

    body = request.get_json()
    message = body.get("message", "")
    user_id = _request_user_id(body.get("user_id", "http_user"))
    session_id = body.get("session_id", f"http_{int(time.time())}")

    if not message:
        return jsonify({"code": 400, "msg": "message is required"}), 400

    def generate():
        try:
            response = _agent.run(
                user_input=message,
                user_id=user_id,
                session_id=session_id,
            )
            # 分 token 发送（按自然段落分割，避免单字碎片）
            for line in response.split("\n"):
                if line.strip():
                    token_text = line + "\n"
                else:
                    token_text = "\n"
                yield f"data: {json.dumps({'type': 'token', 'text': token_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Agent 流式调用异常: {e}")
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)}, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route("/api/images/upload", methods=["POST"])
def image_upload():
    """Upload an order/design image, run OCR, and create a workflow order when possible."""
    file = request.files.get("image")
    session_id = request.form.get("session_id") or f"http_{int(time.time())}"
    if not file or not file.filename:
        return jsonify({"code": 400, "msg": "image is required"}), 400
    if not _allowed_image(file.filename):
        return jsonify({"code": 400, "msg": "只支持 png/jpg/jpeg/webp/bmp 图片"}), 400

    from src.core.session import SessionManager
    from src.core.tools.caller import get_tool_caller
    from src.core.nodes.image_workflow import process_single_image

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_name = secure_filename(file.filename) or "upload.jpg"
    suffix = Path(original_name).suffix.lower() or ".jpg"
    save_name = f"{int(time.time())}_{uuid.uuid4().hex[:10]}{suffix}"
    save_path = UPLOAD_DIR / save_name
    file.save(save_path)

    try:
        caller = get_tool_caller()
        result = process_single_image(str(save_path), caller)
        result["preview_url"] = f"/api/images/file/{save_name}"
        response_text = _format_image_result(result)

        session = SessionManager(session_id)
        session.clear_pending()
        response_text = _handle_image_sales_flow(result, session, response_text)
        session.set_meta("last_extraction", {
            "user_input": f"上传图片：{file.filename}",
            "intent": "workflow",
            "params": {
                "action": "image_upload",
                "image_path": str(save_path),
            },
        })
        session.save_turn(f"上传图片：{file.filename}", response_text)

        return jsonify({
            "code": 0,
            "data": {
                "response": response_text,
                "session_id": session_id,
                "session": _session_snapshot(session_id),
                "image_path": str(save_path),
                "result": _safe_json(result),
            }
        })
    except Exception as e:
        logger.error(f"图片上传识别异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/agent/history", methods=["GET"])
def history():
    """
    获取对话历史
    GET /api/agent/history?session_id=xxx
    """
    session_id = request.args.get("session_id", "")
    if not session_id:
        return jsonify({"code": 400, "msg": "session_id is required"}), 400

    try:
        from src.core.session import SessionManager
        session = SessionManager(session_id)
        hist = session.get_history()
        return jsonify({
            "code": 0,
            "data": {
                "session_id": session_id,
                "history": hist,
                "session": _session_snapshot(session_id),
            }
        })
    except Exception as e:
        logger.error(f"获取历史失败: {e}")
        return jsonify({
            "code": 0,
            "data": {
                "session_id": session_id,
                "history": [],
            }
        })


@app.route("/api/orders/recent", methods=["GET"])
def recent_orders():
    """
    Recent sales and workflow orders for the WebUI side panel.
    GET /api/orders/recent?limit=6
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    limit = request.args.get("limit", 6, type=int)
    limit = max(1, min(limit, 20))

    sales = []
    workflows = []
    try:
        sales_result = caller.call("sales_list", page=1, page_size=limit)
        sales = _enrich_sales_rows(caller, _extract_list_rows(sales_result)[:limit])
    except Exception as e:
        logger.warning(f"最近销售单查询失败: {e}")

    try:
        workflow_result = caller.call("workflow_order_list", page=1, page_size=limit)
        workflows = _extract_list_rows(workflow_result)[:limit]
    except Exception as e:
        logger.warning(f"最近工作流订单查询失败: {e}")

    return jsonify({
        "code": 0,
        "data": {
            "sales": sales,
            "workflows": workflows,
        }
    })


@app.route("/api/sales/cards", methods=["GET"])
def sales_cards():
    """
    Sales cards for the UniApp mini-program.
    GET /api/sales/cards?page=1&page_size=10&keyword=xxx&status=5
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 10, type=int)
    keyword = (request.args.get("keyword", "") or "").strip()
    status_arg = request.args.get("status", "")
    page = max(1, page)
    page_size = max(1, min(page_size, 20))
    status = int(status_arg) if status_arg not in ("", None) else None

    try:
        fetch_size = min(50, max(page_size, 30 if keyword else page_size))
        result = caller.call(
            "sales_list",
            keyword=keyword if keyword and keyword.upper().startswith("S") else None,
            status=status,
            page=page,
            page_size=fetch_size,
        )
        rows = _extract_list_rows(result)
        customer_cache = {}
        cards = [_sales_card(caller, row, customer_cache) for row in rows]
        if keyword:
            lower = keyword.lower()
            cards = [
                card for card in cards
                if lower in str(card.get("sales_no", "")).lower()
                or lower in str(card.get("customer_name", "")).lower()
                or lower in str(card.get("product_summary", "")).lower()
                or any(lower in str(p.get("title", "") + " " + p.get("spec", "")).lower() for p in card.get("products", []))
            ]
        result_data = result.get("data", {}) if isinstance(result, dict) else {}
        if not isinstance(result_data, dict):
            result_data = {}
        return jsonify({
            "code": 0,
            "data": {
                "page": page,
                "page_size": page_size,
                "list": cards[:page_size],
                "total": result_data.get("total", len(cards)),
            }
        })
    except Exception as e:
        logger.error(f"销售单卡片查询失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/sales/<int:sales_id>/print-task", methods=["POST"])
def sales_print_task_api(sales_id: int):
    """Create a print task for a sales order without going through chat."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    if sales_id <= 0:
        return jsonify({"code": 400, "msg": "sales_id is required"}), 400
    try:
        result = caller.call("sales_print_task", sales_id=sales_id)
        if isinstance(result, dict) and result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error")}), 500
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"sales print task failed: sales_id={sales_id}, error={e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/cards", methods=["GET"])
def inventory_cards():
    """
    Inventory cards for the UniApp mini-program.
    GET /api/inventory/cards?keyword=岩味&only_in_stock=1&limit=30
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    keyword = (request.args.get("keyword", "") or "").strip()
    only_in_stock = request.args.get("only_in_stock", "1") not in ("0", "false", "False")
    limit = request.args.get("limit", 30, type=int)
    limit = max(1, min(limit, 80))
    try:
        rows = caller.call(
            "inventory_search",
            keyword=keyword,
            only_in_stock=only_in_stock,
            limit=max(limit * 30, 600),
        )
        cards = _inventory_cards(rows if isinstance(rows, list) else [], limit)
        return jsonify({
            "code": 0,
            "data": {
                "list": cards,
            }
        })
    except Exception as e:
        logger.error(f"库存卡片查询失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/product/color-options", methods=["GET"])
def product_color_options():
    """Return all color/spec options for the same gift-box product series."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    title = (request.args.get("title", "") or "").strip()
    if not title:
        return jsonify({"code": 400, "msg": "title is required"}), 400
    try:
        card = {"title": title, "colors": []}
        product_rows = _load_product_color_options(caller, card)
        _merge_product_color_options(card, product_rows)
        return jsonify({
            "code": 0,
            "data": {
                "title": title,
                "series": _product_series_keyword(title),
                "colors": card.get("colors", []),
            }
        })
    except Exception as e:
        logger.error(f"商品颜色选项查询失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/transfer", methods=["POST"])
def inventory_transfer_api():
    """Transfer inventory between warehouses for the UniApp inventory page."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    body = request.get_json() or {}
    product_id = body.get("product_id")
    quantity = body.get("quantity")
    color = (body.get("color") or "").strip()
    out_warehouse_id = int(body.get("out_warehouse_id") or body.get("from_warehouse_id") or 2)
    enter_warehouse_id = int(body.get("enter_warehouse_id") or body.get("to_warehouse_id") or 1)
    if not product_id:
        return jsonify({"code": 400, "msg": "product_id is required"}), 400
    try:
        quantity = int(quantity or 0)
    except (TypeError, ValueError):
        quantity = 0
    if quantity <= 0:
        return jsonify({"code": 400, "msg": "quantity must be greater than 0"}), 400
    try:
        result = caller.call(
            "inventory_transfer",
            out_warehouse_id=out_warehouse_id,
            enter_warehouse_id=enter_warehouse_id,
            products=[{
                "product_id": int(product_id),
                "unit_id": int(body.get("unit_id") or 1),
                "transfer_number": quantity,
            }],
            note=(body.get("note") or f"小程序调货{f'（{color}）' if color else ''}").strip(),
        )
        if isinstance(result, dict) and result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error")}), 500
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"库存调货失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/purchase", methods=["POST"])
def inventory_purchase_api():
    """Create an inventory inbound record for the UniApp inventory page."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    body = request.get_json() or {}
    product_id = body.get("product_id")
    quantity = body.get("quantity")
    color = (body.get("color") or "").strip()
    warehouse_id = int(body.get("warehouse_id") or 2)
    if not product_id:
        return jsonify({"code": 400, "msg": "product_id is required"}), 400
    try:
        quantity = int(quantity or 0)
    except (TypeError, ValueError):
        quantity = 0
    if quantity <= 0:
        return jsonify({"code": 400, "msg": "quantity must be greater than 0"}), 400
    try:
        result = caller.call(
            "other_enter_add",
            warehouse_id=warehouse_id,
            products=[{
                "product_id": int(product_id),
                "unit_id": int(body.get("unit_id") or 1),
                "buy_number": quantity,
            }],
            note=(body.get("note") or f"小程序进货{f'（{color}）' if color else ''}").strip(),
        )
        if isinstance(result, dict) and result.get("error"):
            return jsonify({"code": 500, "msg": result.get("error")}), 500
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"库存进货失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/workflow/orders", methods=["GET", "POST"])
def workflow_orders():
    """
    GET  /api/workflow/orders?page=1&page_size=10&keyword=xxx
    POST /api/workflow/orders
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    if request.method == "GET":
        keyword = (request.args.get("keyword", "") or "").strip()
        page = max(1, request.args.get("page", 1, type=int))
        page_size = max(1, min(request.args.get("page_size", 10, type=int), 30))
        try:
            result = caller.call("workflow_order_list", keyword=keyword or None, page=page, page_size=page_size)
            data = result.get("data", {}) if isinstance(result, dict) else {}
            rows = data.get("list") or []
            return jsonify({
                "code": 0,
                "data": {
                    "page": data.get("page", page) if isinstance(data, dict) else page,
                    "page_size": data.get("page_size", page_size) if isinstance(data, dict) else page_size,
                    "total": data.get("total", len(rows)) if isinstance(data, dict) else len(rows),
                    "list": [_workflow_card(row) for row in rows],
                }
            })
        except Exception as e:
            logger.error(f"工作流订单查询失败: {e}")
            return jsonify({"code": 500, "msg": str(e)}), 500

    body = request.get_json() or {}
    customer_name = (body.get("customer_name") or "").strip()
    goods_name = (body.get("goods_name") or "").strip()
    if not customer_name:
        return jsonify({"code": 400, "msg": "customer_name is required"}), 400
    if not goods_name:
        return jsonify({"code": 400, "msg": "goods_name is required"}), 400
    try:
        result = caller.call(
            "workflow_order_save",
            order_id=body.get("id"),
            customer_name=customer_name,
            customer_phone=(body.get("customer_phone") or "").strip(),
            goods_name=goods_name,
            color=(body.get("goods_color") or body.get("color") or "").strip(),
            order_quantity=int(body.get("order_quantity") or 0),
            is_screen_print=int(body.get("is_screen_print") or 0),
            order_type=int(body.get("order_type") or 0),
            order_images=body.get("order_images") or [],
            remark=(body.get("remark") or "").strip(),
        )
        if isinstance(result, dict) and result.get("code", 0) != 0:
            return jsonify({"code": result.get("code", 500), "msg": result.get("msg", "保存失败")}), 400
        return jsonify({"code": 0, "data": result.get("data", result) if isinstance(result, dict) else result})
    except Exception as e:
        logger.error(f"工作流订单保存失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/workflow/orders/<int:order_id>/status", methods=["POST"])
def workflow_order_status(order_id: int):
    """Update workflow order status fields."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    body = request.get_json() or {}
    field = body.get("field")
    value = body.get("value")
    if field not in ("is_made", "is_delivered", "order_type"):
        return jsonify({"code": 400, "msg": "field is invalid"}), 400
    try:
        result = caller.call("workflow_order_status_update", order_id=order_id, field=field, value=int(value or 0))
        if isinstance(result, dict) and result.get("code", 0) != 0:
            return jsonify({"code": result.get("code", 500), "msg": result.get("msg", "操作失败")}), 400
        return jsonify({"code": 0, "data": result.get("data", result) if isinstance(result, dict) else result})
    except Exception as e:
        logger.error(f"工作流订单状态更新失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/workflow/orders/<int:order_id>", methods=["DELETE"])
def workflow_order_delete_api(order_id: int):
    """Delete one workflow order."""
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()
    try:
        result = caller.call("workflow_order_delete", ids=str(order_id))
        if isinstance(result, dict) and result.get("code", 0) != 0:
            return jsonify({"code": result.get("code", 500), "msg": result.get("msg", "删除失败")}), 400
        return jsonify({"code": 0, "data": result.get("data", result) if isinstance(result, dict) else result})
    except Exception as e:
        logger.error(f"工作流订单删除失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/inventory/query", methods=["GET"])
def inventory_query():
    """
    库存查询接口
    GET /api/inventory/query?product_id=123
    GET /api/inventory/query?keyword=喜悦
    GET /api/inventory/query?warehouse_id=2
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    product_id = request.args.get("product_id")
    keyword = request.args.get("keyword")
    warehouse_id = request.args.get("warehouse_id")

    try:
        if product_id:
            results = caller.call("inventory_query_by_id", product_id=int(product_id))
        elif keyword:
            # 先搜索商品，再查库存
            products = caller.call("product_search", keyword=keyword)
            results = []
            for p in products[:5]:
                inv = caller.call("inventory_query_by_id", product_id=p["id"])
                results.extend(inv)
        elif warehouse_id:
            results = caller.call("inventory_query_by_warehouse", warehouse_id=int(warehouse_id))
        else:
            return jsonify({"code": 400, "msg": "product_id/keyword/warehouse_id 至少传一个"}), 400

        return jsonify({"code": 0, "data": results})
    except Exception as e:
        logger.error(f"库存查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/product/search", methods=["GET"])
def product_search():
    """
    商品搜索接口
    GET /api/product/search?keyword=喜悦
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    keyword = request.args.get("keyword", "")
    if not keyword:
        return jsonify({"code": 400, "msg": "keyword is required"}), 400

    try:
        results = caller.call("product_search", keyword=keyword)
        return jsonify({"code": 0, "data": results})
    except Exception as e:
        logger.error(f"商品搜索异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/product/list", methods=["GET"])
def product_list():
    """商品管理列表，直接走 ERP Agent API。"""
    from src.engine.api_client import ERPSystemClient

    try:
        client = ERPSystemClient()
        result = client.product_list(
            keyword=request.args.get("keyword") or None,
            brand_name=request.args.get("brand_name") or None,
            status=request.args.get("status", type=int) if request.args.get("status") not in (None, "") else None,
            category_id=request.args.get("category_id", type=int) or None,
            group=request.args.get("group", default=1, type=int) == 1,
            page=request.args.get("page", default=1, type=int),
            page_size=request.args.get("page_size", default=20, type=int),
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品列表异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/options", methods=["GET"])
def product_options():
    """商品编辑基础数据。"""
    from src.engine.api_client import ERPSystemClient

    try:
        product_id = request.args.get("id", type=int)
        result = ERPSystemClient().product_save_info(product_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品基础数据异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/<int:product_id>", methods=["GET"])
def product_detail_api(product_id: int):
    """商品详情。"""
    from src.engine.api_client import ERPSystemClient

    try:
        result = ERPSystemClient().product_detail(product_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品详情异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/save", methods=["POST"])
def product_save_api():
    """创建/编辑商品。"""
    from src.engine.api_client import ERPSystemClient

    try:
        body = request.get_json(silent=True)
        if body is None:
            body = request.form.to_dict(flat=True)
        result = ERPSystemClient().product_save(body or {})
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品保存异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/delete", methods=["POST"])
def product_delete_api():
    """删除商品。"""
    from src.engine.api_client import ERPSystemClient

    try:
        body = request.get_json(silent=True)
        if body is None:
            body = request.form.to_dict(flat=True)
        ids = (body or {}).get("ids")
        if not ids:
            return jsonify({"code": 400, "msg": "缺少商品ID"}), 400
        result = ERPSystemClient().product_delete(ids)
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品删除异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/upload", methods=["POST"])
def product_upload_api():
    """上传商品图片。"""
    from src.engine.api_client import ERPSystemClient

    try:
        file = request.files.get("image")
        if file is None:
            return jsonify({"code": 400, "msg": "缺少图片文件"}), 400
        filename = secure_filename(file.filename or f"product_{int(time.time())}.jpg")
        content = file.read()
        if not content:
            return jsonify({"code": 400, "msg": "图片文件为空"}), 400
        result = ERPSystemClient().product_upload(filename, content, file.mimetype or "application/octet-stream")
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品图片上传异常: {e}")
        return _api_exception_response(e)


@app.route("/api/product/<int:product_id>/shelves", methods=["POST"])
def product_shelves_api(product_id: int):
    """同步商城商品上下架。"""
    from src.engine.api_client import ERPSystemClient

    try:
        body = request.get_json(silent=True) or request.form.to_dict(flat=True) or {}
        state = int(body.get("state", 0))
        result = ERPSystemClient().product_shelves_update(product_id, state)
        return jsonify(result)
    except Exception as e:
        logger.error(f"商品上下架异常: {e}")
        return _api_exception_response(e)


@app.route("/api/customer/list", methods=["GET"])
def customer_list():
    """
    客户列表接口
    GET /api/customer/list?keyword=xxx
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    keyword = request.args.get("keyword", "")

    try:
        results = caller.call("customer_query", keyword=keyword)
        return jsonify({"code": 0, "data": results})
    except Exception as e:
        logger.error(f"客户列表查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/warehouse/list", methods=["GET"])
def warehouse_list():
    """
    仓库列表接口
    GET /api/warehouse/list
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    try:
        results = caller.call("warehouse_list")
        return jsonify({"code": 0, "data": results})
    except Exception as e:
        logger.error(f"仓库列表查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/customer/price", methods=["GET"])
def customer_price():
    """
    客户历史成交价查询
    GET /api/customer/price?customer_id=1&product_id=123
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    customer_id = request.args.get("customer_id", type=int)
    product_id = request.args.get("product_id", type=int)

    if not customer_id or not product_id:
        return jsonify({"code": 400, "msg": "customer_id and product_id are required"}), 400

    try:
        price = caller.call("sales_history_price", customer_id=customer_id, product_id=product_id)
        return jsonify({"code": 0, "data": {"price": price}})
    except Exception as e:
        logger.error(f"客户价格查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/product/retail-price", methods=["GET"])
def product_retail_price():
    """
    商品零售价查询
    GET /api/product/retail-price?product_id=123
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    product_id = request.args.get("product_id", type=int)
    if not product_id:
        return jsonify({"code": 400, "msg": "product_id is required"}), 400

    try:
        price = caller.call("get_product_price", product_id=product_id)
        return jsonify({"code": 0, "data": {"price": price}})
    except Exception as e:
        logger.error(f"零售价查询异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/sales/add", methods=["POST"])
def sales_add():
    """
    开销售单接口
    POST /api/sales/add
    {
        "customer_id": 1,
        "warehouse_id": 2,
        "products": [
            {"product_id": 123, "unit_id": 1, "buy_number": 10, "price": 28.0}
        ]
    }
    """
    from src.core.tools.caller import get_tool_caller
    caller = get_tool_caller()

    body = request.get_json()
    customer_id = body.get("customer_id")
    warehouse_id = body.get("warehouse_id", 2)
    products = body.get("products", [])

    if not customer_id or not products:
        return jsonify({"code": 400, "msg": "customer_id and products are required"}), 400

    try:
        result = caller.call(
            "sales_add",
            customer_id=customer_id,
            warehouse_id=warehouse_id,
            products=products,
        )
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"开单异常: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/tools/list", methods=["GET"])
def tools_list():
    """
    列出所有可用工具
    GET /api/tools/list
    """
    from src.core.tools import list_all_tools
    tools = list_all_tools()
    return jsonify({"code": 0, "data": tools})


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Login with the existing ShopXO mall account and return its token."""
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    accounts = (body.get("accounts") or body.get("username") or body.get("mobile") or body.get("email") or "").strip()
    password = body.get("pwd") or body.get("password") or ""
    login_type = (body.get("type") or "username").strip()
    if not accounts:
        return jsonify({"code": 400, "msg": "请输入商城账号"}), 400
    if login_type == "username" and not password:
        return jsonify({"code": 400, "msg": "请输入商城密码"}), 400

    payload = {
        "type": login_type,
        "accounts": accounts,
        "pwd": password,
    }
    if body.get("verify"):
        payload["verify"] = body.get("verify")
    try:
        result = _shopxo_post("user", "login", payload, uuid_value=body.get("uuid") or "")
        if int(result.get("code", -1)) != 0:
            return jsonify({"code": 401, "msg": result.get("msg") or "商城登录失败"}), 401
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        token = _nested_token(data) or _nested_token(result)
        if not token:
            user = _shopxo_user_by_account(accounts)
            if not user:
                logger.warning(f"商城登录成功但无法解析 token/user: data_keys={list(data.keys())}")
                return jsonify({"code": 500, "msg": "商城登录成功但未返回 token"}), 500
            token = user.get("token", "")
        else:
            user = _normalize_shopxo_user(data, token)
        if not _shopxo_user_can_access_miniapp(user):
            return jsonify({"code": 403, "msg": "当前账号不是管理员，暂无小程序业务权限"}), 403
        SHOPXO_AUTH_CACHE[token] = (time.time() + SHOPXO_AUTH_CACHE_TTL, user)
        return jsonify({"code": 0, "data": {"token": token, "user": user}})
    except Exception as e:
        logger.error(f"商城登录异常: {e}")
        return jsonify({"code": 500, "msg": f"商城登录异常: {e}"}), 500


@app.route("/api/auth/wechat-quick-login", methods=["POST"])
def auth_wechat_quick_login():
    """Login through ShopXO's mini-program auth flow, avoiding password captcha."""
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    authcode = (body.get("authcode") or body.get("code") or "").strip()
    if not authcode:
        return jsonify({"code": 400, "msg": "缺少微信登录 code"}), 400

    try:
        result = _shopxo_post("user", "appminiuserauth", {"authcode": authcode})
        if int(result.get("code", -1)) != 0:
            return jsonify({"code": 401, "msg": result.get("msg") or "微信快捷登录失败"}), 401

        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        user_data = data.get("user") if isinstance(data.get("user"), dict) else data
        token = _nested_token(data) or _nested_token(result)
        if not token:
            token = f"sj_local_{uuid.uuid4().hex}"

        user = _normalize_shopxo_user(user_data, token)
        if not user.get("id") and isinstance(data, dict):
            user = _normalize_shopxo_user(data, token)
        if not _shopxo_user_can_access_miniapp(user):
            return jsonify({"code": 403, "msg": "当前账号不是管理员，暂无小程序业务权限"}), 403

        SHOPXO_AUTH_CACHE[token] = (time.time() + SHOPXO_AUTH_CACHE_TTL, user)
        return jsonify({"code": 0, "data": {"token": token, "user": user}})
    except Exception as e:
        logger.error(f"微信快捷登录异常: {e}")
        return jsonify({"code": 500, "msg": f"微信快捷登录异常: {e}"}), 500


@app.route("/api/auth/captcha", methods=["GET"])
def auth_captcha():
    """Proxy the ShopXO image captcha so the miniapp can keep using the sjagent API host."""
    uuid_value = (request.args.get("uuid") or "").strip() or f"sjagent_{uuid.uuid4().hex}"
    verify_type = (request.args.get("type") or "user_login").strip()
    try:
        resp = _shopxo_get(
            "user",
            "userverifyentry",
            uuid_value=uuid_value,
            extra_params={
                "type": verify_type,
                "t": request.args.get("t") or str(int(time.time() * 1000)),
            },
        )
        content_type = "image/gif" if resp.content.startswith((b"GIF87a", b"GIF89a")) else resp.headers.get("Content-Type", "image/gif")
        response = Response(resp.content, content_type=content_type)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response
    except Exception as e:
        logger.error(f"商城验证码获取异常: {e}")
        return jsonify({"code": 500, "msg": f"商城验证码获取异常: {e}"}), 500


@app.route("/api/auth/me", methods=["GET", "POST"])
def auth_me():
    """Validate the current ShopXO token and return normalized user info."""
    token = _auth_token_from_request()
    if not token:
        return jsonify({"code": 401, "msg": "缺少登录 token"}), 401
    try:
        user = _verify_shopxo_token(token, force=request.args.get("force") in ("1", "true", "True"))
        if not user:
            return jsonify({"code": 401, "msg": "登录已失效，请重新登录"}), 401
        if not _shopxo_user_can_access_miniapp(user):
            return jsonify({"code": 401, "msg": "当前账号不是管理员，暂无小程序业务权限"}), 401
        return jsonify({"code": 0, "data": {"token": token, "user": user}})
    except Exception as e:
        logger.error(f"商城用户信息校验异常: {e}")
        return jsonify({"code": 500, "msg": f"商城用户信息校验异常: {e}"}), 500


@app.route("/api/asr/aliyun-token", methods=["GET"])
def aliyun_asr_token():
    """Return a short-lived Aliyun NLS token for mini-program ASR."""
    try:
        from src.services.aliyun_asr import create_aliyun_token
        token = create_aliyun_token(force=request.args.get("force") in ("1", "true", "True"))
        return jsonify({
            "code": 0,
            "data": {
                "token": token.get("token"),
                "expire_time": token.get("expire_time"),
                "appkey": token.get("appkey"),
                "vocabulary_id": token.get("vocabulary_id") or "",
            }
        })
    except Exception as e:
        logger.error(f"阿里云 ASR Token 获取失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/asr/hotwords/status", methods=["GET"])
def aliyun_asr_hotwords_status():
    """Return local hotword sync status."""
    try:
        from src.services.aliyun_asr import get_hotword_state
        return jsonify({"code": 0, "data": get_hotword_state()})
    except Exception as e:
        logger.error(f"阿里云 ASR 热词状态获取失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/api/asr/hotwords/sync", methods=["POST"])
def aliyun_asr_hotwords_sync():
    """Manually sync ERP hotwords to Aliyun ASR."""
    try:
        from src.services.aliyun_asr import sync_hotwords
        force = request.args.get("force") in ("1", "true", "True")
        body = request.get_json(silent=True) or {}
        if body.get("force") is not None:
            force = bool(body.get("force"))
        result = sync_hotwords(force=force)
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"阿里云 ASR 热词同步失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({"status": "ok", "agent": "sjagent"})


def run_api_server(host: str = "127.0.0.1", port: int = 8080):
    """启动 HTTP API 服务器"""
    app.run(host=host, port=port, debug=False)
