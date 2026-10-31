"""Opt-in real SQL checks. This can only target the disposable loopback database."""
import io
import json
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
from tests.test_product_models import document, glb
from scripts.migrate_product_model_config import migrate

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
            migrate(cursor)
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
        doc = document()
        doc['materials'] = [{'name': 'Paper'}, {'name': 'Foil'}]
        response = self.client.post('/api/product/models/upload', data={'model': (io.BytesIO(glb(doc)), 'integration.glb')})
        self.assertEqual(response.status_code, 200, response.get_json())
        asset = response.get_json()['data']
        self.asset_ids.append(asset['id'])
        return asset

    def create(self, asset=None, **extra):
        nonce = uuid.uuid4().hex[:10]
        payload = {'title': '模型集成测试', 'product_type': 'gift_box', 'product_category_id': [1], 'base': {
            'new_red': {'spec': '红色', 'coding': 'MT_RED_' + nonce, 'unit': {'new': {'unit_id': 1, 'price': 20}}},
            'new_blue': {'spec': '蓝色', 'coding': 'MT_BLUE_' + nonce, 'unit': {'new': {'unit_id': 1, 'price': 20}}}}}
        if asset is not None:
            payload['model_asset_id'] = asset['id']
        payload.update(extra)
        response = self.client.post('/api/product/save', json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()['data']
        self.spu_ids.append(result['spu_id'])
        return result

    def edit(self, result, **extra):
        payload = {'id': result['id'], 'title': '模型集成测试', 'base': {str(sku): {'spec': f'颜色{index}'} for index, sku in enumerate(result['sku_ids'])}, **extra}
        return self.client.post('/api/product/save', json=payload)

    def model_config(self, asset, colors, default=None, **extra):
        return {'version': 1, 'asset_id': asset['id'], 'material_index': 1,
            'sku_colors': colors, 'default_sku_key': default, 'camera_direction': [0, 3, 4],
            'default_pose': 'open', **extra}

    def stored_config(self, product):
        value = self.db.query('SELECT model_config FROM product_model_binding WHERE spu_id=%s',
                              (product['spu_id'],))[0]['model_config']
        return json.loads(value) if isinstance(value, str) else value

    def color_ids(self, product):
        return {row['color']: row['id'] for row in self.db.query(
            'SELECT id, color FROM product_sku WHERE spu_id=%s', (product['spu_id'],))}

    def test_config_new_key_mapping_replace_without_config_reset_and_null(self):
        asset = self.upload()
        product = self.create(asset, model_config=self.model_config(asset,
            {'new_red': '#aa1122', 'new_blue': '#3344bb'}, 'new_red'))
        ids = self.color_ids(product)
        red, blue = str(ids['红色']), str(ids['蓝色'])
        original = self.stored_config(product)
        self.assertEqual(original['sku_colors'], {red: '#AA1122', blue: '#3344BB'})
        self.assertEqual(original['camera_direction'], [0, .6, .8])
        self.assertEqual(self.edit(product).status_code, 200)
        self.assertEqual(self.stored_config(product), original)
        replacement = self.upload()
        self.assertEqual(self.edit(product, model_asset_id=replacement['id']).status_code, 200)
        replaced = self.stored_config(product)
        self.assertEqual(replaced['asset_id'], replacement['id'])
        self.assertEqual(replaced['sku_colors'], original['sku_colors'])
        self.assertIsNone(replaced['material_index'])
        self.assertIsNone(replaced['camera_direction'])
        self.assertEqual(replaced['default_pose'], 'open')
        detail = self.client.get(f"/api/product/{red}").get_json()['data']
        self.assertEqual(detail['model_config'], replaced)
        self.assertNotIn('model_config', detail['model'])
        self.assertEqual(self.edit(product, model_config=None).status_code, 200)
        self.assertIsNone(self.stored_config(product))
        self.assertEqual(self.db.product_model_for_spu(product['spu_id'])['id'], replacement['id'])

    def test_config_validation_rolls_back_product_skus_new_binding_and_asset_origin(self):
        product = self.create()
        fresh = self.upload()
        before = self.db.query('SELECT * FROM product_sku WHERE spu_id=%s ORDER BY id', (product['spu_id'],))
        response = self.edit(product, title='must roll back', model_asset_id=fresh['id'],
            model_config=self.model_config(fresh, {str(product['sku_ids'][0]): '#112233'}, material_index=999))
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(self.db.query('SELECT * FROM product_sku WHERE spu_id=%s ORDER BY id', (product['spu_id'],)), before)
        self.assertIsNone(self.db.product_model_for_spu(product['spu_id']))
        self.assertIsNone(self.db.product_model_asset(fresh['id'])['origin_spu_id'])
        self.assertEqual(self.db.query('SELECT title FROM product_spu WHERE id=%s', (product['spu_id'],))[0]['title'], '模型集成测试')

    def test_deleted_colors_pruned_on_ordinary_save_and_mini_filters_listed_colors(self):
        asset = self.upload()
        product = self.create(asset, model_config=self.model_config(asset,
            {'new_red': '#aa1122', 'new_blue': '#3344bb'}, 'new_red'))
        ids = self.color_ids(product)
        red, blue = ids['红色'], ids['蓝色']
        with self.db.cursor() as cursor:
            cursor.execute('UPDATE product_sku SET is_listed=IF(id=%s,0,1) WHERE spu_id=%s', (red, product['spu_id']))
        response = self.client.get(f'/api/mini/goods/detail?id={blue}')
        self.assertEqual(response.status_code, 200, response.get_json())
        goods = response.get_json()['data']['goods']
        self.assertEqual(goods['model_config']['sku_colors'], {str(blue): '#3344BB'})
        self.assertEqual(goods['model_config']['default_sku_key'], str(blue))
        self.assertEqual(set(goods['model']), {'id', 'url', 'animation_count', 'materials'})
        self.assertEqual(goods['model_url'], asset['url'])
        self.assertTrue(goods['has_model'])
        with self.db.cursor() as cursor:
            cursor.execute('UPDATE product_sku SET deleted_at=NOW() WHERE id=%s', (red,))
        response = self.client.post('/api/product/save', json={'id': blue, 'title': 'Pruned', 'base': {str(blue): {'spec': 'Renamed'}}})
        self.assertEqual(response.status_code, 200, response.get_json())
        stored = self.stored_config(product)
        self.assertEqual(stored['sku_colors'], {str(blue): '#3344BB'})
        self.assertEqual(stored['default_sku_key'], str(blue))
        self.assertNotIn('Renamed', json.dumps(stored))

    def test_migration_repeated_preserves_binding_and_config_exactly(self):
        asset = self.upload()
        product = self.create(asset, model_config=self.model_config(asset, {'new_blue': '#112233'}))
        before = self.db.query('SELECT * FROM product_model_binding WHERE spu_id=%s', (product['spu_id'],))
        with self.db.cursor() as cursor:
            self.assertFalse(migrate(cursor))
            self.assertFalse(migrate(cursor))
        self.assertEqual(self.db.query('SELECT * FROM product_model_binding WHERE spu_id=%s', (product['spu_id'],)), before)

    def test_ordinary_save_with_old_snapshot_preserves_concurrently_added_sku_color(self):
        asset = self.upload()
        product = self.create(asset, model_config=self.model_config(asset,
            {'new_red': '#AA1122', 'new_blue': '#3344BB'}))
        stale_db = model_test_database()
        connection = stale_db._get_connection()
        self.addCleanup(connection.close)
        with connection.cursor() as cursor:
            cursor.execute('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cursor.execute('SELECT CONNECTION_ID() AS id')
            stale_connection_id = cursor.fetchone()['id']
        self.assertNotEqual(stale_connection_id, self.db.query('SELECT CONNECTION_ID() AS id')[0]['id'])
        original_ids = set(product['sku_ids'])
        original_resolve = stale_db.resolve_sku_id
        committed = {}

        def resolve_with_interleaved_commit(product_id, cursor=None):
            resolved = original_resolve(product_id, cursor=cursor)
            if not committed:
                # The ordinary save's initial lookup established its read view,
                # but it has not taken the SPU write lock yet.
                cursor.execute('SELECT id FROM product_sku WHERE spu_id=%s', (product['spu_id'],))
                self.assertEqual({row['id'] for row in cursor.fetchall()}, original_ids)
                base = {str(sku): {'spec': f'Original {index}'}
                        for index, sku in enumerate(product['sku_ids'])}
                base['new_green'] = {'spec': 'Green', 'unit_id': 1}
                colors = {str(sku): '#112233' for sku in product['sku_ids']}
                colors['new_green'] = '#00FF00'
                result = self.db.save_product({'id': product['id'], 'title': 'Concurrent addition',
                    'base': base, 'model_config': self.model_config(asset, colors, 'new_green')},
                    operator_user_id=9007)
                self.assertEqual(result['code'], 0)
                green_id, = set(result['data']['sku_ids']) - original_ids
                committed.update(green_id=green_id, config=self.stored_config(product))
                self.assertEqual(committed['config']['sku_colors'][str(green_id)], '#00FF00')
                # Prove the second connection committed while this transaction
                # still sees the pre-addition snapshot through a plain SELECT.
                cursor.execute('SELECT id FROM product_sku WHERE spu_id=%s', (product['spu_id'],))
                self.assertEqual({row['id'] for row in cursor.fetchall()}, original_ids)
            return resolved

        with patch.object(stale_db, 'resolve_sku_id', side_effect=resolve_with_interleaved_commit):
            result = stale_db.save_product({'id': product['id'], 'title': 'Ordinary stale save',
                'base': {str(sku): {'spec': f'Original {index}'}
                         for index, sku in enumerate(product['sku_ids'])}})
        self.assertEqual(result['code'], 0)
        live_ids = {row['id'] for row in self.db.query(
            'SELECT id FROM product_sku WHERE spu_id=%s AND deleted_at IS NULL', (product['spu_id'],))}
        self.assertIn(committed['green_id'], live_ids)
        self.assertEqual(self.stored_config(product), committed['config'])

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
