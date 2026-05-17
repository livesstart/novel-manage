import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import ai_routes
import app as novel_app


class FakeReaderAssistantClient:
    def __init__(self):
        self.messages = None

    def chat(self, messages, stream=False):
        self.messages = messages
        return 'The answer uses the current novel context.'


class ReaderAIAssistantTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        self.original_propagate_exceptions = novel_app.app.config.get('PROPAGATE_EXCEPTIONS')
        self.original_get_ai_client = ai_routes.get_ai_client
        self.original_build_novel_ai_context = ai_routes.build_novel_ai_context
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.app.config['PROPAGATE_EXCEPTIONS'] = False
        novel_app.init_db()

        self.book_path = Path(self.tmpdir.name) / 'reader-assistant.txt'
        self.book_path.write_text(
            'Chapter 1\nOpening reader clue.\n'
            + ('reader filler text\n' * 900)
            + 'Chapter 2\nLate reader assistant context marker.\n',
            encoding='utf-8'
        )

        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO novels (title, author, description, file_path, status) VALUES (?, ?, ?, ?, ?)',
            ('Reader Assistant Book', 'Assistant Author', 'A book for reader assistant tests.', str(self.book_path), 1),
        )
        self.novel_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.fake_client = FakeReaderAssistantClient()
        ai_routes.get_ai_client = lambda: self.fake_client
        self.client = novel_app.app.test_client()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        novel_app.app.config['PROPAGATE_EXCEPTIONS'] = self.original_propagate_exceptions
        ai_routes.get_ai_client = self.original_get_ai_client
        ai_routes.build_novel_ai_context = self.original_build_novel_ai_context
        self.tmpdir.cleanup()

    def test_reader_assistant_answers_with_novel_and_current_chapter_context(self):
        response = self.client.post(
            f'/api/ai/novels/{self.novel_id}/reader-assistant',
            json={
                'question': 'What does the late marker imply?',
                'chapter_index': 1,
                'chapter_title': 'Chapter 2',
                'conversation': [
                    {'role': 'user', 'content': 'Summarize the clue.'},
                    {'role': 'assistant', 'content': 'The clue appears late.'},
                ],
            },
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['data']['answer'], 'The answer uses the current novel context.')
        self.assertIn('context', payload['data'])
        self.assertIn('Late reader assistant context marker.', self.fake_client.messages[1]['content'])
        self.assertIn('Current chapter: Chapter 2', self.fake_client.messages[-1]['content'])
        self.assertIn('What does the late marker imply?', self.fake_client.messages[-1]['content'])

    def test_reader_assistant_rejects_empty_question(self):
        response = self.client.post(
            f'/api/ai/novels/{self.novel_id}/reader-assistant',
            json={'question': '   '},
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload['success'])

    def test_reader_assistant_rejects_non_object_json_body(self):
        response = self.client.post(
            f'/api/ai/novels/{self.novel_id}/reader-assistant',
            json='not an object',
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(payload, dict)
        self.assertFalse(payload['success'])
        non_object_message = payload['message']

        response = self.client.post(
            f'/api/ai/novels/{self.novel_id}/reader-assistant',
            json=[],
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(payload, dict)
        self.assertFalse(payload['success'])
        self.assertEqual(payload['message'], non_object_message)

    def test_reader_assistant_requires_ai_client(self):
        ai_routes.get_ai_client = lambda: None

        response = self.client.post(
            f'/api/ai/novels/{self.novel_id}/reader-assistant',
            json={'question': 'Can you answer?'},
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload['success'])

    def test_reader_assistant_wraps_context_errors_in_json_response(self):
        def raise_context_error(*args, **kwargs):
            raise RuntimeError('context boom')

        ai_routes.build_novel_ai_context = raise_context_error

        response = self.client.post(
            f'/api/ai/novels/{self.novel_id}/reader-assistant',
            json={'question': 'Can you answer with context?'},
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 500)
        self.assertIsInstance(payload, dict)
        self.assertFalse(payload['success'])
        self.assertIn('context boom', payload['message'])


if __name__ == '__main__':
    unittest.main()
