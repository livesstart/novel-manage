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


class FakeWritingStyleAIClient:
    def __init__(self):
        self.messages = None

    def chat(self, messages, stream=False):
        self.messages = messages
        return json.dumps({
            'summary': '冷静克制的悬疑叙事，靠细节递进推动真相。',
            'narrative_perspective': '第三人称有限视角，贴近主角观察。',
            'language_texture': '句式简洁，偏理性，偶尔用具象物象压住情绪。',
            'pacing': '线索逐层推进，章节末尾保留轻微悬念。',
            'description_focus': '重视物件、光线和动作细节。',
            'dialogue_style': '对话短促，常用试探和反问推进信息。',
            'emotional_tone': '冷峻、克制、带一点不安。',
            'signature_techniques': [
                {
                    'name': '物件锚点',
                    'description': '用关键物件承载线索和情绪压力。',
                    'evidence': '星河钥匙在满月下发光。',
                    'confidence': 0.91,
                }
            ],
            'examples': [
                {
                    'label': '线索片段',
                    'analysis': '用物件变化暗示谜团正在扩大。',
                    'evidence': '钥匙边缘浮出细小的银色刻痕。',
                    'confidence': 0.86,
                }
            ],
            'imitation_guide': '续写时保持短句和克制心理描写，先写可观察细节，再给出人物判断。',
            'style_prompt': '请用冷静克制的悬疑叙事续写：第三人称有限视角，短句，重视物件和动作细节。',
            'confidence': 0.89,
        }, ensure_ascii=False)


class WritingStyleAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        self.original_get_ai_client = ai_routes.get_ai_client
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.init_db()

        self.book_path = Path(self.tmpdir.name) / 'writing-style.txt'
        self.book_path.write_text(
            '第一章 星河钥匙\n'
            '林舟第一次发现星河钥匙时，它在满月下发光，钥匙边缘浮出细小的银色刻痕。\n'
            '沈秋压低声音问，既然门从未出现，钥匙为什么要醒来？\n',
            encoding='utf-8'
        )

        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO novels (title, author, file_path, status) VALUES (?, ?, ?, ?)',
            ('写作风格测试', '测试作者', str(self.book_path), 1)
        )
        self.novel_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.fake_client = FakeWritingStyleAIClient()
        ai_routes.get_ai_client = lambda: self.fake_client
        self.client = novel_app.app.test_client()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        ai_routes.get_ai_client = self.original_get_ai_client
        self.tmpdir.cleanup()

    def test_writing_style_analysis_is_generated_and_persisted(self):
        response = self.client.post(f'/api/ai/novels/{self.novel_id}/writing-style/analyze')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        data = payload['data']
        self.assertEqual(data['analysis_status'], 'completed')
        self.assertEqual(data['summary'], '冷静克制的悬疑叙事，靠细节递进推动真相。')
        self.assertEqual(data['narrative_perspective'], '第三人称有限视角，贴近主角观察。')
        self.assertEqual(data['signature_techniques'][0]['name'], '物件锚点')
        self.assertEqual(data['examples'][0]['label'], '线索片段')
        self.assertEqual(data['style_prompt'], '请用冷静克制的悬疑叙事续写：第三人称有限视角，短句，重视物件和动作细节。')
        self.assertEqual(data['confidence'], 0.89)
        self.assertIn('正文片段', self.fake_client.messages[1]['content'])

        read_response = self.client.get(f'/api/novels/{self.novel_id}/writing-style')
        read_payload = read_response.get_json()

        self.assertEqual(read_response.status_code, 200)
        self.assertTrue(read_payload['success'])
        self.assertEqual(read_payload['data']['analysis_status'], 'completed')
        self.assertEqual(read_payload['data']['summary'], '冷静克制的悬疑叙事，靠细节递进推动真相。')
        self.assertEqual(read_payload['data']['signature_techniques'][0]['description'], '用关键物件承载线索和情绪压力。')
        self.assertEqual(read_payload['data']['examples'][0]['analysis'], '用物件变化暗示谜团正在扩大。')

    def test_writing_style_analysis_requires_existing_novel(self):
        response = self.client.post('/api/ai/novels/99999/writing-style/analyze')
        payload = response.get_json()

        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(payload)
        self.assertFalse(payload['success'])

    def test_writing_style_schema_is_idempotent(self):
        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        ai_routes.ensure_character_analysis_schema(cursor)
        ai_routes.ensure_character_analysis_schema(cursor)

        cursor.execute('PRAGMA table_info(novel_writing_styles)')
        style_columns = {row[1] for row in cursor.fetchall()}
        cursor.execute('PRAGMA table_info(novel_writing_style_analysis_runs)')
        run_columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        self.assertIn('summary', style_columns)
        self.assertIn('style_prompt', style_columns)
        self.assertIn('signature_techniques_json', style_columns)
        self.assertIn('source_excerpt_chars', run_columns)


if __name__ == '__main__':
    unittest.main()
