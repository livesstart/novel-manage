import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as novel_app


class ReaderProgressTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.init_db()

        self.book_path = Path(self.tmpdir.name) / 'book.txt'
        self.book_path.write_text(
            '第1章 开始\n这里是开头正文\n第2章 继续\n这里是中段正文\n第3章 结束\n这里是结尾正文',
            encoding='utf-8'
        )

        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO novels (title, file_path, status) VALUES (?, ?, ?)',
            ('测试小说', str(self.book_path), 0)
        )
        self.novel_id = cursor.lastrowid
        conn.commit()
        conn.close()
        self.client = novel_app.app.test_client()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        self.tmpdir.cleanup()

    def test_save_progress_and_return_it_when_reader_opens(self):
        response = self.client.put(
            f'/api/novels/{self.novel_id}/reading-progress',
            json={'chapter_index': 1, 'scroll_percent': 42.5}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])

        read_response = self.client.get(f'/api/novels/{self.novel_id}/read')
        payload = read_response.get_json()

        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(payload['data']['reading_progress']['chapter_index'], 1)
        self.assertEqual(payload['data']['reading_progress']['scroll_percent'], 42.5)
        self.assertIsNotNone(payload['data']['reading_progress']['last_read_at'])
        self.assertEqual(payload['data']['initial_chapter']['index'], 1)
        self.assertIn('这里是中段正文', payload['data']['initial_chapter']['content'])

    def test_save_progress_clamps_values_to_available_range(self):
        response = self.client.put(
            f'/api/novels/{self.novel_id}/reading-progress',
            json={'chapter_index': 99, 'scroll_percent': 999}
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['data']['reading_progress']['chapter_index'], 2)
        self.assertEqual(payload['data']['reading_progress']['scroll_percent'], 100)


if __name__ == '__main__':
    unittest.main()
