# 全新角色卡系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent global character library with editable character cards, searchable filters, AI completion, per-novel AI generation, and lightweight same-novel relationship editing.

**Architecture:** Keep the existing novel-level AI generation routes for compatibility, but add a focused `character_routes.py` module for global character CRUD, relation editing, and single-card AI completion. Add independent frontend assets `static/js/characters.js` and `static/css/characters.css` so the new role-card system does not further inflate `novels.js` or make the novel-detail Tab remain the primary product surface.

**Tech Stack:** Python 3, Flask, SQLite, native JavaScript, CSS, Node static checks, Python `unittest`.

---

## Spec

Design document: `docs/superpowers/specs/2026-05-04-character-library-system-design.md`

## Scope Check

This plan implements one coherent first release of the new role-card system. Backend CRUD, frontend library UI, AI completion, and novel-detail entry points are coupled by the same character-card model and should ship together. Features explicitly out of scope remain excluded: cross-book merge, avatars, import/export, timeline, chapter evidence management, and bulk character operations.

## File Structure

- Modify: `app.py`
  - Register `character_routes.py`.
  - Keep `app.py` below the existing line-count threshold.
- Modify: `ai_routes.py`
  - Extend character schema for `notes`, `is_manual`, and relation `is_manual`.
  - Update novel-level AI generation to preserve manual notes and manual relations.
- Create: `character_routes.py`
  - Own global `/api/characters` routes.
  - Own `/api/characters/<id>/relations` and `/api/character-relations/<id>` routes.
  - Own `/api/characters/<id>/ai-complete`.
  - Contain character serializers and normalizers that are used by these routes.
- Modify: `templates/index.html`
  - Add left-nav "角色库".
  - Add `view-characters`.
  - Add role-card drawer/edit form markup.
  - Add "打开角色库查看全部" in novel detail character Tab.
  - Load `characters.css` through `style.css` and `characters.js` before `app.js`.
- Create: `static/js/characters.js`
  - Own character-library frontend state, filters, cards, drawer, CRUD, AI completion, and relation editing.
- Create: `static/css/characters.css`
  - Own role-card library layout, cards, drawer, and relation-editing styles.
- Modify: `static/css/style.css`
  - Import `characters.css`.
- Modify: `static/js/app.js`
  - Initialize/load character library when entering `characters` view.
  - Preserve existing novel-list behavior and top filter toolbar behavior.
- Modify: `static/js/core.js`
  - Add `state.characters` or keep a dedicated `characterState` in `characters.js`; only touch `core.js` if shared app state is needed.
- Modify: `static/js/novels.js`
  - Add novel-detail action to open global character library filtered by current novel.
  - Keep existing character Tab data loading.
- Modify: `tests/app_structure.test.py`
  - Add new public route expectations.
  - Add `character_routes.py` to comment/docstring readability checks.
- Create: `tests/character_library.test.py`
  - Backend tests for CRUD, filtering, relation editing, AI completion, and compatibility.
- Create: `tests/character-library-ui.test.js`
  - Static frontend tests for navigation, library view, drawer, API calls, and CSS.
- Modify: `tests/character_analysis.test.py`
  - Add checks for schema migration and novel-level AI preserving manual notes/relations.
- Modify: `tests/character-analysis-ui.test.js`
  - Add novel-detail "open character library" entry check.

## Shared Data Contracts

Character list item returned by `GET /api/characters`:

```json
{
  "id": 1,
  "novel_id": 10,
  "novel_title": "示例小说",
  "name": "林舟",
  "aliases": ["小舟"],
  "role_type": "主角",
  "description": "负责追查星河钥匙的核心人物。",
  "traits": ["冷静", "执着"],
  "profile": {
    "summary": "追查星河钥匙的核心行动者。",
    "appearance": "气质冷静，行动时克制而专注。",
    "personality": ["冷静", "执着"],
    "motivation": "查清星河钥匙的来源。",
    "skills": ["推理", "行动力"],
    "tags": ["核心角色"]
  },
  "notes": "用户备注",
  "confidence": 0.92,
  "is_manual": 1,
  "updated_at": "2026-05-04 12:00:00"
}
```

Character detail returned by `GET /api/characters/<id>` adds:

```json
{
  "relations": [
    {
      "id": 3,
      "source_character_id": 1,
      "target_character_id": 2,
      "target_name": "沈秋",
      "relation_type": "同盟",
      "description": "两人共同追查线索。",
      "confidence": 0.84,
      "is_manual": 1
    }
  ]
}
```

## Task 1: Backend Route Map And Schema Tests

**Files:**
- Modify: `tests/app_structure.test.py`
- Modify: `tests/character_analysis.test.py`
- Create: `tests/character_library.test.py`

- [ ] **Step 1: Add route map expectations**

In `tests/app_structure.test.py`, add these expected routes in sorted position inside `EXPECTED_ROUTES`:

```python
    ('/api/character-relations/<int:relation_id>', 'DELETE'),
    ('/api/character-relations/<int:relation_id>', 'PUT'),
    ('/api/characters', 'GET'),
    ('/api/characters', 'POST'),
    ('/api/characters/<int:character_id>', 'DELETE'),
    ('/api/characters/<int:character_id>', 'GET'),
    ('/api/characters/<int:character_id>', 'PUT'),
    ('/api/characters/<int:character_id>/ai-complete', 'POST'),
    ('/api/characters/<int:character_id>/relations', 'POST'),
```

Also add `character_routes.py` to the `python_files` list in `test_python_comments_and_docstrings_are_readable`.

- [ ] **Step 2: Add schema migration test**

In `tests/character_analysis.test.py`, add a test that verifies existing character and relation tables gain `notes`, `is_manual`, and relation `is_manual`.

```python
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
```

- [ ] **Step 3: Create failing backend route tests**

Create `tests/character_library.test.py` with this baseline test module:

```python
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as novel_app
import character_routes


class FakeAIClient:
    def chat(self, messages, stream=False):
        return json.dumps({
            'summary': '负责追查星河钥匙的核心行动者。',
            'description': '林舟负责追查星河钥匙。',
            'appearance': '气质冷静。',
            'personality': ['冷静', '执着'],
            'motivation': '查清星河钥匙。',
            'skills': ['推理'],
            'tags': ['核心角色']
        }, ensure_ascii=False)


class CharacterLibraryTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        self.original_get_ai_client = character_routes.get_ai_client
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.init_db()
        character_routes.get_ai_client = lambda: FakeAIClient()
        self.client = novel_app.app.test_client()

        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO novels (title, author, description, file_path, status) VALUES (?, ?, ?, ?, ?)',
            ('角色库测试', '测试作者', '星河钥匙相关故事。', str(Path(self.tmpdir.name) / 'book.txt'), 1)
        )
        self.novel_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO novels (title, author, description, status) VALUES (?, ?, ?, ?)',
            ('另一本小说', '测试作者', '用于跨书关系校验。', 1)
        )
        self.other_novel_id = cursor.lastrowid
        conn.commit()
        conn.close()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        character_routes.get_ai_client = self.original_get_ai_client
        self.tmpdir.cleanup()

    def create_character(self, name='林舟', novel_id=None, role_type='主角'):
        response = self.client.post('/api/characters', json={
            'novel_id': novel_id or self.novel_id,
            'name': name,
            'aliases': ['小舟'] if name == '林舟' else [],
            'role_type': role_type,
            'description': f'{name}的角色说明。',
            'traits': ['冷静'],
            'profile': {
                'summary': f'{name}的角色定位。',
                'appearance': '气质冷静。',
                'personality': ['冷静'],
                'motivation': '查清真相。',
                'skills': ['推理'],
                'tags': ['核心角色']
            },
            'notes': '手动备注'
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['success'])
        return payload['data']

    def test_character_crud_and_filters(self):
        created = self.create_character()
        self.assertEqual(created['name'], '林舟')
        self.assertEqual(created['novel_id'], self.novel_id)
        self.assertEqual(created['notes'], '手动备注')
        self.assertEqual(created['is_manual'], 1)

        list_response = self.client.get('/api/characters?keyword=林舟&role_type=主角&tag=核心角色')
        list_payload = list_response.get_json()
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(list_payload['success'])
        self.assertEqual(list_payload['data']['total'], 1)
        self.assertEqual(list_payload['data']['items'][0]['novel_title'], '角色库测试')

        detail_response = self.client.get(f"/api/characters/{created['id']}")
        detail_payload = detail_response.get_json()
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_payload['data']['profile']['skills'], ['推理'])

        update_response = self.client.put(f"/api/characters/{created['id']}", json={
            'name': '林舟',
            'aliases': ['小舟', '林调查员'],
            'role_type': '主角',
            'description': '更新后的角色说明。',
            'traits': ['冷静', '执着'],
            'profile': {
                'summary': '更新后的定位。',
                'appearance': '克制而专注。',
                'personality': ['冷静', '执着'],
                'motivation': '确认钥匙来源。',
                'skills': ['推理', '行动力'],
                'tags': ['核心角色', '调查者']
            },
            'notes': '更新后的备注'
        })
        update_payload = update_response.get_json()
        self.assertEqual(update_response.status_code, 200)
        self.assertTrue(update_payload['success'])
        self.assertEqual(update_payload['data']['aliases'], ['小舟', '林调查员'])
        self.assertEqual(update_payload['data']['notes'], '更新后的备注')

        delete_response = self.client.delete(f"/api/characters/{created['id']}")
        delete_payload = delete_response.get_json()
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_payload['success'])

    def test_relation_editing_rejects_cross_novel_targets(self):
        source = self.create_character('林舟', self.novel_id, '主角')
        target = self.create_character('沈秋', self.novel_id, '同伴')
        other = self.create_character('异书角色', self.other_novel_id, '配角')

        create_response = self.client.post(f"/api/characters/{source['id']}/relations", json={
            'target_character_id': target['id'],
            'relation_type': '同盟',
            'description': '共同追查线索。'
        })
        create_payload = create_response.get_json()
        self.assertEqual(create_response.status_code, 200)
        self.assertTrue(create_payload['success'])
        self.assertEqual(create_payload['data']['relation_type'], '同盟')
        self.assertEqual(create_payload['data']['is_manual'], 1)

        cross_response = self.client.post(f"/api/characters/{source['id']}/relations", json={
            'target_character_id': other['id'],
            'relation_type': '误连',
            'description': '跨书关系不允许。'
        })
        self.assertEqual(cross_response.status_code, 400)

        update_response = self.client.put(f"/api/character-relations/{create_payload['data']['id']}", json={
            'relation_type': '搭档',
            'description': '更新后的关系说明。'
        })
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.get_json()['data']['relation_type'], '搭档')

        delete_response = self.client.delete(f"/api/character-relations/{create_payload['data']['id']}")
        self.assertEqual(delete_response.status_code, 200)

    def test_ai_complete_fills_empty_profile_fields_without_overwriting_notes(self):
        created = self.create_character()
        update_response = self.client.put(f"/api/characters/{created['id']}", json={
            'name': '林舟',
            'aliases': ['小舟'],
            'role_type': '主角',
            'description': '',
            'traits': [],
            'profile': {'summary': '', 'tags': []},
            'notes': '必须保留的手动备注'
        })
        self.assertEqual(update_response.status_code, 200)

        response = self.client.post(f"/api/characters/{created['id']}/ai-complete", json={})
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['data']['profile']['summary'], '负责追查星河钥匙的核心行动者。')
        self.assertEqual(payload['data']['profile']['skills'], ['推理'])
        self.assertEqual(payload['data']['notes'], '必须保留的手动备注')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 4: Run tests to verify RED**

Run:

```powershell
python tests/app_structure.test.py
python tests/character_analysis.test.py
python tests/character_library.test.py
```

Expected:

- `tests/app_structure.test.py` fails because new routes and `character_routes.py` do not exist.
- `tests/character_analysis.test.py` fails because manual schema fields do not exist.
- `tests/character_library.test.py` fails importing `character_routes`.

- [ ] **Step 5: Commit failing backend tests**

Run:

```powershell
git add tests/app_structure.test.py tests/character_analysis.test.py tests/character_library.test.py
git commit -m "test: cover character library backend"
```

Expected: commit succeeds with test-only changes.

## Task 2: Backend Schema, Serialization, And CRUD Routes

**Files:**
- Modify: `app.py`
- Modify: `ai_routes.py`
- Create: `character_routes.py`
- Modify: `tests/app_structure.test.py`
- Test: `tests/character_library.test.py`
- Test: `tests/character_analysis.test.py`

- [ ] **Step 1: Add manual schema fields**

In `ai_routes.ensure_character_analysis_schema`, after the existing `profile_json` migration, add idempotent migrations:

```python
    if 'notes' not in character_columns:
        cursor.execute("ALTER TABLE novel_characters ADD COLUMN notes TEXT DEFAULT ''")
    if 'is_manual' not in character_columns:
        cursor.execute("ALTER TABLE novel_characters ADD COLUMN is_manual INTEGER DEFAULT 0")
```

After creating `novel_character_relations`, add:

```python
    cursor.execute('PRAGMA table_info(novel_character_relations)')
    relation_columns = {row[1] for row in cursor.fetchall()}
    if 'is_manual' not in relation_columns:
        cursor.execute('ALTER TABLE novel_character_relations ADD COLUMN is_manual INTEGER DEFAULT 0')
```

- [ ] **Step 2: Create `character_routes.py` with route registration**

Create `character_routes.py` with these top-level imports and helpers:

```python
"""Character library routes."""
import json
import re
import sqlite3
import textwrap

from flask import jsonify, request

from ai_client import AIConfig, get_ai_client


def parse_json_list(value):
    if not value:
        return []
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def parse_json_dict(value):
    if not value:
        return {}
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def normalize_short_text(value, max_length=160):
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    return text[:max_length].strip()


def normalize_string_list(value, *, max_items=8, max_length=24):
    if isinstance(value, str):
        candidates = re.split(r'[,，、/\n]+', value)
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []

    normalized = []
    seen = set()
    for item in candidates:
        text = normalize_short_text(item, max_length=max_length)
        text = re.sub(r'^[#\s\-\*\.]+|[#\s\-\*\.]+$', '', text).strip()
        if len(text) < 1:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
        if len(normalized) >= max_items:
            break
    return normalized


def normalize_profile(value):
    profile = value if isinstance(value, dict) else {}
    return {
        'summary': normalize_short_text(profile.get('summary'), max_length=120),
        'appearance': normalize_short_text(profile.get('appearance'), max_length=180),
        'personality': normalize_string_list(profile.get('personality'), max_items=8, max_length=18),
        'motivation': normalize_short_text(profile.get('motivation'), max_length=180),
        'skills': normalize_string_list(profile.get('skills'), max_items=8, max_length=18),
        'tags': normalize_string_list(profile.get('tags'), max_items=12, max_length=20),
    }
```

- [ ] **Step 3: Add serializers to `character_routes.py`**

Add:

```python
def build_profile_from_row(item):
    profile = parse_json_dict(item.pop('profile_json', '{}'))
    traits = item.get('traits') or []
    if not profile:
        profile = {}
    return {
        'summary': normalize_short_text(profile.get('summary') or item.get('description') or '', max_length=120),
        'appearance': normalize_short_text(profile.get('appearance'), max_length=180),
        'personality': normalize_string_list(profile.get('personality') or traits, max_items=8, max_length=18),
        'motivation': normalize_short_text(profile.get('motivation'), max_length=180),
        'skills': normalize_string_list(profile.get('skills'), max_items=8, max_length=18),
        'tags': normalize_string_list(profile.get('tags'), max_items=12, max_length=20),
    }


def serialize_character_row(row):
    item = dict(row)
    item['aliases'] = parse_json_list(item.pop('aliases_json', '[]'))
    item['traits'] = parse_json_list(item.pop('traits_json', '[]'))
    item['profile'] = build_profile_from_row(item)
    item['notes'] = item.get('notes') or ''
    item['is_manual'] = int(item.get('is_manual') or 0)
    return item


def serialize_relation_row(row, *, perspective_character_id=None):
    item = dict(row)
    source_id = item.get('source_character_id')
    target_id = item.get('target_character_id')
    if perspective_character_id and source_id == perspective_character_id:
        item['other_character_id'] = target_id
        item['other_name'] = item.get('target_name')
    elif perspective_character_id and target_id == perspective_character_id:
        item['other_character_id'] = source_id
        item['other_name'] = item.get('source_name')
    item['is_manual'] = int(item.get('is_manual') or 0)
    return item
```

- [ ] **Step 4: Implement CRUD route registration**

Add `register_character_routes(app, *, get_db, resolve_novel_file_path, is_text_readable_file, detect_encoding)` and implement:

```python
def register_character_routes(app, *, get_db, resolve_novel_file_path, is_text_readable_file, detect_encoding):
    def get_novel_context(cursor, novel_id):
        cursor.execute('SELECT * FROM novels WHERE id = ?', (novel_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetch_character(cursor, character_id):
        cursor.execute('''
            SELECT ch.*, n.title AS novel_title
            FROM novel_characters ch
            JOIN novels n ON ch.novel_id = n.id
            WHERE ch.id = ?
        ''', (character_id,))
        row = cursor.fetchone()
        return serialize_character_row(row) if row else None

    def collect_character_payload(data, *, require_novel=True):
        data = data or {}
        try:
            novel_id = int(data.get('novel_id')) if data.get('novel_id') not in (None, '') else None
        except (TypeError, ValueError):
            novel_id = None
        name = normalize_short_text(data.get('name'), max_length=32)
        if require_novel and not novel_id:
            return None, '请选择所属小说'
        if not name:
            return None, '请填写角色名'
        profile = normalize_profile(data.get('profile'))
        return {
            'novel_id': novel_id,
            'name': name,
            'aliases': normalize_string_list(data.get('aliases'), max_items=6, max_length=24),
            'role_type': normalize_short_text(data.get('role_type') or '未知', max_length=32),
            'description': normalize_short_text(data.get('description'), max_length=260),
            'traits': normalize_string_list(data.get('traits') or profile.get('personality'), max_items=8, max_length=18),
            'profile': profile,
            'notes': normalize_short_text(data.get('notes'), max_length=600),
        }, None
```

Then add route handlers:

```python
    @app.route('/api/characters', methods=['GET'])
    def list_characters():
        keyword = normalize_short_text(request.args.get('keyword'), max_length=80)
        novel_id = request.args.get('novel_id')
        role_type = normalize_short_text(request.args.get('role_type'), max_length=32)
        tag = normalize_short_text(request.args.get('tag'), max_length=32)
        sort = request.args.get('sort') or 'updated_desc'

        where = []
        params = []
        if keyword:
            where.append('''(
                ch.name LIKE ? OR ch.aliases_json LIKE ? OR ch.description LIKE ?
                OR ch.profile_json LIKE ? OR ch.notes LIKE ?
            )''')
            like = f'%{keyword}%'
            params.extend([like, like, like, like, like])
        if novel_id:
            where.append('ch.novel_id = ?')
            params.append(novel_id)
        if role_type:
            where.append('ch.role_type = ?')
            params.append(role_type)
        if tag:
            where.append('ch.profile_json LIKE ?')
            params.append(f'%"{tag}"%')

        order_by = {
            'name': 'ch.name COLLATE NOCASE ASC',
            'novel': 'n.title COLLATE NOCASE ASC, ch.name COLLATE NOCASE ASC',
            'role': 'ch.role_type COLLATE NOCASE ASC, ch.name COLLATE NOCASE ASC',
            'updated_asc': 'ch.updated_at ASC, ch.id ASC',
        }.get(sort, 'ch.updated_at DESC, ch.id DESC')

        sql_where = f"WHERE {' AND '.join(where)}" if where else ''
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT ch.*, n.title AS novel_title
            FROM novel_characters ch
            JOIN novels n ON ch.novel_id = n.id
            {sql_where}
            ORDER BY {order_by}
        ''', params)
        items = [serialize_character_row(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'data': {'items': items, 'total': len(items)}})
```

In the same `register_character_routes` function, add the CRUD handlers:

```python
    @app.route('/api/characters', methods=['POST'])
    def create_character():
        payload, error = collect_character_payload(request.get_json(silent=True), require_novel=True)
        if error:
            return jsonify({'success': False, 'message': error}), 400

        conn = get_db()
        cursor = conn.cursor()
        try:
            if not get_novel_context(cursor, payload['novel_id']):
                return jsonify({'success': False, 'message': '所属小说不存在'}), 400
            cursor.execute('''
                INSERT INTO novel_characters (
                    novel_id, name, aliases_json, role_type, description,
                    traits_json, first_chapter_index, evidence, confidence,
                    profile_json, notes, is_manual, sort_order, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, '', 0, ?, ?, 1, 0, CURRENT_TIMESTAMP)
            ''', (
                payload['novel_id'],
                payload['name'],
                json.dumps(payload['aliases'], ensure_ascii=False),
                payload['role_type'],
                payload['description'],
                json.dumps(payload['traits'], ensure_ascii=False),
                json.dumps(payload['profile'], ensure_ascii=False),
                payload['notes'],
            ))
            character_id = cursor.lastrowid
            conn.commit()
            character = fetch_character(cursor, character_id)
            return jsonify({'success': True, 'data': character})
        except sqlite3.IntegrityError:
            conn.rollback()
            return jsonify({'success': False, 'message': '同一本小说中已存在同名角色'}), 400
        except Exception as exc:
            conn.rollback()
            return jsonify({'success': False, 'message': str(exc)}), 500
        finally:
            conn.close()

    @app.route('/api/characters/<int:character_id>', methods=['GET'])
    def get_character(character_id):
        conn = get_db()
        cursor = conn.cursor()
        character = fetch_character(cursor, character_id)
        conn.close()
        if not character:
            return jsonify({'success': False, 'message': '角色不存在'}), 404
        character['relations'] = []
        return jsonify({'success': True, 'data': character})

    @app.route('/api/characters/<int:character_id>', methods=['PUT'])
    def update_character(character_id):
        conn = get_db()
        cursor = conn.cursor()
        existing = fetch_character(cursor, character_id)
        if not existing:
            conn.close()
            return jsonify({'success': False, 'message': '角色不存在'}), 404

        payload, error = collect_character_payload(request.get_json(silent=True), require_novel=False)
        if error:
            conn.close()
            return jsonify({'success': False, 'message': error}), 400
        payload['novel_id'] = payload['novel_id'] or existing['novel_id']

        try:
            if not get_novel_context(cursor, payload['novel_id']):
                return jsonify({'success': False, 'message': '所属小说不存在'}), 400
            cursor.execute('''
                UPDATE novel_characters
                SET novel_id = ?, name = ?, aliases_json = ?, role_type = ?,
                    description = ?, traits_json = ?, profile_json = ?,
                    notes = ?, is_manual = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                payload['novel_id'],
                payload['name'],
                json.dumps(payload['aliases'], ensure_ascii=False),
                payload['role_type'],
                payload['description'],
                json.dumps(payload['traits'], ensure_ascii=False),
                json.dumps(payload['profile'], ensure_ascii=False),
                payload['notes'],
                character_id,
            ))
            conn.commit()
            updated = fetch_character(cursor, character_id)
            return jsonify({'success': True, 'data': updated})
        except sqlite3.IntegrityError:
            conn.rollback()
            return jsonify({'success': False, 'message': '同一本小说中已存在同名角色'}), 400
        except Exception as exc:
            conn.rollback()
            return jsonify({'success': False, 'message': str(exc)}), 500
        finally:
            conn.close()

    @app.route('/api/characters/<int:character_id>', methods=['DELETE'])
    def delete_character(character_id):
        conn = get_db()
        cursor = conn.cursor()
        existing = fetch_character(cursor, character_id)
        if not existing:
            conn.close()
            return jsonify({'success': False, 'message': '角色不存在'}), 404
        try:
            cursor.execute('''
                DELETE FROM novel_character_relations
                WHERE source_character_id = ? OR target_character_id = ?
            ''', (character_id, character_id))
            cursor.execute('DELETE FROM novel_characters WHERE id = ?', (character_id,))
            conn.commit()
            return jsonify({'success': True})
        except Exception as exc:
            conn.rollback()
            return jsonify({'success': False, 'message': str(exc)}), 500
        finally:
            conn.close()
```

- [ ] **Step 5: Register routes in `app.py`**

Near the existing route imports, add:

```python
from character_routes import register_character_routes
```

After `register_ai_routes(...)`, add:

```python
register_character_routes(
    app,
    get_db=get_db,
    resolve_novel_file_path=resolve_novel_file_path,
    is_text_readable_file=is_text_readable_file,
    detect_encoding=detect_encoding,
)
```

- [ ] **Step 6: Run tests to verify GREEN for CRUD**

Run:

```powershell
python tests/app_structure.test.py
python tests/character_analysis.test.py
python -m unittest tests.character_library.CharacterLibraryTest.test_character_crud_and_filters
python -m py_compile app.py ai_routes.py character_routes.py
```

Expected: `app_structure`, `character_analysis`, and `test_character_crud_and_filters` pass. Relation and AI-complete tests remain RED for Task 3 and Task 4.

- [ ] **Step 7: Commit backend CRUD implementation**

Run:

```powershell
git add app.py ai_routes.py character_routes.py tests/app_structure.test.py tests/character_analysis.test.py tests/character_library.test.py
git commit -m "feat: add character library backend"
```

Expected: commit succeeds with schema and CRUD routes.

## Task 3: Relationship Editing Routes

**Files:**
- Modify: `character_routes.py`
- Test: `tests/character_library.test.py`

- [ ] **Step 1: Confirm failing relation test**

Run:

```powershell
python -m unittest tests.character_library.CharacterLibraryTest.test_relation_editing_rejects_cross_novel_targets
```

Expected: FAIL because relation routes are not complete.

- [ ] **Step 2: Implement same-novel relation validation**

In `character_routes.py`, inside `register_character_routes`, add helpers:

```python
    def fetch_relation(cursor, relation_id):
        cursor.execute('''
            SELECT r.*,
                   sc.name AS source_name,
                   tc.name AS target_name
            FROM novel_character_relations r
            JOIN novel_characters sc ON r.source_character_id = sc.id
            JOIN novel_characters tc ON r.target_character_id = tc.id
            WHERE r.id = ?
        ''', (relation_id,))
        row = cursor.fetchone()
        return serialize_relation_row(row) if row else None

    def validate_same_novel_relation(cursor, source_character_id, target_character_id):
        cursor.execute('SELECT id, novel_id FROM novel_characters WHERE id IN (?, ?)', (
            source_character_id,
            target_character_id,
        ))
        rows = {row['id']: dict(row) for row in cursor.fetchall()}
        source = rows.get(source_character_id)
        target = rows.get(target_character_id)
        if not source or not target:
            return None, None, '角色不存在'
        if source['novel_id'] != target['novel_id']:
            return None, None, '只能维护同一本小说内的角色关系'
        if source_character_id == target_character_id:
            return None, None, '不能关联角色自身'
        return source, target, None
```

- [ ] **Step 3: Implement relation routes**

Add:

```python
    @app.route('/api/characters/<int:character_id>/relations', methods=['POST'])
    def create_character_relation(character_id):
        data = request.get_json(silent=True) or {}
        try:
            target_character_id = int(data.get('target_character_id'))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': '请选择目标角色'}), 400
        relation_type = normalize_short_text(data.get('relation_type') or '相关', max_length=32)
        description = normalize_short_text(data.get('description'), max_length=260)

        conn = get_db()
        cursor = conn.cursor()
        try:
            source, target, error = validate_same_novel_relation(cursor, character_id, target_character_id)
            if error:
                return jsonify({'success': False, 'message': error}), 400
            cursor.execute('''
                INSERT INTO novel_character_relations (
                    novel_id, source_character_id, target_character_id,
                    relation_type, description, evidence, confidence, is_manual, sort_order, updated_at
                ) VALUES (?, ?, ?, ?, ?, '', 0, 1, 0, CURRENT_TIMESTAMP)
            ''', (
                source['novel_id'],
                character_id,
                target_character_id,
                relation_type,
                description,
            ))
            relation_id = cursor.lastrowid
            conn.commit()
            relation = fetch_relation(cursor, relation_id)
            return jsonify({'success': True, 'data': relation})
        except Exception as exc:
            conn.rollback()
            return jsonify({'success': False, 'message': str(exc)}), 500
        finally:
            conn.close()
```

Add the update and delete handlers:

```python
    @app.route('/api/character-relations/<int:relation_id>', methods=['PUT'])
    def update_character_relation(relation_id):
        data = request.get_json(silent=True) or {}
        relation_type = normalize_short_text(data.get('relation_type') or '相关', max_length=32)
        description = normalize_short_text(data.get('description'), max_length=260)

        conn = get_db()
        cursor = conn.cursor()
        relation = fetch_relation(cursor, relation_id)
        if not relation:
            conn.close()
            return jsonify({'success': False, 'message': '关系不存在'}), 404
        try:
            cursor.execute('''
                UPDATE novel_character_relations
                SET relation_type = ?, description = ?, is_manual = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (relation_type, description, relation_id))
            conn.commit()
            updated = fetch_relation(cursor, relation_id)
            return jsonify({'success': True, 'data': updated})
        except Exception as exc:
            conn.rollback()
            return jsonify({'success': False, 'message': str(exc)}), 500
        finally:
            conn.close()

    @app.route('/api/character-relations/<int:relation_id>', methods=['DELETE'])
    def delete_character_relation(relation_id):
        conn = get_db()
        cursor = conn.cursor()
        relation = fetch_relation(cursor, relation_id)
        if not relation:
            conn.close()
            return jsonify({'success': False, 'message': '关系不存在'}), 404
        try:
            cursor.execute('DELETE FROM novel_character_relations WHERE id = ?', (relation_id,))
            conn.commit()
            return jsonify({'success': True})
        except Exception as exc:
            conn.rollback()
            return jsonify({'success': False, 'message': str(exc)}), 500
        finally:
            conn.close()
```

- [ ] **Step 4: Include relations in character detail**

Replace `GET /api/characters/<id>` from Task 2 with this version:

```python
    @app.route('/api/characters/<int:character_id>', methods=['GET'])
    def get_character(character_id):
        conn = get_db()
        cursor = conn.cursor()
        data = fetch_character(cursor, character_id)
        if not data:
            conn.close()
            return jsonify({'success': False, 'message': '角色不存在'}), 404
        cursor.execute('''
            SELECT r.*,
                   sc.name AS source_name,
                   tc.name AS target_name
            FROM novel_character_relations r
            JOIN novel_characters sc ON r.source_character_id = sc.id
            JOIN novel_characters tc ON r.target_character_id = tc.id
            WHERE r.source_character_id = ? OR r.target_character_id = ?
            ORDER BY r.sort_order ASC, r.id ASC
        ''', (character_id, character_id))
        data['relations'] = [
            serialize_relation_row(row, perspective_character_id=character_id)
            for row in cursor.fetchall()
        ]
        conn.close()
        return jsonify({'success': True, 'data': data})
```

- [ ] **Step 5: Run relation tests**

Run:

```powershell
python -m unittest tests.character_library.CharacterLibraryTest.test_relation_editing_rejects_cross_novel_targets
python -m unittest tests.character_library.CharacterLibraryTest.test_character_crud_and_filters
```

Expected: relation and CRUD tests pass. The AI-complete test remains RED for Task 4.

- [ ] **Step 6: Commit relation implementation**

Run:

```powershell
git add character_routes.py tests/character_library.test.py
git commit -m "feat: add character relation editing"
```

Expected: commit succeeds.

## Task 4: Single Character AI Completion

**Files:**
- Modify: `character_routes.py`
- Test: `tests/character_library.test.py`

- [ ] **Step 1: Confirm failing AI-complete test**

Run:

```powershell
python -m unittest tests.character_library.CharacterLibraryTest.test_ai_complete_fills_empty_profile_fields_without_overwriting_notes
```

Expected: FAIL because `/api/characters/<id>/ai-complete` is not implemented.

- [ ] **Step 2: Add AI completion helpers**

In `character_routes.py`, add helpers near the serializers:

```python
def extract_json_object(text):
    cleaned = (text or '').strip()
    if not cleaned:
        raise ValueError('AI 未返回内容')
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```$', '', cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            return json.loads(match.group(0))
        raise ValueError('AI 返回格式无法解析，请稍后重试')
```

Inside `register_character_routes`, add:

```python
    def extract_text_excerpt(file_path, max_chars=8000):
        if not file_path:
            return ''
        actual_path, _ = resolve_novel_file_path(file_path)
        if not actual_path or not is_text_readable_file(actual_path):
            return ''
        try:
            encoding = detect_encoding(actual_path)
            with open(actual_path, 'r', encoding=encoding, errors='ignore') as file_obj:
                return file_obj.read(max_chars).strip()
        except Exception:
            return ''

    def build_character_completion_messages(character, novel, content_excerpt):
        profile = character.get('profile') or {}
        context = [
            f'小说标题：{novel.get("title") or "未提供"}',
            f'作者：{novel.get("author") or "未提供"}',
            f'小说简介：{novel.get("description") or "无"}',
            f'角色名：{character.get("name")}',
            f'已有别名：{"、".join(character.get("aliases") or []) or "无"}',
            f'已有身份：{character.get("role_type") or "未知"}',
            f'已有简介：{character.get("description") or "无"}',
            f'已有备注：{character.get("notes") or "无"}',
            f'已有角色卡：{json.dumps(profile, ensure_ascii=False)}',
        ]
        if content_excerpt:
            context.append(f'正文片段：\n{content_excerpt[:8000]}')
        user_prompt = '\n\n'.join(context) + textwrap.dedent("""

        请只基于以上信息补全这张角色卡的空字段。
        只输出 JSON 对象，不要输出 Markdown。
        JSON 格式：
        {"summary":"一句话角色定位","description":"角色说明","appearance":"外貌或气质","personality":["性格标签"],"motivation":"明确动机","skills":["能力或特长"],"tags":["角色标签"]}
        不要修改角色名、所属小说和用户备注。信息不足时返回空字符串或空数组。
        """)
        return [
            {'role': 'system', 'content': '你是严谨的小说角色卡整理助手，只根据文本证据补全角色档案。'},
            {'role': 'user', 'content': user_prompt.strip()},
        ]
```

- [ ] **Step 3: Implement AI completion route**

Add:

```python
    @app.route('/api/characters/<int:character_id>/ai-complete', methods=['POST'])
    def complete_character_with_ai(character_id):
        conn = get_db()
        cursor = conn.cursor()
        character = fetch_character(cursor, character_id)
        if not character:
            conn.close()
            return jsonify({'success': False, 'message': '角色不存在'}), 404
        novel = get_novel_context(cursor, character['novel_id'])
        conn.close()

        client = get_ai_client()
        if not client:
            return jsonify({'success': False, 'message': '请先在 AI 配置中激活可用模型'}), 400

        content_excerpt = extract_text_excerpt(novel.get('file_path'), max_chars=8000) if novel else ''
        messages = build_character_completion_messages(character, novel or {}, content_excerpt)

        try:
            response_text = client.chat(messages, stream=False)
            response_data = extract_json_object(response_text)
            completion_profile = normalize_profile(response_data)
            description = normalize_short_text(response_data.get('description'), max_length=260)

            merged_profile = character.get('profile') or {}
            for key, value in completion_profile.items():
                if key == 'tags':
                    existing = merged_profile.get('tags') if isinstance(merged_profile.get('tags'), list) else []
                    merged_profile[key] = existing or value
                elif not merged_profile.get(key):
                    merged_profile[key] = value

            merged_description = character.get('description') or description
            merged_traits = character.get('traits') or completion_profile.get('personality') or []

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE novel_characters
                SET description = ?, traits_json = ?, profile_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                merged_description,
                json.dumps(merged_traits, ensure_ascii=False),
                json.dumps(merged_profile, ensure_ascii=False),
                character_id,
            ))
            conn.commit()
            updated = fetch_character(cursor, character_id)
            conn.close()
            return jsonify({'success': True, 'data': updated})
        except (ValueError, RuntimeError) as exc:
            return jsonify({'success': False, 'message': str(exc)}), 422
        except Exception as exc:
            return jsonify({'success': False, 'message': str(exc)}), 500
```

- [ ] **Step 4: Run AI-complete tests**

Run:

```powershell
python -m unittest tests.character_library.CharacterLibraryTest.test_ai_complete_fills_empty_profile_fields_without_overwriting_notes
python tests/character_library.test.py
```

Expected: all character library tests pass.

- [ ] **Step 5: Commit AI completion implementation**

Run:

```powershell
git add character_routes.py tests/character_library.test.py
git commit -m "feat: add character card ai completion"
```

Expected: commit succeeds.

## Task 5: Novel-Level AI Conflict Preservation

**Files:**
- Modify: `ai_routes.py`
- Modify: `tests/character_analysis.test.py`

- [ ] **Step 1: Add failing test for manual preservation**

In `tests/character_analysis.test.py`, add:

```python
    def test_ai_generation_preserves_manual_character_notes_and_relations(self):
        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        ai_routes.ensure_character_analysis_schema(cursor)
        cursor.execute('''
            INSERT INTO novel_characters (
                novel_id, name, aliases_json, role_type, description,
                traits_json, first_chapter_index, evidence, confidence,
                profile_json, notes, is_manual, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.novel_id,
            '林舟',
            json.dumps(['手动别名'], ensure_ascii=False),
            '主角',
            '手动维护的角色简介。',
            json.dumps(['谨慎'], ensure_ascii=False),
            0,
            '手动证据',
            0.5,
            json.dumps({'summary': '手动定位', 'tags': ['手动标签']}, ensure_ascii=False),
            '保留备注',
            1,
            0,
        ))
        source_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO novel_characters (
                novel_id, name, aliases_json, role_type, description,
                traits_json, profile_json, notes, is_manual, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.novel_id,
            '沈秋',
            '[]',
            '同伴',
            '手动维护的同伴简介。',
            json.dumps(['敏锐'], ensure_ascii=False),
            json.dumps({'summary': '同伴定位'}, ensure_ascii=False),
            '',
            1,
            1,
        ))
        target_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO novel_character_relations (
                novel_id, source_character_id, target_character_id,
                relation_type, description, evidence, confidence, is_manual, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.novel_id,
            source_id,
            target_id,
            '手动关系',
            '手动关系说明',
            '手动关系证据',
            1,
            1,
            0,
        ))
        conn.commit()
        conn.close()

        response = self.client.post(f'/api/ai/novels/{self.novel_id}/characters/analyze')
        self.assertEqual(response.status_code, 200)

        read_response = self.client.get(f'/api/novels/{self.novel_id}/characters')
        read_payload = read_response.get_json()
        self.assertTrue(read_payload['success'])
        character = next(item for item in read_payload['data']['characters'] if item['name'] == '林舟')
        relation_descriptions = [relation['description'] for relation in read_payload['data']['relations']]

        self.assertEqual(character['notes'], '保留备注')
        self.assertEqual(character['is_manual'], 1)
        self.assertEqual(character['profile']['summary'], '手动定位')
        self.assertIn('手动关系说明', relation_descriptions)
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
python tests/character_analysis.test.py
```

Expected: FAIL because `replace_character_analysis` currently deletes all characters and relations for the novel.

- [ ] **Step 3: Update `replace_character_analysis`**

In `ai_routes.py`, replace `replace_character_analysis` with:

```python
    def replace_character_analysis(novel_id, characters, relations, *, model='', source_excerpt_chars=0):
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM novel_characters WHERE novel_id = ?', (novel_id,))
            existing_by_name = {row['name'].lower(): dict(row) for row in cursor.fetchall()}
            character_id_by_name = {}

            for index, character in enumerate(characters):
                key = character['name'].lower()
                existing = existing_by_name.get(key)
                ai_profile = character.get('profile') or {}
                ai_traits = character.get('traits') or []

                if existing:
                    is_manual = int(existing.get('is_manual') or 0)
                    existing_profile = parse_json_dict(existing.get('profile_json'))
                    existing_traits = parse_json_list(existing.get('traits_json'))
                    if is_manual:
                        merged_profile = dict(existing_profile)
                        for field, value in ai_profile.items():
                            if not merged_profile.get(field):
                                merged_profile[field] = value
                        aliases = parse_json_list(existing.get('aliases_json')) or character['aliases']
                        role_type = existing.get('role_type') or character['role_type']
                        description = existing.get('description') or character['description']
                        traits = existing_traits or ai_traits
                        notes = existing.get('notes') or ''
                        manual_flag = 1
                    else:
                        merged_profile = ai_profile
                        aliases = character['aliases']
                        role_type = character['role_type']
                        description = character['description']
                        traits = ai_traits
                        notes = existing.get('notes') or ''
                        manual_flag = 0

                    cursor.execute('''
                        UPDATE novel_characters
                        SET aliases_json = ?, role_type = ?, description = ?,
                            traits_json = ?, first_chapter_index = ?, evidence = ?,
                            confidence = ?, profile_json = ?, notes = ?,
                            is_manual = ?, sort_order = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        json.dumps(aliases, ensure_ascii=False),
                        role_type,
                        description,
                        json.dumps(traits, ensure_ascii=False),
                        character['first_chapter_index'],
                        character['evidence'],
                        character['confidence'],
                        json.dumps(merged_profile, ensure_ascii=False),
                        notes,
                        manual_flag,
                        index,
                        existing['id'],
                    ))
                    character_id_by_name[key] = existing['id']
                else:
                    cursor.execute('''
                        INSERT INTO novel_characters (
                            novel_id, name, aliases_json, role_type, description,
                            traits_json, first_chapter_index, evidence, confidence,
                            profile_json, notes, is_manual, sort_order
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 0, ?)
                    ''', (
                        novel_id,
                        character['name'],
                        json.dumps(character['aliases'], ensure_ascii=False),
                        character['role_type'],
                        character['description'],
                        json.dumps(ai_traits, ensure_ascii=False),
                        character['first_chapter_index'],
                        character['evidence'],
                        character['confidence'],
                        json.dumps(ai_profile, ensure_ascii=False),
                        index,
                    ))
                    character_id_by_name[key] = cursor.lastrowid

            cursor.execute('''
                DELETE FROM novel_character_relations
                WHERE novel_id = ? AND COALESCE(is_manual, 0) = 0
            ''', (novel_id,))

            saved_relation_count = 0
            for index, relation in enumerate(relations):
                source_id = character_id_by_name.get(relation['source_name'].lower())
                target_id = character_id_by_name.get(relation['target_name'].lower())
                if not source_id or not target_id:
                    continue

                cursor.execute('''
                    INSERT INTO novel_character_relations (
                        novel_id, source_character_id, target_character_id,
                        relation_type, description, evidence, confidence,
                        is_manual, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                ''', (
                    novel_id,
                    source_id,
                    target_id,
                    relation['relation_type'],
                    relation['description'],
                    relation['evidence'],
                    relation['confidence'],
                    index,
                ))
                saved_relation_count += 1

            cursor.execute('''
                INSERT INTO novel_character_analysis_runs (
                    novel_id, status, model, character_count, relation_count,
                    source_excerpt_chars, error_message, updated_at, finished_at
                ) VALUES (?, 'completed', ?, ?, ?, ?, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(novel_id) DO UPDATE SET
                    status = 'completed',
                    model = excluded.model,
                    character_count = excluded.character_count,
                    relation_count = excluded.relation_count,
                    source_excerpt_chars = excluded.source_excerpt_chars,
                    error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP,
                    finished_at = CURRENT_TIMESTAMP
            ''', (
                novel_id,
                model,
                len(characters),
                saved_relation_count,
                source_excerpt_chars,
            ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return serialize_character_analysis(novel_id)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python tests/character_analysis.test.py
python tests/character_library.test.py
```

Expected: both pass.

- [ ] **Step 5: Commit AI conflict preservation**

Run:

```powershell
git add ai_routes.py tests/character_analysis.test.py
git commit -m "feat: preserve manual character edits during ai generation"
```

Expected: commit succeeds.

## Task 6: Frontend Static Tests For Character Library

**Files:**
- Create: `tests/character-library-ui.test.js`
- Modify: `tests/character-analysis-ui.test.js`

- [ ] **Step 1: Create character library static UI test**

Create `tests/character-library-ui.test.js`:

```javascript
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const appJs = fs.readFileSync(path.join(root, 'static/js/app.js'), 'utf8');
const charactersJs = fs.readFileSync(path.join(root, 'static/js/characters.js'), 'utf8');
const styleCss = fs.readFileSync(path.join(root, 'static/css/style.css'), 'utf8');
const charactersCss = fs.readFileSync(path.join(root, 'static/css/characters.css'), 'utf8');

assert.match(template, /data-view="characters"/, 'sidebar should include character library nav');
assert.match(template, /id="view-characters"/, 'template should include character library view');
assert.match(template, /id="character-library-search"/, 'character library should include search input');
assert.match(template, /id="character-library-novel-filter"/, 'character library should include novel filter');
assert.match(template, /id="character-library-role-filter"/, 'character library should include role filter');
assert.match(template, /id="character-library-tag-filter"/, 'character library should include tag filter');
assert.match(template, /id="character-library-sort"/, 'character library should include sort control');
assert.match(template, /id="btn-character-create"/, 'character library should include create button');
assert.match(template, /id="btn-character-ai-generate"/, 'character library should include per-novel AI generation button');
assert.match(template, /id="character-library-grid"/, 'character library should include card grid');
assert.match(template, /id="character-drawer"/, 'character library should include detail drawer');
assert.match(template, /id="character-relation-list"/, 'character drawer should include relation list');

assert.match(styleCss, /characters\.css/, 'style entry should import character library css');
assert.match(template, /\/static\/js\/characters\.js/, 'template should load character library script');

assert.match(appJs, /loadCharacterLibrary\(\)/, 'app should load character library when switching views');
assert.match(charactersJs, /const characterState/, 'characters module should define character state');
assert.match(charactersJs, /async function loadCharacterLibrary/, 'characters module should load character library');
assert.match(charactersJs, /function renderCharacterFilters/, 'characters module should render filters');
assert.match(charactersJs, /function renderCharacterCards/, 'characters module should render cards');
assert.match(charactersJs, /\/api\/characters/, 'characters module should call character API');

assert.match(charactersCss, /\.character-library-shell/, 'character CSS should style page shell');
assert.match(charactersCss, /\.character-library-card/, 'character CSS should style cards');
assert.match(charactersCss, /\.character-drawer/, 'character CSS should style drawer');
assert.match(charactersCss, /\.character-relation-editor/, 'character CSS should style relation editor');

console.log('character library UI checks passed');
```

- [ ] **Step 2: Add novel-detail entry static test**

In `tests/character-analysis-ui.test.js`, add:

```javascript
assert.match(template, /id="btn-open-character-library"/, 'novel detail should link to full character library');
assert.match(novelsJs, /openCharacterLibraryForNovel/, 'novel detail should open character library filtered by novel');
```

- [ ] **Step 3: Run tests to verify RED**

Run:

```powershell
node tests/character-library-ui.test.js
node tests/character-analysis-ui.test.js
```

Expected:

- `character-library-ui` fails because files and DOM do not exist.
- `character-analysis-ui` fails because the novel-detail entry is missing.

- [ ] **Step 4: Commit failing frontend tests**

Run:

```powershell
git add tests/character-library-ui.test.js tests/character-analysis-ui.test.js
git commit -m "test: cover character library UI"
```

Expected: commit succeeds.

## Task 7: Frontend Character Library Shell

**Files:**
- Modify: `templates/index.html`
- Modify: `static/css/style.css`
- Create: `static/css/characters.css`
- Create: `static/js/characters.js`
- Modify: `static/js/app.js`
- Test: `tests/character-library-ui.test.js`

- [ ] **Step 1: Add sidebar nav and view markup**

In `templates/index.html`, add nav item after novel list:

```html
                <a href="#" class="nav-item" data-view="characters">
                    <i class="fas fa-address-card"></i>
                    <span>角色库</span>
                </a>
```

Add `view-characters` before category view:

```html
                <div class="view hidden" id="view-characters">
                    <section class="character-library-shell">
                        <div class="character-library-toolbar">
                            <div class="character-library-heading">
                                <span class="section-kicker">角色资料库</span>
                                <h2>角色库</h2>
                            </div>
                            <div class="character-library-actions">
                                <button class="btn btn-secondary" id="btn-character-ai-generate">
                                    <i class="fas fa-wand-magic-sparkles"></i>
                                    AI 生成该书角色卡
                                </button>
                                <button class="btn btn-primary" id="btn-character-create">
                                    <i class="fas fa-plus"></i>
                                    新建角色
                                </button>
                            </div>
                        </div>
                        <div class="character-library-filters">
                            <input type="text" id="character-library-search" placeholder="搜索角色名、别名、简介或备注">
                            <select id="character-library-novel-filter"></select>
                            <select id="character-library-role-filter">
                                <option value="">全部身份</option>
                                <option value="主角">主角</option>
                                <option value="反派">反派</option>
                                <option value="同伴">同伴</option>
                                <option value="配角">配角</option>
                                <option value="未知">未知</option>
                            </select>
                            <input type="text" id="character-library-tag-filter" placeholder="标签">
                            <select id="character-library-sort">
                                <option value="updated_desc">最近更新</option>
                                <option value="updated_asc">最早更新</option>
                                <option value="name">名称</option>
                                <option value="novel">所属小说</option>
                                <option value="role">身份</option>
                            </select>
                        </div>
                        <div class="character-library-grid" id="character-library-grid"></div>
                    </section>
                </div>
```

- [ ] **Step 2: Add character drawer markup**

Near existing modals/drawers, add:

```html
    <aside class="character-drawer" id="character-drawer" aria-hidden="true">
        <div class="character-drawer-panel">
            <div class="character-drawer-head">
                <div>
                    <span class="section-kicker" id="character-drawer-novel">未选择小说</span>
                    <h3 id="character-drawer-title">新建角色</h3>
                </div>
                <button class="btn-close" id="btn-character-drawer-close">&times;</button>
            </div>
            <div class="character-drawer-body">
                <input type="hidden" id="character-id">
                <label>所属小说</label>
                <select id="character-novel-id"></select>
                <label>角色名</label>
                <input type="text" id="character-name">
                <label>别名</label>
                <input type="text" id="character-aliases" placeholder="用顿号或逗号分隔">
                <label>身份</label>
                <input type="text" id="character-role-type">
                <label>简介</label>
                <textarea id="character-description" rows="3"></textarea>
                <label>性格/特征</label>
                <input type="text" id="character-traits" placeholder="用顿号或逗号分隔">
                <label>标签</label>
                <input type="text" id="character-tags" placeholder="用顿号或逗号分隔">
                <label>一句话定位</label>
                <input type="text" id="character-summary">
                <label>外貌/气质</label>
                <input type="text" id="character-appearance">
                <label>动机</label>
                <input type="text" id="character-motivation">
                <label>能力/特长</label>
                <input type="text" id="character-skills" placeholder="用顿号或逗号分隔">
                <label>备注</label>
                <textarea id="character-notes" rows="3"></textarea>
                <div class="character-relation-editor">
                    <div class="character-section-title">相关角色</div>
                    <div id="character-relation-list"></div>
                    <div class="character-relation-form">
                        <select id="character-relation-target"></select>
                        <input type="text" id="character-relation-type" placeholder="关系类型">
                        <input type="text" id="character-relation-description" placeholder="关系说明">
                        <button class="btn btn-secondary" id="btn-character-relation-save">保存关系</button>
                    </div>
                </div>
            </div>
            <div class="character-drawer-footer">
                <button class="btn btn-secondary" id="btn-character-ai-complete">AI 补全</button>
                <button class="btn btn-secondary" id="btn-character-delete">删除</button>
                <button class="btn btn-primary" id="btn-character-save">保存角色</button>
            </div>
        </div>
    </aside>
```

- [ ] **Step 3: Load assets**

In `static/css/style.css`, add before `overrides.css`:

```css
@import url('./characters.css');
```

In `templates/index.html`, load before `app.js`:

```html
    <script src="/static/js/characters.js"></script>
```

- [ ] **Step 4: Create `characters.css`**

Create `static/css/characters.css` with:

```css
.character-library-shell {
    display: grid;
    gap: 16px;
}

.character-library-toolbar,
.character-library-actions,
.character-library-filters {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.character-library-toolbar {
    justify-content: space-between;
}

.character-library-heading h2 {
    margin: 2px 0 0;
}

.character-library-filters input,
.character-library-filters select {
    min-height: 38px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    padding: 0 10px;
}

.character-library-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 12px;
}

.character-library-card {
    display: grid;
    gap: 8px;
    padding: 14px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    background: #ffffff;
    cursor: pointer;
}

.character-library-card h3 {
    margin: 0;
    font-size: 17px;
}

.character-library-card p {
    margin: 0;
    color: var(--text-secondary);
    line-height: 1.6;
}

.character-library-card-meta,
.character-library-card-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    color: var(--text-secondary);
    font-size: 12px;
}

.character-library-card-tags span {
    padding: 3px 8px;
    border-radius: 999px;
    background: #ecfeff;
    color: #0e7490;
}

.character-drawer {
    position: fixed;
    inset: 0;
    z-index: 1200;
    display: none;
    justify-content: flex-end;
    background: rgba(15, 23, 42, 0.28);
}

.character-drawer.active {
    display: flex;
}

.character-drawer-panel {
    width: min(560px, 100%);
    height: 100%;
    display: grid;
    grid-template-rows: auto 1fr auto;
    background: #ffffff;
    box-shadow: -20px 0 40px rgba(15, 23, 42, 0.18);
}

.character-drawer-head,
.character-drawer-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 16px;
    border-bottom: 1px solid var(--border-color);
}

.character-drawer-footer {
    border-top: 1px solid var(--border-color);
    border-bottom: 0;
}

.character-drawer-body {
    overflow: auto;
    display: grid;
    gap: 8px;
    padding: 16px;
}

.character-drawer-body input,
.character-drawer-body select,
.character-drawer-body textarea {
    width: 100%;
}

.character-section-title {
    margin-top: 12px;
    font-weight: 700;
}

.character-relation-editor {
    display: grid;
    gap: 10px;
}

.character-relation-form {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}

.character-relation-form button {
    grid-column: 1 / -1;
}
```

- [ ] **Step 5: Create `characters.js` shell**

Create `static/js/characters.js` with state and loading/rendering skeleton:

```javascript
const characterState = {
    items: [],
    activeCharacter: null,
    filters: {
        keyword: '',
        novelId: '',
        roleType: '',
        tag: '',
        sort: 'updated_desc'
    },
    isLoading: false,
    isSaving: false
};

function splitCharacterListInput(value) {
    return String(value || '')
        .split(/[、,，/\n]+/)
        .map(item => item.trim())
        .filter(Boolean);
}

function joinCharacterListInput(items) {
    return Array.isArray(items) ? items.join('、') : '';
}

function getCharacterProfileForDisplay(character = {}) {
    const profile = character.profile && typeof character.profile === 'object' ? character.profile : {};
    return {
        summary: profile.summary || character.description || '暂无角色简介',
        appearance: profile.appearance || '',
        personality: Array.isArray(profile.personality) && profile.personality.length ? profile.personality : (character.traits || []),
        motivation: profile.motivation || '',
        skills: Array.isArray(profile.skills) ? profile.skills : [],
        tags: Array.isArray(profile.tags) ? profile.tags : []
    };
}

async function loadCharacterLibrary(overrides = {}) {
    characterState.filters = { ...characterState.filters, ...overrides };
    const params = new URLSearchParams();
    if (characterState.filters.keyword) params.set('keyword', characterState.filters.keyword);
    if (characterState.filters.novelId) params.set('novel_id', characterState.filters.novelId);
    if (characterState.filters.roleType) params.set('role_type', characterState.filters.roleType);
    if (characterState.filters.tag) params.set('tag', characterState.filters.tag);
    if (characterState.filters.sort) params.set('sort', characterState.filters.sort);

    characterState.isLoading = true;
    renderCharacterCards();
    try {
        const res = await api.get(`/api/characters?${params.toString()}`);
        if (!res.success) {
            showToast(res.message || '角色库加载失败', 'error');
            return;
        }
        characterState.items = res.data.items || [];
        renderCharacterFilters();
        renderCharacterCards();
    } catch (err) {
        console.error('加载角色库失败:', err);
        showToast('加载角色库失败: ' + err.message, 'error');
    } finally {
        characterState.isLoading = false;
    }
}

function renderCharacterFilters() {
    const novelSelect = document.getElementById('character-library-novel-filter');
    const drawerNovelSelect = document.getElementById('character-novel-id');
    const options = ['<option value="">全部小说</option>']
        .concat(state.novels.map(novel => `<option value="${novel.id}">${escapeHtml(novel.title)}</option>`));
    novelSelect.innerHTML = options.join('');
    novelSelect.value = characterState.filters.novelId || '';
    drawerNovelSelect.innerHTML = ['<option value="">请选择小说</option>']
        .concat(state.novels.map(novel => `<option value="${novel.id}">${escapeHtml(novel.title)}</option>`))
        .join('');
}

function renderCharacterCards() {
    const grid = document.getElementById('character-library-grid');
    if (!grid) return;
    if (characterState.isLoading) {
        grid.innerHTML = '<div class="empty-state">角色库加载中...</div>';
        return;
    }
    if (!characterState.items.length) {
        grid.innerHTML = '<div class="empty-state">暂无角色卡</div>';
        return;
    }
    grid.innerHTML = characterState.items.map(character => {
        const profile = getCharacterProfileForDisplay(character);
        return `
            <article class="character-library-card" data-character-id="${character.id}">
                <div class="character-library-card-meta">
                    <span>${escapeHtml(character.novel_title || '未关联小说')}</span>
                    <span>${escapeHtml(character.role_type || '角色')}</span>
                </div>
                <h3>${escapeHtml(character.name)}</h3>
                <p>${escapeHtml(profile.summary)}</p>
                <div class="character-library-card-tags">
                    ${profile.tags.map(tag => `<span>${escapeHtml(tag)}</span>`).join('')}
                </div>
            </article>
        `;
    }).join('');
    grid.querySelectorAll('.character-library-card').forEach(card => {
        card.addEventListener('click', () => openCharacterDrawer(Number(card.dataset.characterId)));
    });
}
```

- [ ] **Step 6: Wire view switching in `app.js`**

In `init`, keep existing initial loaders and do not load the full character library until the user opens the view.

In `switchView`, add:

```javascript
    if (viewName === 'characters') {
        renderCharacterFilters();
        loadCharacterLibrary();
    }
```

Update filter/add button visibility so the novel-list toolbar remains hidden outside `novels`.

In `bindEvents`, add event listeners for character filters:

```javascript
    document.getElementById('character-library-search').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => loadCharacterLibrary({ keyword: e.target.value.trim() }), 300);
    });
    document.getElementById('character-library-novel-filter').addEventListener('change', (e) => loadCharacterLibrary({ novelId: e.target.value }));
    document.getElementById('character-library-role-filter').addEventListener('change', (e) => loadCharacterLibrary({ roleType: e.target.value }));
    document.getElementById('character-library-tag-filter').addEventListener('input', (e) => loadCharacterLibrary({ tag: e.target.value.trim() }));
    document.getElementById('character-library-sort').addEventListener('change', (e) => loadCharacterLibrary({ sort: e.target.value }));
```

- [ ] **Step 7: Run frontend shell tests**

Run:

```powershell
node tests/character-library-ui.test.js
node --check static/js/characters.js
node --check static/js/app.js
```

Expected: static shell checks pass for navigation, filters, card rendering, assets, and syntax.

- [ ] **Step 8: Commit frontend shell**

Run:

```powershell
git add templates/index.html static/css/style.css static/css/characters.css static/js/characters.js static/js/app.js tests/character-library-ui.test.js
git commit -m "feat: add character library shell"
```

Expected: commit succeeds.

## Task 8: Frontend Character Drawer CRUD And Relations

**Files:**
- Modify: `static/js/characters.js`
- Modify: `static/js/app.js`
- Modify: `static/css/characters.css`
- Test: `tests/character-library-ui.test.js`

- [ ] **Step 1: Add drawer helpers**

Add these drawer helper functions to `characters.js`:

```javascript
function openCharacterDrawerElement() {
    const drawer = document.getElementById('character-drawer');
    drawer.classList.add('active');
    drawer.setAttribute('aria-hidden', 'false');
}

function closeCharacterDrawer() {
    const drawer = document.getElementById('character-drawer');
    drawer.classList.remove('active');
    drawer.setAttribute('aria-hidden', 'true');
    characterState.activeCharacter = null;
}

function fillCharacterForm(character = {}) {
    const profile = getCharacterProfileForDisplay(character);
    document.getElementById('character-id').value = character.id || '';
    document.getElementById('character-novel-id').value = character.novel_id || characterState.filters.novelId || '';
    document.getElementById('character-name').value = character.name || '';
    document.getElementById('character-aliases').value = joinCharacterListInput(character.aliases);
    document.getElementById('character-role-type').value = character.role_type || '未知';
    document.getElementById('character-description').value = character.description || '';
    document.getElementById('character-traits').value = joinCharacterListInput(character.traits);
    document.getElementById('character-tags').value = joinCharacterListInput(profile.tags);
    document.getElementById('character-summary').value = profile.summary === '暂无角色简介' ? '' : profile.summary;
    document.getElementById('character-appearance').value = profile.appearance;
    document.getElementById('character-motivation').value = profile.motivation;
    document.getElementById('character-skills').value = joinCharacterListInput(profile.skills);
    document.getElementById('character-notes').value = character.notes || '';
}

function collectCharacterFormData() {
    return {
        novel_id: document.getElementById('character-novel-id').value,
        name: document.getElementById('character-name').value.trim(),
        aliases: splitCharacterListInput(document.getElementById('character-aliases').value),
        role_type: document.getElementById('character-role-type').value.trim() || '未知',
        description: document.getElementById('character-description').value.trim(),
        traits: splitCharacterListInput(document.getElementById('character-traits').value),
        profile: {
            summary: document.getElementById('character-summary').value.trim(),
            appearance: document.getElementById('character-appearance').value.trim(),
            personality: splitCharacterListInput(document.getElementById('character-traits').value),
            motivation: document.getElementById('character-motivation').value.trim(),
            skills: splitCharacterListInput(document.getElementById('character-skills').value),
            tags: splitCharacterListInput(document.getElementById('character-tags').value)
        },
        notes: document.getElementById('character-notes').value.trim()
    };
}
```

- [ ] **Step 2: Implement open/save/delete/AI**

Add:

```javascript
async function openCharacterDrawer(characterId) {
    renderCharacterFilters();
    if (!characterId) {
        characterState.activeCharacter = null;
        document.getElementById('character-drawer-title').textContent = '新建角色';
        document.getElementById('character-drawer-novel').textContent = '选择所属小说';
        fillCharacterForm({});
        renderCharacterRelations([]);
        openCharacterDrawerElement();
        return;
    }
    const res = await api.get(`/api/characters/${characterId}`);
    if (!res.success) {
        showToast(res.message || '角色详情加载失败', 'error');
        return;
    }
    characterState.activeCharacter = res.data;
    document.getElementById('character-drawer-title').textContent = res.data.name;
    document.getElementById('character-drawer-novel').textContent = res.data.novel_title || '未关联小说';
    fillCharacterForm(res.data);
    renderCharacterRelations(res.data.relations || []);
    renderCharacterRelationTargets(res.data);
    openCharacterDrawerElement();
}

async function saveCharacter() {
    const data = collectCharacterFormData();
    if (!data.name) {
        showToast('请填写角色名', 'error');
        return;
    }
    const id = document.getElementById('character-id').value;
    const res = id
        ? await api.put(`/api/characters/${id}`, data)
        : await api.post('/api/characters', data);
    if (!res.success) {
        showToast(res.message || '保存角色失败', 'error');
        return;
    }
    showToast(id ? '角色已更新' : '角色已创建', 'success');
    await loadCharacterLibrary();
    await openCharacterDrawer(res.data.id);
}

async function deleteCharacter() {
    const id = document.getElementById('character-id').value;
    if (!id) {
        closeCharacterDrawer();
        return;
    }
    if (!confirm('确定要删除这张角色卡吗？相关关系也会删除。')) return;
    const res = await api.delete(`/api/characters/${id}`);
    if (!res.success) {
        showToast(res.message || '删除角色失败', 'error');
        return;
    }
    showToast('角色已删除', 'success');
    closeCharacterDrawer();
    await loadCharacterLibrary();
}

async function completeCharacterWithAI() {
    const id = document.getElementById('character-id').value;
    if (!id) {
        showToast('请先保存角色，再使用 AI 补全', 'error');
        return;
    }
    const res = await api.post(`/api/characters/${id}/ai-complete`, {});
    if (!res.success) {
        showToast(res.message || 'AI 补全失败', 'error');
        return;
    }
    showToast('AI 已补全角色卡', 'success');
    await loadCharacterLibrary();
    await openCharacterDrawer(res.data.id);
}
```

- [ ] **Step 3: Wire drawer event handlers in `app.js`**

In `bindEvents`, add the drawer and relation button listeners after the character filter listeners:

```javascript
    document.getElementById('btn-character-create').addEventListener('click', () => openCharacterDrawer(null));
    document.getElementById('btn-character-save').addEventListener('click', saveCharacter);
    document.getElementById('btn-character-delete').addEventListener('click', deleteCharacter);
    document.getElementById('btn-character-ai-complete').addEventListener('click', completeCharacterWithAI);
    document.getElementById('btn-character-relation-save').addEventListener('click', saveCharacterRelation);
    document.getElementById('btn-character-drawer-close').addEventListener('click', closeCharacterDrawer);
```

- [ ] **Step 4: Implement relation rendering and saving**

Add:

```javascript
function renderCharacterRelations(relations = []) {
    const list = document.getElementById('character-relation-list');
    if (!relations.length) {
        list.innerHTML = '<div class="character-relation-empty">暂无相关角色</div>';
        return;
    }
    list.innerHTML = relations.map(relation => `
        <div class="character-relation-item" data-relation-id="${relation.id}">
            <strong>${escapeHtml(relation.other_name || relation.target_name || relation.source_name || '未知角色')}</strong>
            <span>${escapeHtml(relation.relation_type || '相关')}</span>
            <p>${escapeHtml(relation.description || '暂无说明')}</p>
            <button class="btn btn-sm btn-secondary" data-relation-delete="${relation.id}">删除</button>
        </div>
    `).join('');
    list.querySelectorAll('[data-relation-delete]').forEach(button => {
        button.addEventListener('click', () => deleteCharacterRelation(Number(button.dataset.relationDelete)));
    });
}

function renderCharacterRelationTargets(character = {}) {
    const select = document.getElementById('character-relation-target');
    const currentNovelId = String(character.novel_id || document.getElementById('character-novel-id').value || '');
    const currentId = Number(character.id || 0);
    const options = characterState.items
        .filter(item => String(item.novel_id) === currentNovelId && item.id !== currentId)
        .map(item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`);
    select.innerHTML = '<option value="">选择同书角色</option>' + options.join('');
}

async function saveCharacterRelation() {
    const sourceId = document.getElementById('character-id').value;
    const targetId = document.getElementById('character-relation-target').value;
    const relationType = document.getElementById('character-relation-type').value.trim();
    const description = document.getElementById('character-relation-description').value.trim();
    if (!sourceId || !targetId) {
        showToast('请选择要关联的角色', 'error');
        return;
    }
    const res = await api.post(`/api/characters/${sourceId}/relations`, {
        target_character_id: targetId,
        relation_type: relationType || '相关',
        description
    });
    if (!res.success) {
        showToast(res.message || '保存关系失败', 'error');
        return;
    }
    document.getElementById('character-relation-type').value = '';
    document.getElementById('character-relation-description').value = '';
    await openCharacterDrawer(Number(sourceId));
}

async function deleteCharacterRelation(relationId) {
    const res = await api.delete(`/api/character-relations/${relationId}`);
    if (!res.success) {
        showToast(res.message || '删除关系失败', 'error');
        return;
    }
    await openCharacterDrawer(Number(document.getElementById('character-id').value));
}
```

- [ ] **Step 5: Add CSS for relation items**

Append to `static/css/characters.css`:

```css
.character-relation-item,
.character-relation-empty {
    display: grid;
    gap: 6px;
    padding: 10px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    background: #f8fafc;
}

.character-relation-item p {
    margin: 0;
    color: var(--text-secondary);
}
```

- [ ] **Step 6: Update static test for executable functions**

In `tests/character-library-ui.test.js`, add assertions:

```javascript
assert.match(charactersJs, /function collectCharacterFormData/, 'characters module should collect drawer form data');
assert.match(charactersJs, /function renderCharacterRelations/, 'characters module should render relation list');
assert.match(charactersJs, /async function openCharacterDrawer/, 'characters module should open drawer');
assert.match(charactersJs, /async function saveCharacter/, 'characters module should save characters');
assert.match(charactersJs, /async function deleteCharacter/, 'characters module should delete characters');
assert.match(charactersJs, /async function completeCharacterWithAI/, 'characters module should call AI completion');
assert.match(charactersJs, /async function saveCharacterRelation/, 'characters module should save relations');
assert.match(charactersJs, /async function deleteCharacterRelation/, 'characters module should delete relations');
assert.match(charactersJs, /\/api\/character-relations/, 'characters module should call relation API');
```

- [ ] **Step 7: Run frontend tests**

Run:

```powershell
node tests/character-library-ui.test.js
node --check static/js/characters.js
node --check static/js/app.js
```

Expected: pass.

- [ ] **Step 8: Commit drawer implementation**

Run:

```powershell
git add static/js/characters.js static/js/app.js static/css/characters.css tests/character-library-ui.test.js
git commit -m "feat: add character library drawer interactions"
```

Expected: commit succeeds.

## Task 9: Novel Detail Entry To Global Character Library

**Files:**
- Modify: `templates/index.html`
- Modify: `static/js/novels.js`
- Modify: `static/js/characters.js`
- Modify: `tests/character-analysis-ui.test.js`
- Test: `tests/character-analysis-ui.test.js`
- Test: `tests/character-library-ui.test.js`

- [ ] **Step 1: Add detail Tab entry button**

In the novel detail character panel header, add a button before the AI generation button:

```html
                                <button class="btn btn-sm btn-secondary" id="btn-open-character-library">
                                    <i class="fas fa-address-card"></i>
                                    打开角色库查看全部
                                </button>
```

- [ ] **Step 2: Add bridge function in `characters.js`**

Add:

```javascript
function openCharacterLibraryForNovel(novelId) {
    const normalizedNovelId = novelId ? String(novelId) : '';
    switchView('characters');
    document.getElementById('character-library-novel-filter').value = normalizedNovelId;
    loadCharacterLibrary({ novelId: normalizedNovelId });
}
```

- [ ] **Step 3: Wire detail button in `novels.js`**

In `renderNovelDetail`, after binding `btn-detail-analyze-characters`, add:

```javascript
    document.getElementById('btn-open-character-library').onclick = () => openCharacterLibraryForNovel(novel.id);
```

- [ ] **Step 4: Run detail-entry tests**

Run:

```powershell
node tests/character-analysis-ui.test.js
node tests/character-library-ui.test.js
node --check static/js/characters.js
node --check static/js/novels.js
```

Expected: all pass.

- [ ] **Step 5: Commit detail entry**

Run:

```powershell
git add templates/index.html static/js/characters.js static/js/novels.js tests/character-analysis-ui.test.js
git commit -m "feat: link novel detail to character library"
```

Expected: commit succeeds.

## Task 10: Regression Verification And Polish

**Files:**
- Verify: all modified files

- [ ] **Step 1: Run backend test suite**

Run:

```powershell
python tests/character_library.test.py
python tests/character_analysis.test.py
python tests/app_structure.test.py
```

Expected: all pass.

- [ ] **Step 2: Run frontend static tests**

Run:

```powershell
node tests/character-library-ui.test.js
node tests/character-analysis-ui.test.js
node tests/novel-detail-ui.test.js
```

Expected: all pass.

- [ ] **Step 3: Run syntax checks**

Run:

```powershell
python -m py_compile app.py ai_client.py ai_routes.py character_routes.py crawler_routes.py reader_utils.py storage_utils.py
node --check static/js/app.js
node --check static/js/core.js
node --check static/js/novels.js
node --check static/js/characters.js
```

Expected: all pass.

- [ ] **Step 4: Inspect diff and status**

Run:

```powershell
git status --short
git diff --stat HEAD
```

Expected: no modified or staged feature files remain. Pre-existing unrelated untracked files are left untouched.

- [ ] **Step 5: Confirm clean feature handoff**

Run:

```powershell
git status --short
```

Expected: no modified or staged feature files remain. Any unrelated untracked files listed by Git are not part of this plan.

## Self-Review

- Spec coverage: The plan covers global character library navigation, independent list and drawer UI, backend CRUD, relation editing, single-card AI completion, novel-level AI preservation behavior, novel-detail entry, static frontend checks, backend tests, and regression verification.
- Placeholder scan: The plan has no placeholder tasks and includes concrete route names, file paths, commands, test code, and implementation snippets.
- Type consistency: The plan consistently uses `profile.summary`, `profile.appearance`, `profile.personality`, `profile.motivation`, `profile.skills`, `profile.tags`, `notes`, and `is_manual`; route ids consistently use `character_id` and `relation_id`.
