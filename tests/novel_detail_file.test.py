import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as novel_app


class NovelDetailFileTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.init_db()

        self.book_path = Path(self.tmpdir.name) / 'detail-book.txt'
        self.book_content = '第一章 开始\n这是正文。\n第二章 继续\n还是正文。\n'
        self.book_path.write_text(self.book_content, encoding='utf-8')

        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO novels (title, file_path, status) VALUES (?, ?, ?)',
            ('详情测试小说', str(self.book_path), 1)
        )
        self.novel_id = cursor.lastrowid
        conn.commit()
        conn.close()
        self.client = novel_app.app.test_client()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        self.tmpdir.cleanup()

    def test_check_file_returns_detail_metadata(self):
        response = self.client.get(f'/api/novels/{self.novel_id}/check-file')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        data = payload['data']
        self.assertTrue(data['file_found'])
        self.assertEqual(data['file_size'], self.book_path.stat().st_size)
        self.assertEqual(data['file_extension'], '.txt')
        self.assertTrue(data['is_text_readable'])
        self.assertIsNotNone(data['file_modified_at'])


if __name__ == '__main__':
    unittest.main()
