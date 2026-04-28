import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import ai_client


class AIConfigProxyTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = ai_client.DATABASE
        ai_client.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        ai_client.AIConfig.init_table()

    def tearDown(self):
        ai_client.DATABASE = self.original_database
        self.tmpdir.cleanup()

    def test_ai_config_table_persists_proxy_fields(self):
        conn = sqlite3.connect(ai_client.DATABASE)
        columns = {row[1] for row in conn.execute('PRAGMA table_info(ai_configs)').fetchall()}
        conn.close()

        self.assertIn('use_proxy', columns)
        self.assertIn('proxy_url', columns)

        config_id = ai_client.AIConfig.save_config({
            'name': 'Gemini via proxy',
            'provider': 'gemini-native',
            'api_key': 'test-key',
            'model': 'gemini-2.0-flash',
            'use_proxy': True,
            'proxy_url': 'http://127.0.0.1:7890',
        })

        config = ai_client.AIConfig.get_config(config_id)
        self.assertEqual(config.get('use_proxy'), 1)
        self.assertEqual(config.get('proxy_url'), 'http://127.0.0.1:7890')

    def test_client_request_kwargs_include_proxy_only_when_enabled(self):
        proxied_client = ai_client.GeminiClient({
            'api_key': 'test-key',
            'model': 'gemini-2.0-flash',
            'use_proxy': 1,
            'proxy_url': 'http://127.0.0.1:7890',
        })
        self.assertEqual(
            proxied_client._request_kwargs(),
            {'proxies': {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}},
        )

        direct_client = ai_client.GeminiClient({
            'api_key': 'test-key',
            'model': 'gemini-2.0-flash',
            'use_proxy': 0,
            'proxy_url': 'http://127.0.0.1:7890',
        })
        self.assertEqual(direct_client._request_kwargs(), {})


if __name__ == '__main__':
    unittest.main()
