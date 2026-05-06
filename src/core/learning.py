"""Runtime learning memory for intent examples and user corrections."""
import json
import re
from datetime import datetime
from pathlib import Path
from src.utils import get_logger

logger = get_logger("sjagent.learning")

LEARNING_FILE = Path(__file__).parent.parent.parent / "data" / "learning_rules.json"

INTENT_ALIASES = {
    "下单": "order",
    "开单": "order",
    "订货": "order",
    "查库存": "inventory",
    "库存": "inventory",
    "有货": "inventory",
    "盘点": "stocktaking",
    "进货": "purchase",
    "入库": "purchase",
    "采购": "purchase",
    "调货": "transfer",
    "调拨": "transfer",
    "查订单": "sales_query",
    "查销售单": "sales_query",
    "订单查询": "sales_query",
    "删除订单": "sales_manage",
    "删单": "sales_manage",
    "工作流": "workflow",
    "工作流订单": "workflow",
    "设计稿订单": "workflow",
    "聊天": "chat",
    "闲聊": "chat",
}


def normalize_text(text: str) -> str:
    """Normalize text for exact example lookup."""
    return re.sub(r"[\s，,。！？?！：:；;、]+", "", str(text or "")).lower()


def _load() -> dict:
    if not LEARNING_FILE.exists():
        return {"examples": []}
    try:
        with open(LEARNING_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("examples", [])
            return data
    except Exception as e:
        logger.warning(f"读取学习记忆失败: {e}")
    return {"examples": []}


def _save(data: dict):
    LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LEARNING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def compact_extraction(extracted: dict) -> dict:
    """Keep only stable fields that are safe to reuse as an example."""
    if not extracted:
        return {}
    allowed = {
        "intent", "action", "customer", "keyword", "product_name", "color",
        "sales_id", "count", "from", "to", "warehouse", "goods_name",
        "quantity", "qty", "unit", "target",
    }
    compact = {k: v for k, v in extracted.items() if k in allowed and v not in (None, "", [])}
    if extracted.get("products"):
        compact["products"] = extracted["products"]
    return compact


def record_example(text: str, extracted: dict, source: str = "llm") -> bool:
    """Record a phrase and its extracted intent/parameters."""
    if source == "llm" and _is_context_dependent(text):
        return False

    compact = compact_extraction(extracted)
    intent = compact.get("intent")
    if not text or not intent or intent in {"chat", "help", "knowledge", "unknown"}:
        return False
    key = normalize_text(text)
    if len(key) < 3:
        return False

    data = _load()
    now = datetime.now().isoformat(timespec="seconds")
    for example in data["examples"]:
        if example.get("key") == key:
            example["text"] = text
            example["extracted"] = compact
            example["source"] = source
            example["count"] = int(example.get("count", 0)) + 1
            example["updated_at"] = now
            _save(data)
            return True

    data["examples"].append({
        "key": key,
        "text": text,
        "extracted": compact,
        "source": source,
        "count": 1,
        "created_at": now,
        "updated_at": now,
    })
    data["examples"] = data["examples"][-200:]
    _save(data)
    return True


def _is_context_dependent(text: str) -> bool:
    """Avoid saving phrases that only make sense with prior context."""
    normalized = normalize_text(text)
    context_words = ("再", "回去", "他的", "它的", "这个", "那个", "这单", "刚才", "上一单", "最近几单", "最近3单", "呢")
    if any(word in normalized for word in context_words) and len(normalized) <= 12:
        return True
    return normalized in {"再调货回去", "调回去", "再来一次", "一样的", "同上"}


def match_learned(text: str) -> dict | None:
    """Exact lookup for corrected/learned phrases."""
    key = normalize_text(text)
    if not key:
        return None
    data = _load()
    for example in reversed(data.get("examples", [])):
        if example.get("key") == key:
            extracted = example.get("extracted") or {}
            if extracted.get("intent"):
                logger.info(f"命中学习记忆: {text[:50]} -> {extracted.get('intent')}")
                return dict(extracted)
    return None


def get_prompt_examples(limit: int = 12) -> str:
    """Return learned examples to append to the LLM prompt."""
    examples = _load().get("examples", [])
    examples = sorted(
        examples,
        key=lambda x: (x.get("source") == "correction", int(x.get("count", 0)), x.get("updated_at", "")),
        reverse=True,
    )[:limit]
    if not examples:
        return ""
    lines = ["\n已学习的本店说法示例（优先参考，但仍要结合当前上下文）："]
    for ex in examples:
        extracted = ex.get("extracted", {})
        lines.append(f"- 用户说：{ex.get('text')} => {json.dumps(extracted, ensure_ascii=False)}")
    return "\n".join(lines)


def parse_correction(text: str) -> str | None:
    """Parse a correction such as '不是查库存，是调货' into an intent."""
    text = str(text or "").strip()
    patterns = [
        r"(?:不是|不对|错了|理解错了|应该是|这是|这个是|这句是).{0,12}(下单|开单|订货|查库存|库存|有货|盘点|进货|入库|采购|调货|调拨|查订单|查销售单|订单查询|删除订单|删单|工作流订单|工作流|设计稿订单)",
        r"(?:记住|以后).{0,12}(下单|开单|订货|查库存|库存|有货|盘点|进货|入库|采购|调货|调拨|查订单|查销售单|订单查询|删除订单|删单|工作流订单|工作流|设计稿订单)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return INTENT_ALIASES.get(m.group(1))
    return None
