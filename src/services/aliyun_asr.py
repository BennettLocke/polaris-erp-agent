"""Aliyun Intelligent Speech Interaction helpers.

The agent keeps business hotwords in Alibaba Cloud and stores only the
resulting vocabulary id locally. The source of truth remains the ERP database.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymysql
import yaml
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT_DIR / "data" / "aliyun_asr_hotwords.json"
CONFIG_PATH = ROOT_DIR / "config.yaml"

HOTWORD_NAME = "sjagent_business_hotwords"
HOTWORD_DESCRIPTION = "sjagent auto sync from ERP products, colors, warehouses and customers"
BUSINESS_WORDS = (
    "北极星",
    "开单",
    "销售单",
    "库存",
    "查库存",
    "调货",
    "进货",
    "盘点",
    "订单",
    "工作流订单",
    "制作完成",
    "取消制作",
    "配送完成",
    "取消配送",
    "删除订单",
    "编辑订单",
    "百鑫仓库",
    "店里仓库",
    "自己店里",
    "半斤礼盒",
    "三两礼盒",
    "二两礼盒",
    "一两礼盒",
    "三小盒",
    "六小盒",
)

_token_lock = threading.Lock()
_token_cache: dict[str, Any] = {}
_scheduler_started = False


class AliyunAsrError(RuntimeError):
    """Raised when Aliyun ASR configuration or API calls fail."""


@dataclass
class AliyunAsrConfig:
    ak_id: str
    ak_secret: str
    appkey: str
    region: str = "cn-shanghai"
    token_domain: str = "nls-meta.cn-shanghai.aliyuncs.com"
    slp_domain: str = "nls-slp.cn-shanghai.aliyuncs.com"
    vocab_id: str = ""
    max_words: int = 500


def _load_yaml_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _config_value(config: dict[str, Any], key: str, default: Any = None) -> Any:
    value: Any = config
    for part in key.split("."):
        if not isinstance(value, dict):
            return default
        value = value.get(part)
        if value is None:
            return default
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return os.environ.get(value[2:-1], default)
    return value


def get_aliyun_asr_config() -> AliyunAsrConfig:
    load_dotenv(ROOT_DIR / ".env")
    config = _load_yaml_config()
    aliyun = config.get("aliyun_asr", {}) if isinstance(config.get("aliyun_asr"), dict) else {}

    ak_id = os.getenv("ALIYUN_AK_ID") or _config_value(config, "aliyun_asr.access_key_id", "")
    ak_secret = os.getenv("ALIYUN_AK_SECRET") or _config_value(config, "aliyun_asr.access_key_secret", "")
    appkey = (
        os.getenv("ALIYUN_NLS_APPKEY")
        or os.getenv("ALIYUN_NLS_ACCESS_TOKEN")
        or _config_value(config, "aliyun_asr.appkey", "")
    )
    if not ak_id or not ak_secret:
        raise AliyunAsrError("缺少 ALIYUN_AK_ID / ALIYUN_AK_SECRET")
    if not appkey:
        raise AliyunAsrError("缺少 ALIYUN_NLS_APPKEY")

    return AliyunAsrConfig(
        ak_id=ak_id,
        ak_secret=ak_secret,
        appkey=appkey,
        region=str(aliyun.get("region") or "cn-shanghai"),
        token_domain=str(aliyun.get("token_domain") or "nls-meta.cn-shanghai.aliyuncs.com"),
        slp_domain=str(aliyun.get("slp_domain") or "nls-slp.cn-shanghai.aliyuncs.com"),
        vocab_id=str(os.getenv("ALIYUN_NLS_VOCAB_ID") or _config_value(config, "aliyun_asr.vocab_id", "") or ""),
        max_words=int(os.getenv("ALIYUN_ASR_MAX_HOTWORDS") or aliyun.get("max_words") or 500),
    )


def _aliyun_request(cfg: AliyunAsrConfig, domain: str, version: str, action: str, body: dict[str, Any] | None = None) -> dict:
    client = AcsClient(cfg.ak_id, cfg.ak_secret, cfg.region)
    request = CommonRequest()
    request.set_method("POST")
    request.set_domain(domain)
    request.set_version(version)
    request.set_action_name(action)
    for key, value in (body or {}).items():
        request.add_body_params(key, value)
    response = client.do_action_with_exception(request)
    return json.loads(response)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def create_aliyun_token(force: bool = False) -> dict[str, Any]:
    """Return a cached NLS token plus appkey and vocabulary id."""
    global _token_cache
    cfg = get_aliyun_asr_config()
    now = int(time.time())
    with _token_lock:
        cached = dict(_token_cache)
        if not force and cached.get("token") and int(cached.get("expire_time") or 0) - now > 600:
            cached["appkey"] = cfg.appkey
            cached["vocabulary_id"] = get_hotword_state().get("vocab_id") or cfg.vocab_id
            return cached

        data = _aliyun_request(cfg, cfg.token_domain, "2019-02-28", "CreateToken")
        token = data.get("Token") or {}
        result = {
            "token": token.get("Id") or "",
            "expire_time": int(token.get("ExpireTime") or 0),
            "appkey": cfg.appkey,
            "vocabulary_id": get_hotword_state().get("vocab_id") or cfg.vocab_id,
        }
        if not result["token"]:
            raise AliyunAsrError("阿里云 CreateToken 未返回 Token")
        _token_cache = dict(result)
        return result


def _db_config() -> dict[str, Any]:
    config = _load_yaml_config()
    return {
        "host": _config_value(config, "database.host"),
        "port": int(_config_value(config, "database.port", 3306)),
        "user": _config_value(config, "database.user"),
        "password": _config_value(config, "database.password"),
        "database": _config_value(config, "database.name"),
        "charset": _config_value(config, "database.charset", "utf8mb4"),
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": True,
    }


def _fetch_rows(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    load_dotenv(ROOT_DIR / ".env")
    conn = pymysql.connect(**_db_config())
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())
    finally:
        conn.close()


def _clean_word(text: Any) -> str:
    word = str(text or "").strip()
    if not word:
        return ""
    word = word.replace("【", "").replace("】", "")
    word = word.replace("3两", "三两").replace("2两", "二两").replace("1两", "一两")
    word = word.replace("3小盒", "三小盒").replace("6小盒", "六小盒")
    word = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]+", "", word)
    word = re.sub(r"^(?:SJ)?\d{2,}", "", word, flags=re.IGNORECASE)
    return word[:15]


def _add(words: dict[str, int], text: Any, weight: int) -> None:
    word = _clean_word(text)
    if not word or len(word) < 2:
        return
    if len(word) > 15:
        return
    words[word] = max(words.get(word, -6), max(-6, min(5, int(weight))))


def collect_hotwords(max_words: int = 500) -> tuple[dict[str, int], dict[str, int]]:
    """Collect and normalize hotwords from ERP tables and static business terms."""
    words: dict[str, int] = {}
    source_counts = {"business": 0, "products": 0, "recent_sales": 0, "colors": 0, "warehouses": 0, "customers": 0}

    for word in BUSINESS_WORDS:
        before = len(words)
        _add(words, word, 4)
        source_counts["business"] += len(words) - before

    config = _load_yaml_config()
    for color in _config_value(config, "business_rules.color_filter.standard_colors", []) or []:
        before = len(words)
        _add(words, color, 4)
        source_counts["colors"] += len(words) - before
    for alias, target in (_config_value(config, "business_rules.color_filter.aliases", {}) or {}).items():
        before = len(words)
        _add(words, alias, 3)
        _add(words, target, 4)
        source_counts["colors"] += len(words) - before

    recent_sales_rows = _fetch_rows(
        """
        SELECT title, spec
        FROM sxo_plugins_erp_sales_detail
        WHERE title IS NOT NULL AND title <> ''
        ORDER BY upd_time DESC, id DESC
        LIMIT 300
        """
    )
    for row in recent_sales_rows:
        before = len(words)
        _add(words, row.get("title"), 5)
        _add(words, row.get("spec"), 4)
        source_counts["recent_sales"] += max(0, len(words) - before)

    product_rows = _fetch_rows(
        """
        SELECT title, spec, simple_desc
        FROM sxo_plugins_erp_product
        WHERE title IS NOT NULL AND title <> ''
        ORDER BY upd_time DESC, id DESC
        LIMIT 2000
        """
    )
    for row in product_rows:
        before = len(words)
        title = row.get("title") or ""
        spec = row.get("spec") or ""
        simple_desc = row.get("simple_desc") or ""
        _add(words, title, 5)
        clean_title = _clean_word(title)
        if clean_title:
            for suffix in ("半斤", "三两", "二两", "一两", "三小盒", "六小盒"):
                if suffix in clean_title:
                    _add(words, suffix if "礼盒" in suffix else f"{suffix}礼盒", 4)
        if spec:
            _add(words, spec, 4)
        if simple_desc:
            for part in re.split(r"[,，;；/\\s]+", str(simple_desc)):
                _add(words, part, 2)
        source_counts["products"] += max(0, len(words) - before)

    for row in _fetch_rows("SELECT name, alias FROM sxo_plugins_erp_warehouse WHERE is_enable = 1"):
        before = len(words)
        _add(words, row.get("name"), 4)
        _add(words, row.get("alias"), 3)
        source_counts["warehouses"] += len(words) - before

    customer_rows = _fetch_rows(
        """
        SELECT name, company_name, contacts_name
        FROM sxo_plugins_erp_company
        WHERE is_enable = 1 AND is_customer = 1
        ORDER BY upd_time DESC, id DESC
        LIMIT 800
        """
    )
    for row in customer_rows:
        before = len(words)
        _add(words, row.get("name"), 3)
        _add(words, row.get("company_name"), 3)
        _add(words, row.get("contacts_name"), 2)
        source_counts["customers"] += len(words) - before

    # Keep high-weight words first, and preserve insertion order for ties.
    # Product rows are inserted by newest update first, so recent products stay
    # inside the 500-word Aliyun limit instead of being pushed out alphabetically.
    sorted_words = sorted(words.items(), key=lambda item: -item[1])
    limited = dict(sorted_words[:max(1, min(max_words, 500))])
    return limited, source_counts


def get_hotword_state() -> dict[str, Any]:
    state = _read_json(STATE_PATH)
    cfg_vocab_id = ""
    try:
        cfg_vocab_id = get_aliyun_asr_config().vocab_id
    except Exception:
        cfg_vocab_id = ""
    if cfg_vocab_id and not state.get("vocab_id"):
        state["vocab_id"] = cfg_vocab_id
    return state


def sync_hotwords(force: bool = False) -> dict[str, Any]:
    """Create or update Aliyun ASR hotword vocabulary from current ERP data."""
    cfg = get_aliyun_asr_config()
    words, source_counts = collect_hotwords(cfg.max_words)
    payload = json.dumps(words, ensure_ascii=False, separators=(",", ":"))
    payload_md5 = hashlib.md5(payload.encode("utf-8")).hexdigest()
    state = get_hotword_state()
    vocab_id = state.get("vocab_id") or cfg.vocab_id

    if not force and vocab_id and state.get("md5") == payload_md5:
        return {
            "changed": False,
            "vocab_id": vocab_id,
            "word_count": len(words),
            "source_counts": source_counts,
            "synced_at": state.get("synced_at"),
        }

    body = {
        "Name": HOTWORD_NAME,
        "Description": HOTWORD_DESCRIPTION,
        "WordWeights": payload,
    }
    if vocab_id:
        body["Id"] = vocab_id
        action = "UpdateAsrVocab"
    else:
        action = "CreateAsrVocab"

    result = _aliyun_request(cfg, cfg.slp_domain, "2018-11-20", action, body)
    if action == "CreateAsrVocab":
        vocab_id = result.get("VocabId")
        if not vocab_id:
            raise AliyunAsrError("阿里云 CreateAsrVocab 未返回 VocabId")

    new_state = {
        "vocab_id": vocab_id,
        "md5": payload_md5,
        "word_count": len(words),
        "source_counts": source_counts,
        "synced_at": int(time.time()),
        "synced_at_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "last_action": action,
        "request_id": result.get("RequestId"),
        "sample_words": list(words.keys())[:30],
    }
    _write_json(STATE_PATH, new_state)
    return {"changed": True, **new_state}


def _seconds_until_next_daily_sync(sync_hour: int = 12) -> int:
    now = time.time()
    local = time.localtime(now)
    hour = max(0, min(23, int(sync_hour)))
    target = time.mktime((
        local.tm_year,
        local.tm_mon,
        local.tm_mday,
        hour,
        0,
        0,
        local.tm_wday,
        local.tm_yday,
        local.tm_isdst,
    ))
    if target <= now:
        target += 86400
    return max(60, int(target - now))


def start_hotword_scheduler(
    interval_seconds: int = 86400,
    initial_delay_seconds: int = 60,
    daily_sync_hour: int = 12,
) -> bool:
    """Start one background hotword sync loop.

    The service checks once shortly after startup, then checks again every day
    at local noon. sync_hotwords(force=False) skips the Aliyun update when the
    selected 500 words did not change.
    """
    global _scheduler_started
    if _scheduler_started:
        return False
    _scheduler_started = True

    def loop() -> None:
        time.sleep(max(0, initial_delay_seconds))
        while True:
            try:
                sync_hotwords(force=False)
            except Exception as exc:
                print(f"[aliyun_asr] hotword sync failed: {exc}")
            if daily_sync_hour is None:
                time.sleep(max(60, interval_seconds))
            else:
                time.sleep(_seconds_until_next_daily_sync(daily_sync_hour))

    thread = threading.Thread(target=loop, name="aliyun-asr-hotword-sync", daemon=True)
    thread.start()
    return True
