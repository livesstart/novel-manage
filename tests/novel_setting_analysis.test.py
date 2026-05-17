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


LATE_CONTEXT_MARKER = 'SETTING_LATE_CONTEXT_MARKER_AFTER_12000'


class FakeSettingAIClient:
    def __init__(self):
        self.messages = None

    def chat(self, messages, stream=False):
        self.messages = messages
        return json.dumps({
            'settings': [
                {
                    'category': '世界观',
                    'name': '星河钥匙',
                    'summary': '能开启遗迹入口的核心设定。',
                    'details': '星河钥匙会在满月时回应持有者，并指向旧城遗迹。',
                    'evidence': '林舟第一次发现星河钥匙，它在满月下发光。',
                    'confidence': 0.91,
                },
                {
                    'category': '组织',
                    'name': '旧城守望会',
                    'summary': '守护旧城遗迹入口的地下组织。',
                    'details': '成员通过银色徽记识别身份。',
                    'evidence': '沈秋提到旧城守望会一直守着遗迹入口。',
                    'confidence': 0.82,
                },
            ]
        }, ensure_ascii=False)


class NovelSettingAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        self.original_get_ai_client = ai_routes.get_ai_client
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.init_db()

        self.book_path = Path(self.tmpdir.name) / 'settings.txt'
        self.book_path.write_text(
            '第一章 星河钥匙\n林舟第一次发现星河钥匙，它在满月下发光。\n'
            '第二章 守望会\n沈秋提到旧城守望会一直守着遗迹入口。\n',
            encoding='utf-8'
        )
        self.book_path.write_text(
            self.book_path.read_text(encoding='utf-8')
            + ('front-only filler line for context migration.\n' * 420)
            + f'\n{LATE_CONTEXT_MARKER}\n',
            encoding='utf-8'
        )

        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO novels (title, author, file_path, status) VALUES (?, ?, ?, ?)',
            ('设定提取测试', '测试作者', str(self.book_path), 1)
        )
        self.novel_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.fake_client = FakeSettingAIClient()
        ai_routes.get_ai_client = lambda: self.fake_client
        self.client = novel_app.app.test_client()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        ai_routes.get_ai_client = self.original_get_ai_client
        self.tmpdir.cleanup()

    def test_setting_analysis_is_generated_and_persisted(self):
        response = self.client.post(f'/api/ai/novels/{self.novel_id}/settings/analyze')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        data = payload['data']
        self.assertEqual(data['setting_count'], 2)
        self.assertEqual(data['settings'][0]['category'], '世界观')
        self.assertEqual(data['settings'][0]['name'], '星河钥匙')
        self.assertEqual(data['settings'][0]['summary'], '能开启遗迹入口的核心设定。')
        self.assertEqual(data['settings'][0]['confidence'], 0.91)
        self.assertIn('Novel content context', self.fake_client.messages[1]['content'])
        self.assertIn(LATE_CONTEXT_MARKER, self.fake_client.messages[1]['content'])

        read_response = self.client.get(f'/api/novels/{self.novel_id}/settings')
        read_payload = read_response.get_json()

        self.assertEqual(read_response.status_code, 200)
        self.assertTrue(read_payload['success'])
        self.assertEqual(read_payload['data']['analysis_status'], 'completed')
        self.assertEqual(read_payload['data']['setting_count'], 2)
        self.assertEqual(read_payload['data']['settings'][1]['name'], '旧城守望会')

    def test_setting_analysis_requires_existing_novel(self):
        response = self.client.post('/api/ai/novels/99999/settings/analyze')
        payload = response.get_json()

        self.assertEqual(response.status_code, 404)
        self.assertFalse(payload['success'])
        self.assertEqual(payload['message'], '小说不存在')

    def test_setting_schema_is_idempotent(self):
        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        ai_routes.ensure_character_analysis_schema(cursor)
        ai_routes.ensure_character_analysis_schema(cursor)

        cursor.execute('PRAGMA table_info(novel_settings)')
        setting_columns = {row[1] for row in cursor.fetchall()}
        cursor.execute('PRAGMA table_info(novel_setting_analysis_runs)')
        run_columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        self.assertIn('category', setting_columns)
        self.assertIn('details', setting_columns)
        self.assertIn('setting_count', run_columns)


if __name__ == '__main__':
    unittest.main()
