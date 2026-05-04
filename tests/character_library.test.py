import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as novel_app
import character_routes


class FakeAIClient:
    def chat(self, messages, stream=False):
        return json.dumps({
            'summary': '负责追查星河钥匙的核心行动者。',
            'description': '林舟负责追查星河钥匙。',
            'appearance': '气质冷静。',
            'personality': ['冷静', '执着'],
            'motivation': '查清星河钥匙。',
            'skills': ['推理'],
            'tags': ['核心角色']
        }, ensure_ascii=False)


class CharacterLibraryTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        self.original_get_ai_client = character_routes.get_ai_client
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.init_db()
        character_routes.get_ai_client = lambda: FakeAIClient()
        self.client = novel_app.app.test_client()

        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO novels (title, author, description, file_path, status) VALUES (?, ?, ?, ?, ?)',
            ('角色库测试', '测试作者', '星河钥匙相关故事。', str(Path(self.tmpdir.name) / 'book.txt'), 1)
        )
        self.novel_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO novels (title, author, description, status) VALUES (?, ?, ?, ?)',
            ('另一本小说', '测试作者', '用于跨书关系校验。', 1)
        )
        self.other_novel_id = cursor.lastrowid
        conn.commit()
        conn.close()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        character_routes.get_ai_client = self.original_get_ai_client
        self.tmpdir.cleanup()

    def create_character(self, name='林舟', novel_id=None, role_type='主角'):
        response = self.client.post('/api/characters', json={
            'novel_id': novel_id or self.novel_id,
            'name': name,
            'aliases': ['小舟'] if name == '林舟' else [],
            'role_type': role_type,
            'description': f'{name}的角色说明。',
            'traits': ['冷静'],
            'profile': {
                'summary': f'{name}的角色定位。',
                'appearance': '气质冷静。',
                'personality': ['冷静'],
                'motivation': '查清真相。',
                'skills': ['推理'],
                'tags': ['核心角色']
            },
            'notes': '手动备注'
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['success'])
        return payload['data']

    def test_character_crud_and_filters(self):
        created = self.create_character()
        self.assertEqual(created['name'], '林舟')
        self.assertEqual(created['novel_id'], self.novel_id)
        self.assertEqual(created['notes'], '手动备注')
        self.assertEqual(created['is_manual'], 1)

        list_response = self.client.get('/api/characters?keyword=林舟&role_type=主角&tag=核心角色')
        list_payload = list_response.get_json()
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(list_payload['success'])
        self.assertEqual(list_payload['data']['total'], 1)
        self.assertEqual(list_payload['data']['items'][0]['novel_title'], '角色库测试')

        detail_response = self.client.get(f"/api/characters/{created['id']}")
        detail_payload = detail_response.get_json()
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_payload['data']['profile']['skills'], ['推理'])

        update_response = self.client.put(f"/api/characters/{created['id']}", json={
            'name': '林舟',
            'aliases': ['小舟', '林调查员'],
            'role_type': '主角',
            'description': '更新后的角色说明。',
            'traits': ['冷静', '执着'],
            'profile': {
                'summary': '更新后的定位。',
                'appearance': '克制而专注。',
                'personality': ['冷静', '执着'],
                'motivation': '确认钥匙来源。',
                'skills': ['推理', '行动力'],
                'tags': ['核心角色', '调查者']
            },
            'notes': '更新后的备注'
        })
        update_payload = update_response.get_json()
        self.assertEqual(update_response.status_code, 200)
        self.assertTrue(update_payload['success'])
        self.assertEqual(update_payload['data']['aliases'], ['小舟', '林调查员'])
        self.assertEqual(update_payload['data']['notes'], '更新后的备注')

        delete_response = self.client.delete(f"/api/characters/{created['id']}")
        delete_payload = delete_response.get_json()
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_payload['success'])

    def test_relation_editing_rejects_cross_novel_targets(self):
        source = self.create_character('林舟', self.novel_id, '主角')
        target = self.create_character('沈秋', self.novel_id, '同伴')
        other = self.create_character('异书角色', self.other_novel_id, '配角')

        create_response = self.client.post(f"/api/characters/{source['id']}/relations", json={
            'target_character_id': target['id'],
            'relation_type': '同盟',
            'description': '共同追查线索。'
        })
        create_payload = create_response.get_json()
        self.assertEqual(create_response.status_code, 200)
        self.assertTrue(create_payload['success'])
        self.assertEqual(create_payload['data']['relation_type'], '同盟')
        self.assertEqual(create_payload['data']['is_manual'], 1)

        cross_response = self.client.post(f"/api/characters/{source['id']}/relations", json={
            'target_character_id': other['id'],
            'relation_type': '误连',
            'description': '跨书关系不允许。'
        })
        self.assertEqual(cross_response.status_code, 400)

        update_response = self.client.put(f"/api/character-relations/{create_payload['data']['id']}", json={
            'relation_type': '搭档',
            'description': '更新后的关系说明。'
        })
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.get_json()['data']['relation_type'], '搭档')

        delete_response = self.client.delete(f"/api/character-relations/{create_payload['data']['id']}")
        self.assertEqual(delete_response.status_code, 200)

    def test_ai_complete_fills_empty_profile_fields_without_overwriting_notes(self):
        created = self.create_character()
        update_response = self.client.put(f"/api/characters/{created['id']}", json={
            'name': '林舟',
            'aliases': ['小舟'],
            'role_type': '主角',
            'description': '',
            'traits': [],
            'profile': {'summary': '', 'tags': []},
            'notes': '必须保留的手动备注'
        })
        self.assertEqual(update_response.status_code, 200)

        response = self.client.post(f"/api/characters/{created['id']}/ai-complete", json={})
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['data']['profile']['summary'], '负责追查星河钥匙的核心行动者。')
        self.assertEqual(payload['data']['profile']['skills'], ['推理'])
        self.assertEqual(payload['data']['notes'], '必须保留的手动备注')


if __name__ == '__main__':
    unittest.main()
