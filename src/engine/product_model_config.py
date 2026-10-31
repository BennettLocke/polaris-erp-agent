"""The version-one product binding config; names always come from live SKUs."""
from __future__ import annotations

import math
import re


FIELDS = {"version", "asset_id", "material_index", "sku_colors", "default_sku_key",
          "camera_direction", "default_pose"}


def project_config(config: dict | None, sku_ids: list[str]) -> dict | None:
    if config is None:
        return None
    colors = config.get("sku_colors") or {}
    colors = {key: colors[key].upper() for key in sku_ids
              if isinstance(colors.get(key), str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", colors[key])}
    default = config.get("default_sku_key")
    return {key: config.get(key) for key in FIELDS} | {
        "sku_colors": colors,
        "default_sku_key": default if default in colors else next(iter(colors), None),
    }


def validate_config(config: dict, asset: dict, sku_keys: dict[str, str]) -> dict:
    if not isinstance(config, dict) or set(config) != FIELDS:
        raise ValueError("model_config must contain exactly the version 1 fields")
    if type(config["version"]) is not int or config["version"] != 1:
        raise ValueError("model_config.version must be 1")
    if type(config["asset_id"]) is not int or config["asset_id"] != asset["id"]:
        raise ValueError("model_config.asset_id must match the bound asset")
    index = config["material_index"]
    indices = {item["index"] for item in asset["materials"]
               if isinstance(item, dict) and type(item.get("index")) is int}
    if index is not None and (type(index) is not int or index < 0 or index not in indices):
        raise ValueError("model_config.material_index must be an original asset material index")
    colors = config["sku_colors"]
    if not isinstance(colors, dict):
        raise ValueError("model_config.sku_colors must be an object")
    mapped = {}
    for key, color in colors.items():
        if not isinstance(key, str) or key not in sku_keys:
            raise ValueError("model_config SKU keys must reference saved base keys")
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise ValueError("model_config colors must be #RRGGBB")
        mapped[sku_keys[key]] = color.upper()
    default = config["default_sku_key"]
    if default is not None and (not isinstance(default, str) or default not in sku_keys):
        raise ValueError("model_config.default_sku_key must reference a saved base key")
    vector = config["camera_direction"]
    if vector is not None:
        try:
            valid = (isinstance(vector, list) and len(vector) == 3
                     and all(type(v) in (int, float) and math.isfinite(v) for v in vector))
        except OverflowError:
            valid = False
        if not valid or not any(vector):
            raise ValueError("model_config.camera_direction must be a finite nonzero 3-vector")
        scale = max(abs(v) for v in vector)
        vector = [v / scale for v in vector]
        length = math.hypot(*vector)
        vector = [v / length for v in vector]
    if config["default_pose"] != "open":
        raise ValueError("model_config.default_pose must be open")
    return {**config, "sku_colors": mapped, "default_sku_key": sku_keys.get(default),
            "camera_direction": vector}
