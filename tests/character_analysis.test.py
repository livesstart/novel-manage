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
                    'summary': '追查星河钥匙的核心行动者。',
                    'description': '负责追查星河钥匙的核心人物。',
                    'appearance': '气质冷静，行动时克制而专注。',
                    'traits': ['冷静', '执着'],
                    'personality': ['冷静', '执着'],
                    'motivation': '查清星河钥匙的来源。',
                    'skills': ['推理', '行动力'],
                    'first_seen': '第一章 星河钥匙',
                    'first_chapter_index': 0,
                    'evidence': '林舟第一次发现星河钥匙。',
                    'confidence': 0.92,
                },
                {
                    'name': '沈秋',
                    'aliases': [],
                    'role_type': '同伴',
                    'summary': '协助主角破解线索的同伴。',
                    'description': '协助林舟破解线索。',
                    'appearance': '观察细致，表达直接。',
                    'traits': ['敏锐'],
                    'personality': ['敏锐'],
                    'motivation': '帮助林舟确认另一种推理方向。',
                    'skills': ['观察', '分析'],
                    'first_seen': '第二章 同行',
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
        self.assertEqual(data['characters'][0]['profile']['summary'], '追查星河钥匙的核心行动者。')
        self.assertEqual(data['characters'][0]['profile']['appearance'], '气质冷静，行动时克制而专注。')
        self.assertEqual(data['characters'][0]['profile']['personality'], ['冷静', '执着'])
        self.assertEqual(data['characters'][0]['profile']['motivation'], '查清星河钥匙的来源。')
        self.assertEqual(data['characters'][0]['profile']['skills'], ['推理', '行动力'])
        self.assertEqual(data['characters'][0]['profile']['first_seen'], '第一章 星河钥匙')
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
        read_character = read_payload['data']['characters'][0]
        self.assertEqual(read_character['profile']['summary'], '追查星河钥匙的核心行动者。')
        self.assertEqual(read_character['profile']['skills'], ['推理', '行动力'])

    def test_character_analysis_accepts_legacy_character_payload(self):
        class LegacyAIClient:
            def chat(self, messages, stream=False):
                return json.dumps({
                    'characters': [
                        {
                            'name': '旧角色',
                            'aliases': ['旧名'],
                            'role_type': '配角',
                            'description': '旧格式中的角色说明。',
                            'traits': ['谨慎'],
                            'first_chapter_index': 0,
                            'evidence': '旧角色在第一章出现。',
                            'confidence': 0.7,
                        }
                    ],
                    'relations': [],
                }, ensure_ascii=False)

        ai_routes.get_ai_client = lambda: LegacyAIClient()

        response = self.client.post(f'/api/ai/novels/{self.novel_id}/characters/analyze')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        character = payload['data']['characters'][0]
        self.assertEqual(character['name'], '旧角色')
        self.assertEqual(character['description'], '旧格式中的角色说明。')
        self.assertEqual(character['traits'], ['谨慎'])
        self.assertEqual(character['profile']['summary'], '旧格式中的角色说明。')
        self.assertEqual(character['profile']['personality'], ['谨慎'])
        self.assertEqual(character['profile']['first_seen'], '第 1 章')

    def test_existing_character_table_without_profile_json_is_migrated_and_serialized(self):
        legacy_database = os.path.join(self.tmpdir.name, 'legacy-profile-migration.db')
        novel_app.DATABASE = legacy_database

        conn = sqlite3.connect(legacy_database)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE novels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                description TEXT,
                file_path TEXT,
                category_id INTEGER,
                cover_path TEXT,
                status INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                color TEXT DEFAULT '#3498db',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE novel_tags (
                novel_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (novel_id, tag_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE novel_characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                novel_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                aliases_json TEXT DEFAULT '[]',
                role_type TEXT,
                description TEXT,
                traits_json TEXT DEFAULT '[]',
                first_chapter_index INTEGER,
                evidence TEXT,
                confidence REAL DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (novel_id, name)
            )
        ''')
        cursor.execute(
            'INSERT INTO novels (title, author, description, status) VALUES (?, ?, ?, ?)',
            ('旧库角色卡测试', '旧库作者', '旧库简介', 1)
        )
        novel_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO novel_characters (
                novel_id, name, aliases_json, role_type, description,
                traits_json, first_chapter_index, evidence, confidence, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            novel_id,
            '旧库角色',
            json.dumps(['旧称'], ensure_ascii=False),
            '配角',
            '旧库中的角色说明。',
            json.dumps(['可靠', '沉稳'], ensure_ascii=False),
            2,
            '旧库角色在第三章现身。',
            0.66,
            0,
        ))

        ai_routes.ensure_character_analysis_schema(cursor)
        ai_routes.ensure_character_analysis_schema(cursor)
        cursor.execute('PRAGMA table_info(novel_characters)')
        character_columns = {row[1] for row in cursor.fetchall()}
        conn.commit()
        conn.close()

        self.assertIn('profile_json', character_columns)

        response = self.client.get(f'/api/novels/{novel_id}/characters')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['data']['character_count'], 1)
        character = payload['data']['characters'][0]
        self.assertEqual(character['name'], '旧库角色')
        self.assertEqual(character['aliases'], ['旧称'])
        self.assertEqual(character['traits'], ['可靠', '沉稳'])
        self.assertEqual(character['profile']['summary'], '旧库中的角色说明。')
        self.assertEqual(character['profile']['appearance'], '')
        self.assertEqual(character['profile']['personality'], ['可靠', '沉稳'])
        self.assertEqual(character['profile']['motivation'], '')
        self.assertEqual(character['profile']['skills'], [])
        self.assertEqual(character['profile']['first_seen'], '第 3 章')
        self.assertEqual(character['profile']['card_evidence'], '旧库角色在第三章现身。')

    def test_character_library_schema_adds_manual_fields_idempotently(self):
        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()

        ai_routes.ensure_character_analysis_schema(cursor)
        ai_routes.ensure_character_analysis_schema(cursor)

        cursor.execute('PRAGMA table_info(novel_characters)')
        character_columns = {row[1] for row in cursor.fetchall()}
        cursor.execute('PRAGMA table_info(novel_character_relations)')
        relation_columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        self.assertIn('notes', character_columns)
        self.assertIn('is_manual', character_columns)
        self.assertIn('is_manual', relation_columns)

    def test_character_analysis_requires_existing_novel(self):
        response = self.client.post('/api/ai/novels/99999/characters/analyze')
        payload = response.get_json()

        self.assertEqual(response.status_code, 404)
        self.assertFalse(payload['success'])


if __name__ == '__main__':
    unittest.main()
