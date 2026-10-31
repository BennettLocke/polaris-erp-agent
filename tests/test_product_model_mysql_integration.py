"""Opt-in real SQL checks. This can only target the disposable loopback database."""
import io
import os
from pathlib import Path
import threading
import unittest
import uuid
from contextlib import ExitStack
from unittest.mock import patch

import pymysql
from pymysql.cursors import DictCursor

from scripts.deploy_database_schema import split_sql
from src.engine.native_db import NativeDBClient
from src.services.business.products import ProductService
from src.channels import http_api
from tests.test_product_models import glb

ROOT = Path(__file__).resolve().parents[1]


def model_test_database():
    """Never use .env or caller-selected credentials for integration writes."""
    connection = pymysql.connect(host='127.0.0.1', port=13319, user='root', password='',
        database='sjagent_model_test', charset='utf8mb4', cursorclass=DictCursor, autocommit=True)
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE() AS name')
        assert cursor.fetchone()['name'] == 'sjagent_model_test'
    db = object.__new__(NativeDBClient)
    db._local = threading.local()
    db._local.connection = connection
    db.db_config = {'host': '127.0.0.1', 'port': 13319, 'name': 'sjagent_model_test',
        'user': 'root', 'password': '', 'charset': 'utf8mb4'}
    return db


@unittest.skipUnless(os.getenv('SJAGENT_RUN_MODEL_MYSQL_TESTS') == '1', 'requires disposable MariaDB at 127.0.0.1:13319')
class ProductModelMysqlIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = model_test_database()
        with cls.db.cursor() as cursor:
            for filename in ('001_product_catalog.sql', '002_business_core.sql', '003_system_settings.sql', '005_product_models.sql'):
                for sql in split_sql((ROOT / 'database/schema' / filename).read_text(encoding='utf-8')):
                    cursor.execute(sql)
            cursor.execute("INSERT IGNORE INTO product_unit (id,name,code,unit_type,created_at,updated_at) VALUES (1,'套','set','sale',NOW(),NOW())")
            cursor.execute("INSERT IGNORE INTO product_category (id,name,product_type,created_at,updated_at) VALUES (1,'测试礼盒','gift_box',NOW(),NOW())")

    @classmethod
    def tearDownClass(cls):
        cls.db._get_connection().close()

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.spu_ids = []
        self.asset_ids = []
        self.cleanup = self.stack.enter_context(patch('src.services.business.product_models.cleanup_model_object', return_value=True))
        self.stack.enter_context(patch.object(http_api, '_current_web_user', return_value={'id': 9007}))
        self.stack.enter_context(patch.object(http_api, '_has_permission', return_value=True))
        self.service = ProductService(self.db)
        self.stack.enter_context(patch('src.channels.http_api.product_models.get_product_service', return_value=self.service))
        self.stack.enter_context(patch.object(http_api, 'get_product_service', return_value=self.service))
        self.stack.enter_context(patch('src.services.business.product_models.upload_model_file', side_effect=lambda *args: {
            'url': 'https://example.invalid/model.glb', 'path': f'product_models/20261030/{uuid.uuid4().hex}.glb'}))
        self.client = http_api.app.test_client()

    def tearDown(self):
        with self.db.cursor() as cursor:
            for spu in self.spu_ids:
                cursor.execute('DELETE FROM product_model_binding WHERE spu_id=%s', (spu,))
                cursor.execute('DELETE FROM product_media WHERE spu_id=%s', (spu,))
                cursor.execute('DELETE FROM product_sku WHERE spu_id=%s', (spu,))
                cursor.execute('DELETE FROM product_spu WHERE id=%s', (spu,))
            for asset in self.asset_ids:
                cursor.execute('DELETE FROM product_model_asset WHERE id=%s', (asset,))

    def upload(self):
        response = self.client.post('/api/product/models/upload', data={'model': (io.BytesIO(glb()), 'integration.glb')})
        self.assertEqual(response.status_code, 200, response.get_json())
        asset = response.get_json()['data']
        self.asset_ids.append(asset['id'])
        return asset

    def create(self, asset=None):
        nonce = uuid.uuid4().hex[:10]
        payload = {'title': '模型集成测试', 'product_type': 'gift_box', 'product_category_id': [1], 'base': {
            'new_red': {'spec': '红色', 'coding': 'MT_RED_' + nonce, 'unit': {'new': {'unit_id': 1, 'price': 20}}},
            'new_blue': {'spec': '蓝色', 'coding': 'MT_BLUE_' + nonce, 'unit': {'new': {'unit_id': 1, 'price': 20}}}}}
        if asset is not None:
            payload['model_asset_id'] = asset['id']
        response = self.client.post('/api/product/save', json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()['data']
        self.spu_ids.append(result['spu_id'])
        return result

    def edit(self, result, **extra):
        payload = {'id': result['id'], 'title': '模型集成测试', 'base': {str(sku): {'spec': f'颜色{index}'} for index, sku in enumerate(result['sku_ids'])}, **extra}
        return self.client.post('/api/product/save', json=payload)

    def test_upload_bind_shared_colors_replace_unbind_and_no_cross_product_reuse(self):
        first = self.upload()
        product = self.create(first)
        for sku in product['sku_ids']:
            response = self.client.get(f'/api/product/{sku}')
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(response.get_json()['data']['model']['id'], first['id'])
        self.assertEqual(self.edit(product).status_code, 200)
        self.assertEqual(self.db.product_model_for_spu(product['spu_id'])['id'], first['id'])
        second = self.upload()
        self.assertEqual(self.edit(product, model_asset_id=second['id']).status_code, 200)
        self.assertEqual(self.db.product_model_for_spu(product['spu_id'])['id'], second['id'])
        self.assertIsNotNone(self.db.product_model_asset(first['id']))
        self.assertEqual(self.edit(product, model_asset_id=None).status_code, 200)
        other = self.create()
        response = self.edit(other, title='must roll back', model_asset_id=first['id'])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.query('SELECT title FROM product_spu WHERE id=%s', (other['spu_id'],))[0]['title'], '模型集成测试')

    def test_cancellation_cleanup_retry_and_late_save_failure_are_atomic(self):
        asset = self.upload()
        self.cleanup.return_value = False
        response = self.client.delete(f"/api/product/models/{asset['id']}/pending")
        self.assertFalse(response.get_json()['data']['storage_deleted'])
        self.cleanup.return_value = True
        response = self.client.delete(f"/api/product/models/{asset['id']}/pending")
        self.assertTrue(response.get_json()['data']['storage_deleted'])
        self.assertIsNone(self.db.product_model_asset(asset['id']))
        product = self.create()
        fresh = self.upload()
        with patch.object(self.db, '_replace_product_media', side_effect=RuntimeError('injected late save failure')):
            response = self.edit(product, title='must roll back', model_asset_id=fresh['id'])
        self.assertEqual(response.status_code, 500)
        self.assertIsNone(self.db.product_model_for_spu(product['spu_id']))
        self.assertIsNone(self.db.product_model_asset(fresh['id'])['origin_spu_id'])
        self.assertEqual(self.db.query('SELECT title FROM product_spu WHERE id=%s', (product['spu_id'],))[0]['title'], '模型集成测试')
