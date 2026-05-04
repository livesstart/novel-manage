"""Character library routes."""
import json
import re
import sqlite3
import textwrap

from flask import jsonify, request

from ai_client import get_ai_client


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


def build_profile_from_row(item):
    profile = parse_json_dict(item.pop('profile_json', '{}'))
    traits = item.get('traits') or []
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
            if payload['novel_id'] != existing['novel_id']:
                cursor.execute('''
                    DELETE FROM novel_character_relations
                    WHERE source_character_id = ? OR target_character_id = ?
                ''', (character_id, character_id))
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
