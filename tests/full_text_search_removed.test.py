import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as novel_app


class FullTextSearchRemovedTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.init_db()
        self.client = novel_app.app.test_client()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        self.tmpdir.cleanup()

    def test_full_text_search_api_is_removed(self):
        response = self.client.get('/api/search/fulltext?q=test')

        self.assertEqual(response.status_code, 404)

    def test_full_text_search_tables_are_not_created_for_new_databases(self):
        conn = sqlite3.connect(novel_app.DATABASE)
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
            ).fetchall()
        }
        conn.close()

        self.assertNotIn('novel_search_index', table_names)
        self.assertNotIn('novel_search_index_meta', table_names)


if __name__ == '__main__':
    unittest.main()
