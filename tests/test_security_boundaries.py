"""Security boundary regression tests for sessions and image handling."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.session import SessionManager, normalize_session_id
from src.channels.http_api import _is_safe_remote_image_url, _validate_saved_image


class SecurityBoundaryTests(unittest.TestCase):
    def test_session_id_rejects_path_traversal(self):
        self.assertEqual(normalize_session_id("abc_DEF-123"), "abc_DEF-123")
        with self.assertRaises(ValueError):
            normalize_session_id("../secret")
        with self.assertRaises(ValueError):
            SessionManager("..\\secret")

    def test_crop_source_url_blocks_private_hosts(self):
        self.assertFalse(_is_safe_remote_image_url("http://127.0.0.1/admin.jpg"))
        self.assertFalse(_is_safe_remote_image_url("http://169.254.169.254/latest/meta-data.jpg"))
        self.assertFalse(_is_safe_remote_image_url("https://localhost/image.jpg"))
        self.assertTrue(_is_safe_remote_image_url("https://img.513sjbz.com/products/a.jpg"))
        self.assertTrue(_is_safe_remote_image_url("https://bucket.oss-cn-hangzhou.aliyuncs.com/products/a.jpg"))

    def test_saved_image_validation_rejects_fake_jpg(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_image = Path(tmp_dir) / "fake.jpg"
            fake_image.write_bytes(b"not actually an image")

            with self.assertRaises(ValueError):
                _validate_saved_image(fake_image)

    def test_saved_image_validation_rejects_disguised_gif(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_jpg = Path(tmp_dir) / "disguised.jpg"
            Image.new("RGB", (2, 2), "red").save(fake_jpg, format="GIF")

            with self.assertRaisesRegex(ValueError, "图片文件格式无效"):
                _validate_saved_image(fake_jpg)


if __name__ == "__main__":
    unittest.main()
