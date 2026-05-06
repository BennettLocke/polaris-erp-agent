"""
OSS 上传模块
上传图片到阿里云 OSS，返回公开访问 URL
"""
import os
import uuid
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

try:
    import oss2
except ImportError:
    oss2 = None


class OSSUploader:
    """
    阿里云 OSS 上传器
    配置从 config.yaml 读取
    """

    def __init__(self, config: dict):
        """
        Args:
            config: OSS配置字典
                {
                    "access_key_id": "...",
                    "access_key_secret": "...",
                    "bucket": "...",
                    "endpoint": "...",
                    "domain": "...",
                    "upload_path": "order/{date}/{uniqid}.jpg"
                }
        """
        self.config = config
        self._bucket = None

        if oss2 is None:
            raise ImportError("oss2 库未安装，请 pip install oss2")

    def _get_bucket(self):
        """获取或创建 Bucket 连接（懒加载）"""
        if self._bucket is None:
            auth = oss2.Auth(
                self.config["access_key_id"],
                self.config.get("access_key_secret", ""),
            )
            self._bucket = oss2.Bucket(auth, self.config["endpoint"], self.config["bucket"])
        return self._bucket

    def upload(self, local_path: str) -> dict:
        """
        上传本地文件到 OSS

        Args:
            local_path: 本地文件路径

        Returns:
            {"url": "https://...", "path": "order/xxx.jpg"} 或 {"error": "..."}
        """
        if not os.path.exists(local_path):
            return {"error": f"文件不存在: {local_path}"}

        try:
            bucket = self._get_bucket()

            # 生成远程路径
            remote_path = self._generate_path(local_path)

            # 上传
            result = bucket.put_object_from_file(remote_path, local_path)

            if result.status == 200:
                url = f"{self.config['domain']}/{remote_path}"
                return {"url": url, "path": remote_path}
            else:
                return {"error": f"上传失败，status={result.status}"}
        except Exception as e:
            return {"error": str(e)}

    def upload_bytes(self, data: bytes, remote_path: str = None) -> dict:
        """
        上传字节数据到 OSS

        Args:
            data: 字节数据
            remote_path: 远程路径（不指定则自动生成）
        """
        try:
            bucket = self._get_bucket()

            if remote_path is None:
                remote_path = self._generate_path("image.jpg")

            result = bucket.put_object(remote_path, data)

            if result.status == 200:
                url = f"{self.config['domain']}/{remote_path}"
                return {"url": url, "path": remote_path}
            else:
                return {"error": f"上传失败，status={result.status}"}
        except Exception as e:
            return {"error": str(e)}

    def _generate_path(self, original_filename: str) -> str:
        """生成远程路径"""
        template = self.config.get("upload_path", "order/{date}/{uniqid}.jpg")
        date_str = datetime.now().strftime("%Y%m%d")
        uniqid = uuid.uuid4().hex[:8]
        ext = Path(original_filename).suffix or ".jpg"

        path = template.format(date=date_str, uniqid=uniqid)
        if not path.endswith(ext):
            path += ext

        return path


def main():
    parser = argparse.ArgumentParser(description="上传图片到阿里云 OSS")
    parser.add_argument("local_path", help="本地图片路径")
    args = parser.parse_args()

    try:
        from src.core.config import get_config
        uploader = OSSUploader(get_config().oss_config)
        result = uploader.upload(args.local_path)
    except Exception as e:
        result = {"error": str(e)}

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
