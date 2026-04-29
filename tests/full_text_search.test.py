import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as novel_app


class FullTextSearchTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.init_db()

        self.book_path = Path(self.tmpdir.name) / 'search-book.txt'
        self.book_path.write_text(
            '第一章 开始\n普通开头内容。\n第二章 线索\n这里藏着星河钥匙这个独特关键词。\n',
            encoding='utf-8'
        )

        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO novels (title, author, file_path, status) VALUES (?, ?, ?, ?)',
            ('全文搜索测试', '测试作者', str(self.book_path), 1)
        )
        self.novel_id = cursor.lastrowid
        conn.commit()
        conn.close()
        self.client = novel_app.app.test_client()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        self.tmpdir.cleanup()

    def test_search_indexes_text_chapters_and_returns_matches(self):
        response = self.client.get('/api/search/fulltext?q=星河钥匙')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['data']['total'], 1)

        result = payload['data']['results'][0]
        self.assertEqual(result['novel_id'], self.novel_id)
        self.assertEqual(result['title'], '全文搜索测试')
        self.assertEqual(result['chapter_index'], 1)
        self.assertEqual(result['chapter_title'], '第二章 线索')
        self.assertIn('星河钥匙', result['snippet'])

    def test_search_requires_a_query(self):
        response = self.client.get('/api/search/fulltext?q=')
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload['success'])


if __name__ == '__main__':
    unittest.main()
