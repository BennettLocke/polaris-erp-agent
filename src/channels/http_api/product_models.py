"""Authenticated product GLB upload, isolated from image processing."""
from pathlib import Path
import tempfile

from flask import jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from src.services.business.products import get_product_service


def register_product_model_routes(app):
    from src.channels import http_api

    def actor_or_error():
        user = http_api._current_web_user()
        if not isinstance(user, dict) or not user.get("id"):
            return None, (jsonify({"code": 401, "msg": "请先登录北极星"}), 401)
        for permission in ("设置", "图片上传"):
            if not http_api._has_permission(permission):
                return None, http_api._permission_denied(permission)
        return user.get("native_user_id") or user["id"], None

    @app.route("/api/product/models/upload", methods=["POST"])
    def product_model_upload_api():
        actor, error = actor_or_error()
        if error:
            return error
        file = request.files.get("model")
        if file is None:
            return jsonify({"code": 400, "msg": "请选择 GLB 模型文件"}), 400
        filename = str(file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not filename.lower().endswith(".glb"):
            return jsonify({"code": 400, "msg": "只支持贴图内嵌的 GLB 模型"}), 400
        from src.services.business.product_models import validate_model_file, upload_model_file, cleanup_model_object, normalize_model_filename

        http_api.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        uploaded_key = None
        registered_asset = None
        try:
            filename = normalize_model_filename(filename)
            with tempfile.TemporaryDirectory(prefix="product_model_", dir=http_api.UPLOAD_DIR) as folder:
                path = Path(folder) / "model.glb"
                size = 0
                with path.open("wb") as target:
                    while chunk := file.stream.read(1024 * 256):
                        size += len(chunk)
                        if size > http_api.MAX_MODEL_UPLOAD_BYTES:
                            raise RequestEntityTooLarge()
                        target.write(chunk)
                metadata = validate_model_file(path, max_bytes=http_api.MAX_MODEL_UPLOAD_BYTES)
                result = upload_model_file(path, filename)
                if not isinstance(result, dict) or result.get("error") or not result.get("url") or not result.get("path"):
                    raise RuntimeError("模型 OSS 上传未返回完整结果")
                uploaded_key = result["path"]
                metadata.update({"url": result["url"], "oss_key": uploaded_key, "file_name": filename[:255]})
                asset = get_product_service().record_model_asset(metadata, operator_user_id=actor)
                if not isinstance(asset, dict) or not asset.get("id"):
                    raise RuntimeError("模型资产未成功保存")
                registered_asset = asset
            return jsonify({"code": 0, "data": http_api._safe_json(registered_asset)})
        except RequestEntityTooLarge:
            raise
        except Exception as exc:
            # A local temporary-file cleanup failure must not compensate a committed asset.
            if registered_asset is not None:
                http_api.logger.warning("模型资料已保存，本地临时文件清理未完成")
                return jsonify({"code": 0, "data": http_api._safe_json(registered_asset)})
            if uploaded_key:
                try:
                    if not cleanup_model_object(uploaded_key):
                        http_api.logger.warning("模型上传失败后的 OSS 对象回收未完成")
                except Exception:
                    http_api.logger.warning("模型上传失败后的 OSS 对象回收异常")
            if isinstance(exc, ValueError):
                return jsonify({"code": 400, "msg": str(exc)}), 400
            http_api.logger.exception("商品模型上传失败")
            return jsonify({"code": 500, "msg": "模型上传或保存失败，请稍后重试"}), 500

    @app.route("/api/product/models/<int:asset_id>/pending", methods=["DELETE"])
    def product_model_pending_delete_api(asset_id):
        actor, error = actor_or_error()
        if error:
            return error
        try:
            asset = get_product_service().delete_pending_model_asset(asset_id, operator_user_id=actor)
            from src.services.business.product_models import cleanup_model_object

            deleted = False
            if asset.get("oss_key"):
                try:
                    deleted = cleanup_model_object(asset["oss_key"])
                except Exception:
                    http_api.logger.warning("未绑定商品模型的 OSS 对象清理异常")
            if not deleted:
                http_api.logger.warning(f"未绑定商品模型的 OSS 对象清理未完成，asset_id={asset_id}")
            return jsonify({"code": 0, "data": {"id": asset_id, "storage_deleted": deleted}})
        except ValueError as exc:
            return jsonify({"code": 400, "msg": str(exc)}), 400
        except Exception:
            http_api.logger.exception("未绑定商品模型清理失败")
            return jsonify({"code": 500, "msg": "模型清理失败"}), 500
