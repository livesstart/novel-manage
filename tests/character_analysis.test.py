import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import ai_routes
import app as novel_app


class FakeAIClient:
    def __init__(self):
        self.messages = None

    def chat(self, messages, stream=False):
        self.messages = messages
        return json.dumps({
            'characters': [
                {
                    'name': '林舟',
                    'aliases': ['小舟'],
                    'role_type': '主角',
                    'description': '负责追查星河钥匙的核心人物。',
                    'traits': ['冷静', '执着'],
                    'first_chapter_index': 0,
                    'evidence': '林舟第一次发现星河钥匙。',
                    'confidence': 0.92,
                },
                {
                    'name': '沈秋',
                    'aliases': [],
                    'role_type': '同伴',
                    'description': '协助林舟破解线索。',
                    'traits': ['敏锐'],
                    'first_chapter_index': 1,
                    'evidence': '沈秋提出另一种推理方向。',
                    'confidence': 0.88,
                },
            ],
            'relations': [
                {
                    'source': '林舟',
                    'target': '沈秋',
                    'relation_type': '同盟',
                    'description': '两人共同追查星河钥匙。',
                    'evidence': '林舟和沈秋决定一起行动。',
                    'confidence': 0.84,
                }
            ],
        }, ensure_ascii=False)


class CharacterAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        self.original_get_ai_client = ai_routes.get_ai_client
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.init_db()

        self.book_path = Path(self.tmpdir.name) / 'characters.txt'
        self.book_path.write_text(
            '第一章 星河钥匙\n林舟第一次发现星河钥匙。\n第二章 同行\n沈秋提出另一种推理方向，林舟和沈秋决定一起行动。\n',
            encoding='utf-8'
        )

        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO novels (title, author, file_path, status) VALUES (?, ?, ?, ?)',
            ('角色分析测试', '测试作者', str(self.book_path), 1)
        )
        self.novel_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.fake_client = FakeAIClient()
        ai_routes.get_ai_client = lambda: self.fake_client
        self.client = novel_app.app.test_client()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        ai_routes.get_ai_client = self.original_get_ai_client
        self.tmpdir.cleanup()

    def test_character_analysis_is_generated_and_persisted(self):
        response = self.client.post(f'/api/ai/novels/{self.novel_id}/characters/analyze')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        data = payload['data']
        self.assertEqual(data['character_count'], 2)
        self.assertEqual(data['relation_count'], 1)
        self.assertEqual(data['characters'][0]['name'], '林舟')
        self.assertEqual(data['characters'][0]['aliases'], ['小舟'])
        self.assertEqual(data['relations'][0]['source_name'], '林舟')
        self.assertEqual(data['relations'][0]['target_name'], '沈秋')
        self.assertIn('正文片段', self.fake_client.messages[1]['content'])

        read_response = self.client.get(f'/api/novels/{self.novel_id}/characters')
        read_payload = read_response.get_json()

        self.assertEqual(read_response.status_code, 200)
        self.assertTrue(read_payload['success'])
        self.assertEqual(read_payload['data']['character_count'], 2)
        self.assertEqual(read_payload['data']['relation_count'], 1)
        self.assertEqual(read_payload['data']['analysis_status'], 'completed')

    def test_character_analysis_requires_existing_novel(self):
        response = self.client.post('/api/ai/novels/99999/characters/analyze')
        payload = response.get_json()

        self.assertEqual(response.status_code, 404)
        self.assertFalse(payload['success'])


if __name__ == '__main__':
    unittest.main()
