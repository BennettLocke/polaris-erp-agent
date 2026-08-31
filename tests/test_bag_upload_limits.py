import io
import tempfile
import unittest
import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.channels import http_api
from src.skills.bag_upload.workflow import BagUploadWorkflow


class BagUploadLimitTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(http_api, 'UPLOAD_DIR', self.tmp))
        self.stack.enter_context(patch.object(http_api, '_current_web_user', return_value={'id': 1}))
        self.stack.enter_context(patch.object(http_api, '_has_permission', return_value=True))
        self.stack.enter_context(patch.object(http_api, 'feature_enabled', return_value=True))
        session = MagicMock()
        session.has_pending.return_value = True
        session.get_pending_intent.return_value = 'bag_upload'
        self.stack.enter_context(patch('src.core.session.SessionManager', return_value=session))
        self.stack.enter_context(patch.object(http_api, '_session_snapshot', return_value={}))
        self.agent = MagicMock()
        self.agent.run.return_value = 'processed'
        self.stack.enter_context(patch.object(http_api, '_agent', self.agent))
        self.client = http_api.app.test_client()

    def upload(self, content, name):
        return self.client.post('/api/images/upload', data={
            'session_id': 'upload-limit-test', 'image': (io.BytesIO(content), name),
        })

    def test_zip_larger_than_old_image_limit_reaches_bag_processor(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as zf:
            zf.writestr('sample.png', b'x' * (26 * 1024 * 1024))
        response = self.upload(archive.getvalue(), 'batch.zip')
        self.assertEqual(response.status_code, 200)
        self.agent.run.assert_called_once()

    def test_large_image_is_rejected_before_processing_or_saving(self):
        response = self.upload(b'x' * (26 * 1024 * 1024), 'sample.png')
        self.assertEqual(response.status_code, 413)
        self.assertTrue(response.is_json)
        self.assertIn('25', response.get_json()['msg'])
        self.assertIn('图片', response.get_json()['msg'])
        self.agent.run.assert_not_called()
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_request_above_zip_limit_returns_json_without_reading_body(self):
        response = self.client.post('/api/images/upload', environ_overrides={
            'CONTENT_LENGTH': str(102 * 1024 * 1024),
            'CONTENT_TYPE': 'multipart/form-data; boundary=test',
            'wsgi.input': io.BytesIO(b''),
        })
        self.assertEqual(response.status_code, 413)
        self.assertTrue(response.is_json)
        self.assertIn('100', response.get_json()['msg'])
        self.agent.run.assert_not_called()

    def test_file_limit_is_not_bypassed_by_multipart_allowance(self):
        with patch.object(http_api, 'MAX_BAG_ARCHIVE_UPLOAD_BYTES', 4096):
            response = self.upload(b'x' * 4097, 'batch.zip')
        self.assertEqual(response.status_code, 413)
        self.agent.run.assert_not_called()
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_zip_at_file_limit_is_allowed(self):
        with patch.object(http_api, 'MAX_BAG_ARCHIVE_UPLOAD_BYTES', 4096):
            response = self.upload(b'x' * 4096, 'batch.zip')
        self.assertEqual(response.status_code, 200)
        self.agent.run.assert_called_once()

    def test_zip_requires_active_bag_workflow(self):
        with patch('src.core.session.SessionManager') as session:
            session.return_value.has_pending.return_value = False
            response = self.upload(b'zip', 'batch.zip')
        self.assertEqual(response.status_code, 400)
        self.agent.run.assert_not_called()

    def test_other_endpoints_keep_original_request_limit(self):
        response = self.client.post('/api/product/upload', environ_overrides={
            'CONTENT_LENGTH': str(26 * 1024 * 1024),
            'CONTENT_TYPE': 'multipart/form-data; boundary=test',
            'wsgi.input': io.BytesIO(b''),
        })
        self.assertEqual(response.status_code, 413)

    def test_frontend_can_read_current_limits(self):
        response = self.client.get('/api/images/upload-limits')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data'], {
            'image_bytes': 25 * 1024 * 1024,
            'archive_bytes': 100 * 1024 * 1024,
        })


class BagArchiveSafetyTests(unittest.TestCase):
    def extract(self, names, content=b'png'):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / 'batch.zip'
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for name in names:
                    zf.writestr(name, content)
            output = root / 'out'
            output.mkdir()
            return BagUploadWorkflow()._extract_zip_images(archive, output)

    def test_normal_nested_png_archive_is_supported(self):
        rows = self.extract(['folder/岩茶.png', 'README.txt'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['title'], '岩茶')

    def test_too_many_images_are_rejected_before_extracting(self):
        with self.assertRaisesRegex(ValueError, '100'):
            self.extract([f'{n}.png' for n in range(101)])

    def test_oversized_member_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '64'):
            self.extract(['large.png'], b'x' * (65 * 1024 * 1024))

    def test_total_unpacked_size_is_limited(self):
        from src.services.bag_archive import validate_bag_archive
        archive = MagicMock()
        infos = []
        for n in range(9):
            info = zipfile.ZipInfo(f'{n}.png')
            info.file_size = 64 * 1024 * 1024
            infos.append(info)
        archive.infolist.return_value = infos
        with self.assertRaisesRegex(ValueError, '512'):
            validate_bag_archive(archive)

    def test_excessive_non_image_entries_are_rejected(self):
        with self.assertRaisesRegex(ValueError, '1000'):
            self.extract([f'{n}.txt' for n in range(1001)])


if __name__ == '__main__':
    unittest.main()
