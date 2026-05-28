"""Smoke-test local Flask routes without starting a real HTTP server."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.check_admin_dist import verify_admin_dist


def _check(name: str, passed: bool, detail: str = "") -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _close_response(response) -> None:
    close = getattr(response, "close", None)
    if callable(close):
        close()


def run_smoke_tests() -> dict:
    from src.channels.http_api import app

    app.config["TESTING"] = True
    checks: list[dict] = []
    with app.test_client() as client:
        response = client.get("/health")
        payload = response.get_json(silent=True) or {}
        checks.append(_check("health", response.status_code == 200 and payload.get("status") == "ok", f"status={response.status_code}"))
        _close_response(response)

        response = client.get("/login")
        login_text = response.get_data(as_text=True)
        checks.append(_check("login", response.status_code == 200 and "北极星" in login_text, f"status={response.status_code}"))
        _close_response(response)

        response = client.get("/web")
        location = response.headers.get("Location", "")
        checks.append(_check(
            "web_requires_login",
            response.status_code in {301, 302} and location.endswith("/login"),
            f"status={response.status_code}, location={location}",
        ))
        _close_response(response)

        response = client.get("/admin")
        checks.append(_check(
            "admin_shell",
            response.status_code == 200 and b'id="root"' in response.data,
            f"status={response.status_code}",
        ))
        _close_response(response)

        dist_result = verify_admin_dist()
        asset_ok = dist_result.get("code") == 0
        for asset in dist_result.get("assets") or []:
            asset_response = client.get(asset)
            try:
                if asset_response.status_code != 200 or len(asset_response.data or b"") <= 0:
                    asset_ok = False
                    break
            finally:
                _close_response(asset_response)
        checks.append(_check("admin_assets", asset_ok, json.dumps(dist_result, ensure_ascii=False)))

        response = client.get("/api/web-auth/me")
        payload = response.get_json(silent=True) or {}
        checks.append(_check(
            "web_auth_me_unauthorized",
            response.status_code == 401 and int(payload.get("code") or 0) == 401,
            f"status={response.status_code}",
        ))
        _close_response(response)

    return {"code": 0 if all(item["passed"] for item in checks) else 1, "checks": checks}


def main() -> int:
    result = run_smoke_tests()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result["code"])


if __name__ == "__main__":
    raise SystemExit(main())
