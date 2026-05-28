"""Check that React admin_dist points to existing built assets."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ADMIN_PREFIX = "/admin/"
ASSET_PREFIX = "/admin/assets/"


def extract_admin_asset_paths(html: str) -> list[str]:
    paths: list[str] = []
    for match in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html, flags=re.IGNORECASE):
        value = match.group(1).strip()
        if value.startswith(ASSET_PREFIX) and value not in paths:
            paths.append(value)
    return paths


def _asset_path(admin_dist: Path, public_path: str) -> Path:
    relative = public_path.removeprefix(ADMIN_PREFIX).strip("/")
    return admin_dist.joinpath(*relative.split("/"))


def verify_admin_dist(root: str | Path | None = None) -> dict:
    project_root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    admin_dist = project_root / "src" / "channels" / "http_api" / "admin_dist"
    index_path = admin_dist / "index.html"
    result = {
        "code": 0,
        "admin_dist": str(admin_dist),
        "index": str(index_path),
        "assets": [],
        "missing": [],
        "empty": [],
    }
    if not index_path.exists():
        result["code"] = 1
        result["missing"].append(str(index_path))
        return result

    html = index_path.read_text(encoding="utf-8")
    assets = extract_admin_asset_paths(html)
    result["assets"] = assets
    if not assets:
        result["code"] = 1
        result["missing"].append("no /admin/assets references found in index.html")
        return result

    for public_path in assets:
        path = _asset_path(admin_dist, public_path)
        if not path.exists():
            result["missing"].append(public_path)
            continue
        if path.stat().st_size <= 0:
            result["empty"].append(public_path)

    if result["missing"] or result["empty"]:
        result["code"] = 1
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify admin_dist index.html references existing assets.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="Project root path")
    args = parser.parse_args(argv)
    result = verify_admin_dist(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result["code"])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
