"""AI configuration and metadata routes."""
import json
import re
import sqlite3
import textwrap

from flask import jsonify, request

from ai_client import (
    AIConfig,
    AIClientFactory,
    get_ai_client,
    get_native_gemini_client,
    is_gemini_compatible_config,
)
from ai_context import (
    DEFAULT_AI_CONTEXT_CHAR_BUDGET,
    build_novel_ai_context,
    summarize_novel_ai_context,
)


def ensure_character_analysis_schema(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novel_character_analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL UNIQUE,
            status TEXT DEFAULT 'pending',
            model TEXT,
            character_count INTEGER DEFAULT 0,
            relation_count INTEGER DEFAULT 0,
            source_excerpt_chars INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novel_characters (
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
            UNIQUE (novel_id, name),
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('PRAGMA table_info(novel_characters)')
    character_columns = {row[1] for row in cursor.fetchall()}
    if 'profile_json' not in character_columns:
        cursor.execute("ALTER TABLE novel_characters ADD COLUMN profile_json TEXT DEFAULT '{}'")
    if 'notes' not in character_columns:
        cursor.execute("ALTER TABLE novel_characters ADD COLUMN notes TEXT DEFAULT ''")
    if 'is_manual' not in character_columns:
        cursor.execute('ALTER TABLE novel_characters ADD COLUMN is_manual INTEGER DEFAULT 0')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novel_character_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL,
            source_character_id INTEGER NOT NULL,
            target_character_id INTEGER NOT NULL,
            relation_type TEXT,
            description TEXT,
            evidence TEXT,
            confidence REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE,
            FOREIGN KEY (source_character_id) REFERENCES novel_characters(id) ON DELETE CASCADE,
            FOREIGN KEY (target_character_id) REFERENCES novel_characters(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('PRAGMA table_info(novel_character_relations)')
    relation_columns = {row[1] for row in cursor.fetchall()}
    if 'is_manual' not in relation_columns:
        cursor.execute('ALTER TABLE novel_character_relations ADD COLUMN is_manual INTEGER DEFAULT 0')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_novel_characters_novel ON novel_characters(novel_id, sort_order)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_novel_relations_novel ON novel_character_relations(novel_id, sort_order)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novel_setting_analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL UNIQUE,
            status TEXT DEFAULT 'pending',
            model TEXT,
            setting_count INTEGER DEFAULT 0,
            source_excerpt_chars INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novel_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL,
            category TEXT,
            name TEXT NOT NULL,
            summary TEXT,
            details TEXT,
            evidence TEXT,
            confidence REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (novel_id, category, name),
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_novel_settings_novel ON novel_settings(novel_id, sort_order)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novel_writing_style_analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL UNIQUE,
            status TEXT DEFAULT 'pending',
            model TEXT,
            source_excerpt_chars INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novel_writing_styles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL UNIQUE,
            summary TEXT,
            narrative_perspective TEXT,
            language_texture TEXT,
            pacing TEXT,
            description_focus TEXT,
            dialogue_style TEXT,
            emotional_tone TEXT,
            signature_techniques_json TEXT DEFAULT '[]',
            examples_json TEXT DEFAULT '[]',
            imitation_guide TEXT,
            style_prompt TEXT,
            confidence REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
        )
    ''')


def register_ai_routes(app, *, get_db, resolve_novel_file_path, is_text_readable_file, detect_encoding):
    AI_TAG_COLOR_PALETTE = [
        '#6366f1', '#8b5cf6', '#06b6d4', '#14b8a6',
        '#22c55e', '#eab308', '#f97316', '#ef4444',
        '#ec4899', '#3b82f6'
    ]


    def get_novel_detail_record(novel_id):
        """获取单本小说详情及标签，用于 AI 元数据生成。"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT n.*, c.name as category_name
            FROM novels n
            LEFT JOIN categories c ON n.category_id = c.id
            WHERE n.id = ?
        ''', (novel_id,))
        novel = cursor.fetchone()

        if not novel:
            conn.close()
            return None

        novel = dict(novel)
        cursor.execute('''
            SELECT t.id, t.name, t.color
            FROM tags t
            JOIN novel_tags nt ON t.id = nt.tag_id
            WHERE nt.novel_id = ?
            ORDER BY t.name ASC
        ''', (novel_id,))
        novel['tags'] = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return novel


    def get_category_name_by_id(category_id):
        """根据分类 ID 获取分类名称。"""
        if not category_id:
            return ''

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM categories WHERE id = ?', (category_id,))
        row = cursor.fetchone()
        conn.close()
        return row['name'] if row else ''


    def get_tag_names_by_ids(tag_ids):
        """根据标签 ID 列表获取标签名称。"""
        if not tag_ids:
            return []

        clean_ids = [int(tag_id) for tag_id in tag_ids if str(tag_id).isdigit()]
        if not clean_ids:
            return []

        conn = get_db()
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in clean_ids)
        cursor.execute(
            f'SELECT name FROM tags WHERE id IN ({placeholders}) ORDER BY name ASC',
            clean_ids
        )
        names = [row['name'] for row in cursor.fetchall()]
        conn.close()
        return names


    def extract_text_excerpt(file_path, max_chars=4000):
        """提取 TXT 小说前几个字符，作为 AI 生成上下文。"""
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


    def build_ai_context_for_novel(novel, *, focus_chapter_index=None, char_budget=DEFAULT_AI_CONTEXT_CHAR_BUDGET):
        return build_novel_ai_context(
            novel,
            resolve_novel_file_path=resolve_novel_file_path,
            is_text_readable_file=is_text_readable_file,
            char_budget=char_budget,
            focus_chapter_index=focus_chapter_index,
        )


    def has_usable_novel_ai_context(novel, novel_context):
        return bool(
            novel.get('title')
            or novel.get('description')
            or novel_context.get('content_text')
        )


    READER_ASSISTANT_QUESTION_MAX_CHARS = 2000
    READER_ASSISTANT_HISTORY_MAX_MESSAGES = 6
    READER_ASSISTANT_HISTORY_MAX_CHARS = 1200


    def normalize_reader_assistant_question(value):
        return re.sub(r'\s+', ' ', str(value or '')).strip()[:READER_ASSISTANT_QUESTION_MAX_CHARS]


    def normalize_reader_assistant_history(items):
        normalized = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            role = item.get('role')
            if role not in {'user', 'assistant'}:
                continue
            content = re.sub(r'\s+', ' ', str(item.get('content') or '')).strip()
            if not content:
                continue
            normalized.append({'role': role, 'content': content[:READER_ASSISTANT_HISTORY_MAX_CHARS]})
        return normalized[-READER_ASSISTANT_HISTORY_MAX_MESSAGES:]


    def build_reader_assistant_messages(novel_context, *, question, chapter_index=None, chapter_title='', conversation=None):
        messages = [
            {
                'role': 'system',
                'content': (
                    '你是阅读器内的小说 AI 助手。只根据当前提供的小说上下文回答。'
                    '如果上下文无法确认答案，请直接说明无法确认，不要编造剧情、人物关系或结局。'
                ),
            },
            {
                'role': 'user',
                'content': novel_context.get('context_text') or 'Novel content context: Not available.',
            },
        ]
        messages.extend(normalize_reader_assistant_history(conversation))

        chapter_line = ''
        if chapter_index is not None or chapter_title:
            chapter_label = chapter_title or f'Chapter {chapter_index + 1}'
            chapter_line = f'Current chapter: {chapter_label}\n'

        messages.append({
            'role': 'user',
            'content': f"{chapter_line}Question: {question}",
        })
        return messages


    def extract_json_object(text):
        """从 AI 文本响应中提取 JSON 对象。"""
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


    def clamp_confidence(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0
        return max(0, min(number, 1))


    def normalize_short_text(value, max_length=160):
        text = re.sub(r'\s+', ' ', str(value or '')).strip()
        return text[:max_length].strip()


    def normalize_string_list(value, *, max_items=6, max_length=24):
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
            if len(text) < 2:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(text)
            if len(normalized) >= max_items:
                break

        return normalized


    def normalize_character_profile(item, *, description='', traits=None, first_chapter_index=None, evidence=''):
        traits = traits or []
        first_seen = normalize_short_text(item.get('first_seen'), max_length=180)
        if not first_seen and first_chapter_index is not None:
            first_seen = f'第 {first_chapter_index + 1} 章'

        return {
            'summary': normalize_short_text(item.get('summary') or description, max_length=120),
            'appearance': normalize_short_text(item.get('appearance'), max_length=180),
            'personality': normalize_string_list(item.get('personality') or traits, max_items=8, max_length=18),
            'motivation': normalize_short_text(item.get('motivation'), max_length=180),
            'skills': normalize_string_list(item.get('skills'), max_items=8, max_length=18),
            'first_seen': first_seen,
            'card_evidence': normalize_short_text(item.get('card_evidence') or evidence, max_length=180),
        }


    def normalize_character_analysis_payload(payload):
        raw_characters = payload.get('characters') if isinstance(payload, dict) else []
        raw_relations = payload.get('relations') if isinstance(payload, dict) else []
        characters = []
        name_map = {}

        for item in raw_characters or []:
            if not isinstance(item, dict):
                continue
            name = normalize_short_text(item.get('name'), max_length=32)
            if not name:
                continue
            key = name.lower()
            if key in name_map:
                continue

            try:
                first_chapter_index = int(item.get('first_chapter_index'))
            except (TypeError, ValueError):
                first_chapter_index = None

            description = normalize_short_text(item.get('description'), max_length=260)
            traits = normalize_string_list(item.get('traits') or item.get('personality'), max_items=8, max_length=18)
            evidence = normalize_short_text(item.get('evidence'), max_length=220)
            profile = normalize_character_profile(
                item,
                description=description,
                traits=traits,
                first_chapter_index=first_chapter_index if first_chapter_index is None or first_chapter_index >= 0 else None,
                evidence=evidence,
            )

            character = {
                'name': name,
                'aliases': normalize_string_list(item.get('aliases'), max_items=6, max_length=24),
                'role_type': normalize_short_text(item.get('role_type'), max_length=32),
                'description': description,
                'traits': traits,
                'first_chapter_index': first_chapter_index if first_chapter_index is None or first_chapter_index >= 0 else None,
                'evidence': evidence,
                'confidence': clamp_confidence(item.get('confidence')),
                'profile': profile,
            }
            name_map[key] = character
            characters.append(character)
            if len(characters) >= 24:
                break

        relations = []
        relation_keys = set()
        for item in raw_relations or []:
            if not isinstance(item, dict):
                continue
            source_name = normalize_short_text(item.get('source') or item.get('source_name'), max_length=32)
            target_name = normalize_short_text(item.get('target') or item.get('target_name'), max_length=32)
            source_key = source_name.lower()
            target_key = target_name.lower()
            if not source_key or not target_key or source_key == target_key:
                continue
            if source_key not in name_map or target_key not in name_map:
                continue

            relation_type = normalize_short_text(item.get('relation_type') or item.get('type'), max_length=32)
            relation_key = (source_key, target_key, relation_type.lower())
            if relation_key in relation_keys:
                continue
            relation_keys.add(relation_key)

            relations.append({
                'source_name': name_map[source_key]['name'],
                'target_name': name_map[target_key]['name'],
                'relation_type': relation_type or '相关',
                'description': normalize_short_text(item.get('description'), max_length=260),
                'evidence': normalize_short_text(item.get('evidence'), max_length=220),
                'confidence': clamp_confidence(item.get('confidence')),
            })
            if len(relations) >= 40:
                break

        return characters, relations


    def build_character_analysis_messages(novel, novel_context):
        context_text = novel_context.get('context_text') or 'Novel content context: Not available.'
        context_blocks = [
            f'标题：{novel.get("title") or "未提供"}',
            f'作者：{novel.get("author") or "未提供"}',
            f'简介：{novel.get("description") or "无"}',
            context_text,
        ]

        user_prompt = '\n\n'.join(context_blocks) + textwrap.dedent("""

    请为这本小说中已经明确出现或被文本直接支持的角色生成角色卡，并整理角色之间的关系。

    要求：
    1. 只输出一个 JSON 对象，不要输出 Markdown。
    2. JSON 格式必须为：
       {"characters":[{"name":"角色名","aliases":["别名"],"role_type":"主角/反派/同伴/配角/未知","summary":"一句话角色定位","description":"角色说明","appearance":"外貌或气质","personality":["性格标签"],"motivation":"明确动机","skills":["能力或特长"],"first_seen":"首次出现位置","first_chapter_index":0,"evidence":"证据片段","confidence":0.8}],"relations":[{"source":"角色A","target":"角色B","relation_type":"关系类型","description":"关系说明","evidence":"证据片段","confidence":0.8}]}
    3. 只基于已提供文本判断，不要编造未出现的人物、关系和结局。
    4. characters 最多 12 个，relations 最多 20 条。
    5. evidence 必须是能支持判断的简短文本依据。
    6. 信息不足的扩展字段可以留空字符串或空数组，不要补写未被文本支持的细节。
    7. confidence 用 0 到 1 的数字表示可信度。
    """)

        return [
            {
                'role': 'system',
                'content': '你是一个严谨的小说角色卡整理助手，只根据文本证据整理角色资料和关系。'
            },
            {
                'role': 'user',
                'content': user_prompt.strip()
            }
        ]


    def normalize_setting_analysis_payload(payload):
        raw_settings = payload.get('settings') if isinstance(payload, dict) else []
        if not raw_settings and isinstance(payload, dict):
            raw_settings = payload.get('world_settings') or payload.get('novel_settings') or []

        if isinstance(raw_settings, dict):
            expanded = []
            for category, values in raw_settings.items():
                if isinstance(values, list):
                    for value in values:
                        if isinstance(value, dict):
                            expanded.append({'category': category, **value})
                        else:
                            expanded.append({'category': category, 'name': value})
                elif isinstance(values, dict):
                    expanded.append({'category': category, **values})
                else:
                    expanded.append({'category': category, 'name': values})
            raw_settings = expanded

        settings = []
        seen = set()
        for item in raw_settings or []:
            if not isinstance(item, dict):
                item = {'name': item}

            category = normalize_short_text(item.get('category') or item.get('type') or '其他', max_length=24)
            name = normalize_short_text(item.get('name') or item.get('title'), max_length=48)
            summary = normalize_short_text(item.get('summary') or item.get('description'), max_length=220)
            details = item.get('details') or item.get('detail') or item.get('notes') or ''
            if isinstance(details, list):
                details = '；'.join(normalize_short_text(value, max_length=120) for value in details if value)
            details = normalize_short_text(details, max_length=520)
            evidence = normalize_short_text(item.get('evidence'), max_length=220)

            if not name and summary:
                name = summary[:32].strip()
            if not name:
                continue

            key = (category.lower(), name.lower())
            if key in seen:
                continue
            seen.add(key)
            settings.append({
                'category': category or '其他',
                'name': name,
                'summary': summary,
                'details': details,
                'evidence': evidence,
                'confidence': clamp_confidence(item.get('confidence')),
            })
            if len(settings) >= 40:
                break

        return settings


    def build_setting_analysis_messages(novel, novel_context):
        context_text = novel_context.get('context_text') or 'Novel content context: Not available.'
        context_blocks = [
            f'标题：{novel.get("title") or "未提供"}',
            f'作者：{novel.get("author") or "未提供"}',
            f'简介：{novel.get("description") or "无"}',
            context_text,
        ]

        user_prompt = '\n\n'.join(context_blocks) + textwrap.dedent("""

    请提取这本小说中已经明确出现或被文本直接支持的关键设定，整理成可维护的设定集。

    可关注但不限于：世界观、地点、组织势力、规则体系、能力体系、时间线、关键物品、专有术语、社会制度。

    要求：
    1. 只输出一个 JSON 对象，不要输出 Markdown。
    2. JSON 格式必须为：
       {"settings":[{"category":"世界观/地点/组织/规则体系/时间线/关键物品/术语/其他","name":"设定名","summary":"一句话说明","details":"详细说明","evidence":"证据片段","confidence":0.8}]}
    3. 只基于已提供文本判断，不要编造未出现的设定、背景和结局。
    4. settings 最多 18 条，优先保留影响剧情理解的核心设定。
    5. evidence 必须是能支持判断的简短文本依据。
    6. 信息不足时返回空字符串，不要补写未被文本支持的细节。
    7. confidence 用 0 到 1 的数字表示可信度。
    """)

        return [
            {
                'role': 'system',
                'content': '你是一个严谨的小说设定整理助手，只根据文本证据提取世界观、规则和关键设定。'
            },
            {
                'role': 'user',
                'content': user_prompt.strip()
            }
        ]


    def normalize_writing_style_techniques(raw_items):
        techniques = []
        for item in raw_items or []:
            if isinstance(item, str):
                item = {'name': item}
            if not isinstance(item, dict):
                continue

            technique = {
                'name': normalize_short_text(
                    item.get('name') or item.get('title') or item.get('technique'),
                    max_length=48
                ),
                'description': normalize_short_text(
                    item.get('description') or item.get('summary') or item.get('analysis'),
                    max_length=260
                ),
                'evidence': normalize_short_text(item.get('evidence'), max_length=220),
                'confidence': clamp_confidence(item.get('confidence')),
            }
            if technique['name'] or technique['description'] or technique['evidence']:
                techniques.append(technique)
            if len(techniques) >= 8:
                break

        return techniques


    def normalize_writing_style_examples(raw_items):
        examples = []
        for item in raw_items or []:
            if isinstance(item, str):
                item = {'evidence': item}
            if not isinstance(item, dict):
                continue

            example = {
                'label': normalize_short_text(
                    item.get('label') or item.get('name') or item.get('title'),
                    max_length=48
                ),
                'analysis': normalize_short_text(
                    item.get('analysis') or item.get('description') or item.get('summary'),
                    max_length=260
                ),
                'evidence': normalize_short_text(item.get('evidence') or item.get('excerpt'), max_length=220),
                'confidence': clamp_confidence(item.get('confidence')),
            }
            if example['label'] or example['analysis'] or example['evidence']:
                examples.append(example)
            if len(examples) >= 6:
                break

        return examples


    def normalize_writing_style_analysis_payload(payload):
        source = payload if isinstance(payload, dict) else {}
        return {
            'summary': normalize_short_text(source.get('summary') or source.get('overview'), max_length=260),
            'narrative_perspective': normalize_short_text(
                source.get('narrative_perspective') or source.get('perspective'),
                max_length=240
            ),
            'language_texture': normalize_short_text(
                source.get('language_texture') or source.get('language_style'),
                max_length=240
            ),
            'pacing': normalize_short_text(source.get('pacing') or source.get('rhythm'), max_length=240),
            'description_focus': normalize_short_text(
                source.get('description_focus') or source.get('descriptive_focus'),
                max_length=240
            ),
            'dialogue_style': normalize_short_text(source.get('dialogue_style'), max_length=240),
            'emotional_tone': normalize_short_text(
                source.get('emotional_tone') or source.get('tone'),
                max_length=240
            ),
            'signature_techniques': normalize_writing_style_techniques(
                source.get('signature_techniques') or source.get('techniques')
            ),
            'examples': normalize_writing_style_examples(
                source.get('examples') or source.get('representative_examples')
            ),
            'imitation_guide': normalize_short_text(
                source.get('imitation_guide') or source.get('writing_guide') or source.get('style_guide'),
                max_length=900
            ),
            'style_prompt': normalize_short_text(
                source.get('style_prompt') or source.get('prompt') or source.get('imitation_prompt'),
                max_length=1200
            ),
            'confidence': clamp_confidence(source.get('confidence')),
        }


    def has_writing_style_content(style):
        text_fields = (
            'summary',
            'narrative_perspective',
            'language_texture',
            'pacing',
            'description_focus',
            'dialogue_style',
            'emotional_tone',
            'imitation_guide',
            'style_prompt',
        )
        return any(style.get(field) for field in text_fields) or bool(style.get('signature_techniques')) or bool(style.get('examples'))


    def build_writing_style_analysis_messages(novel, novel_context):
        context_text = novel_context.get('context_text') or 'Novel content context: Not available.'
        context_blocks = [
            f'标题：{novel.get("title") or "未提供"}',
            f'作者：{novel.get("author") or "未提供"}',
            f'简介：{novel.get("description") or "无"}',
            context_text,
        ]

        user_prompt = '\n\n'.join(context_blocks) + textwrap.dedent("""

    请分析这本小说已经体现出的写作风格，并整理成可用于后续创作参考的风格档案和仿写指南。

    要求：
    1. 只输出一个 JSON 对象，不要输出 Markdown。
    2. JSON 格式必须为：
       {"summary":"整体写作风格概述","narrative_perspective":"叙事视角","language_texture":"语言质感","pacing":"节奏特征","description_focus":"描写重点","dialogue_style":"对话风格","emotional_tone":"情绪基调","signature_techniques":[{"name":"技法名称","description":"技法说明","evidence":"证据片段","confidence":0.8}],"examples":[{"label":"片段标签","analysis":"片段体现的风格特征","evidence":"证据片段","confidence":0.8}],"imitation_guide":"面向后续写作的具体指南","style_prompt":"可复制给 AI 的风格复刻提示词","confidence":0.8}
    3. 只基于已提供文本判断，不要编造未出现的剧情、人物关系或结局。
    4. signature_techniques 最多 8 条，examples 最多 6 条。
    5. evidence 必须是能支持判断的简短文本依据。
    6. imitation_guide 要写成可执行建议，说明句式、节奏、描写重点、对话和情绪控制方式。
    7. style_prompt 要能直接复制给 AI 使用，要求简洁但足够具体。
    8. confidence 用 0 到 1 的数字表示整体可信度。
    """)

        return [
            {
                'role': 'system',
                'content': '你是一个严谨的小说写作风格分析助手，只根据文本证据总结叙事风格、语言特征和仿写方法。'
            },
            {
                'role': 'user',
                'content': user_prompt.strip()
            }
        ]


    def serialize_setting_analysis(novel_id):
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT *
            FROM novel_setting_analysis_runs
            WHERE novel_id = ?
        ''', (novel_id,))
        run = cursor.fetchone()

        cursor.execute('''
            SELECT *
            FROM novel_settings
            WHERE novel_id = ?
            ORDER BY sort_order ASC, id ASC
        ''', (novel_id,))
        settings = [dict(row) for row in cursor.fetchall()]
        conn.close()

        run_data = dict(run) if run else None
        status = (run_data or {}).get('status') or ('completed' if settings else 'empty')
        return {
            'novel_id': novel_id,
            'analysis_status': status,
            'analyzed_at': (run_data or {}).get('finished_at') or (run_data or {}).get('updated_at'),
            'error_message': (run_data or {}).get('error_message'),
            'setting_count': len(settings),
            'settings': settings,
        }


    def replace_setting_analysis(novel_id, settings, *, model='', source_excerpt_chars=0):
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM novel_settings WHERE novel_id = ?', (novel_id,))
            for index, setting in enumerate(settings):
                cursor.execute('''
                    INSERT INTO novel_settings (
                        novel_id, category, name, summary, details,
                        evidence, confidence, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    novel_id,
                    setting['category'],
                    setting['name'],
                    setting['summary'],
                    setting['details'],
                    setting['evidence'],
                    setting['confidence'],
                    index,
                ))

            cursor.execute('''
                INSERT INTO novel_setting_analysis_runs (
                    novel_id, status, model, setting_count,
                    source_excerpt_chars, error_message, updated_at, finished_at
                ) VALUES (?, 'completed', ?, ?, ?, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(novel_id) DO UPDATE SET
                    status = 'completed',
                    model = excluded.model,
                    setting_count = excluded.setting_count,
                    source_excerpt_chars = excluded.source_excerpt_chars,
                    error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP,
                    finished_at = CURRENT_TIMESTAMP
            ''', (
                novel_id,
                model,
                len(settings),
                source_excerpt_chars,
            ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return serialize_setting_analysis(novel_id)


    def mark_setting_analysis_failed(novel_id, error_message, *, model='', source_excerpt_chars=0):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO novel_setting_analysis_runs (
                novel_id, status, model, setting_count,
                source_excerpt_chars, error_message, updated_at
            ) VALUES (?, 'failed', ?, 0, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(novel_id) DO UPDATE SET
                status = 'failed',
                model = excluded.model,
                source_excerpt_chars = excluded.source_excerpt_chars,
                error_message = excluded.error_message,
                updated_at = CURRENT_TIMESTAMP
        ''', (novel_id, model, source_excerpt_chars, error_message[:500]))
        conn.commit()
        conn.close()


    def serialize_writing_style_analysis(novel_id):
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT *
            FROM novel_writing_style_analysis_runs
            WHERE novel_id = ?
        ''', (novel_id,))
        run = cursor.fetchone()

        cursor.execute('''
            SELECT *
            FROM novel_writing_styles
            WHERE novel_id = ?
        ''', (novel_id,))
        style_row = cursor.fetchone()
        conn.close()

        style = dict(style_row) if style_row else {}
        run_data = dict(run) if run else None
        status = (run_data or {}).get('status') or ('completed' if style else 'empty')
        return {
            'novel_id': novel_id,
            'analysis_status': status,
            'analyzed_at': (run_data or {}).get('finished_at') or (run_data or {}).get('updated_at'),
            'error_message': (run_data or {}).get('error_message'),
            'summary': style.get('summary') or '',
            'narrative_perspective': style.get('narrative_perspective') or '',
            'language_texture': style.get('language_texture') or '',
            'pacing': style.get('pacing') or '',
            'description_focus': style.get('description_focus') or '',
            'dialogue_style': style.get('dialogue_style') or '',
            'emotional_tone': style.get('emotional_tone') or '',
            'signature_techniques': parse_json_list(style.get('signature_techniques_json')),
            'examples': parse_json_list(style.get('examples_json')),
            'imitation_guide': style.get('imitation_guide') or '',
            'style_prompt': style.get('style_prompt') or '',
            'confidence': clamp_confidence(style.get('confidence')),
        }


    def replace_writing_style_analysis(novel_id, style, *, model='', source_excerpt_chars=0):
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM novel_writing_styles WHERE novel_id = ?', (novel_id,))
            cursor.execute('''
                INSERT INTO novel_writing_styles (
                    novel_id, summary, narrative_perspective, language_texture,
                    pacing, description_focus, dialogue_style, emotional_tone,
                    signature_techniques_json, examples_json, imitation_guide,
                    style_prompt, confidence, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                novel_id,
                style['summary'],
                style['narrative_perspective'],
                style['language_texture'],
                style['pacing'],
                style['description_focus'],
                style['dialogue_style'],
                style['emotional_tone'],
                json.dumps(style['signature_techniques'], ensure_ascii=False),
                json.dumps(style['examples'], ensure_ascii=False),
                style['imitation_guide'],
                style['style_prompt'],
                style['confidence'],
            ))

            cursor.execute('''
                INSERT INTO novel_writing_style_analysis_runs (
                    novel_id, status, model, source_excerpt_chars,
                    error_message, updated_at, finished_at
                ) VALUES (?, 'completed', ?, ?, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(novel_id) DO UPDATE SET
                    status = 'completed',
                    model = excluded.model,
                    source_excerpt_chars = excluded.source_excerpt_chars,
                    error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP,
                    finished_at = CURRENT_TIMESTAMP
            ''', (
                novel_id,
                model,
                source_excerpt_chars,
            ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return serialize_writing_style_analysis(novel_id)


    def mark_writing_style_analysis_failed(novel_id, error_message, *, model='', source_excerpt_chars=0):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO novel_writing_style_analysis_runs (
                novel_id, status, model, source_excerpt_chars,
                error_message, updated_at
            ) VALUES (?, 'failed', ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(novel_id) DO UPDATE SET
                status = 'failed',
                model = excluded.model,
                source_excerpt_chars = excluded.source_excerpt_chars,
                error_message = excluded.error_message,
                updated_at = CURRENT_TIMESTAMP
        ''', (novel_id, model, source_excerpt_chars, error_message[:500]))
        conn.commit()
        conn.close()


    def serialize_character_analysis(novel_id):
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT *
            FROM novel_character_analysis_runs
            WHERE novel_id = ?
        ''', (novel_id,))
        run = cursor.fetchone()

        cursor.execute('''
            SELECT *
            FROM novel_characters
            WHERE novel_id = ?
            ORDER BY sort_order ASC, id ASC
        ''', (novel_id,))
        characters = []
        character_ids = set()
        for row in cursor.fetchall():
            item = dict(row)
            character_ids.add(item['id'])
            item['aliases'] = parse_json_list(item.pop('aliases_json', '[]'))
            item['traits'] = parse_json_list(item.pop('traits_json', '[]'))
            item['profile'] = parse_json_dict(item.pop('profile_json', '{}'))
            item['notes'] = item.get('notes') or ''
            item['is_manual'] = int(item.get('is_manual') or 0)
            if not item['profile']:
                first_seen = f"第 {item['first_chapter_index'] + 1} 章" if item.get('first_chapter_index') is not None else ''
                item['profile'] = {
                    'summary': item.get('description') or '',
                    'appearance': '',
                    'personality': item.get('traits') or [],
                    'motivation': '',
                    'skills': [],
                    'first_seen': first_seen,
                    'card_evidence': item.get('evidence') or '',
                }
            characters.append(item)

        cursor.execute('''
            SELECT r.*,
                   sc.name AS source_name,
                   tc.name AS target_name
            FROM novel_character_relations r
            JOIN novel_characters sc ON r.source_character_id = sc.id
            JOIN novel_characters tc ON r.target_character_id = tc.id
            WHERE r.novel_id = ?
            ORDER BY r.sort_order ASC, r.id ASC
        ''', (novel_id,))
        relations = []
        for row in cursor.fetchall():
            relation = dict(row)
            relation['is_manual'] = int(relation.get('is_manual') or 0)
            relations.append(relation)
        conn.close()

        run_data = dict(run) if run else None
        status = (run_data or {}).get('status') or ('completed' if characters or relations else 'empty')
        return {
            'novel_id': novel_id,
            'analysis_status': status,
            'analyzed_at': (run_data or {}).get('finished_at') or (run_data or {}).get('updated_at'),
            'error_message': (run_data or {}).get('error_message'),
            'character_count': len(characters),
            'relation_count': len(relations),
            'characters': characters,
            'relations': relations,
        }


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


    def mark_character_analysis_failed(novel_id, error_message, *, model='', source_excerpt_chars=0):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO novel_character_analysis_runs (
                novel_id, status, model, character_count, relation_count,
                source_excerpt_chars, error_message, updated_at
            ) VALUES (?, 'failed', ?, 0, 0, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(novel_id) DO UPDATE SET
                status = 'failed',
                model = excluded.model,
                source_excerpt_chars = excluded.source_excerpt_chars,
                error_message = excluded.error_message,
                updated_at = CURRENT_TIMESTAMP
        ''', (novel_id, model, source_excerpt_chars, error_message[:500]))
        conn.commit()
        conn.close()


    def normalize_ai_tag_names(raw_tags):
        """清洗 AI 返回的标签名称。"""
        if isinstance(raw_tags, str):
            candidates = re.split(r'[,，、/\n]+', raw_tags)
        elif isinstance(raw_tags, list):
            candidates = []
            for item in raw_tags:
                if isinstance(item, str):
                    candidates.extend(re.split(r'[,，、/\n]+', item))
        else:
            candidates = []

        normalized = []
        seen = set()
        for item in candidates:
            name = (item or '').strip()
            name = re.sub(r'^[#\s\-\*\.]+|[#\s\-\*\.]+$', '', name)
            name = re.sub(r'["\'\[\]{}()<>《》“”]', '', name)
            name = name.replace('（', '').replace('）', '')
            name = name[:20].strip()
            if len(name) < 2:
                continue
            lower_name = name.lower()
            if lower_name in seen:
                continue
            seen.add(lower_name)
            normalized.append(name)
            if len(normalized) >= 8:
                break

        return normalized


    def get_ai_tag_color(tag_name):
        """根据标签名称稳定生成颜色。"""
        if not tag_name:
            return '#3498db'
        color_index = sum(ord(char) for char in tag_name) % len(AI_TAG_COLOR_PALETTE)
        return AI_TAG_COLOR_PALETTE[color_index]


    def ensure_tags_exist(tag_names):
        """确保标签存在，不存在时自动创建。"""
        clean_names = normalize_ai_tag_names(tag_names)
        if not clean_names:
            return []

        conn = get_db()
        cursor = conn.cursor()
        tag_records = []

        try:
            for tag_name in clean_names:
                cursor.execute(
                    'SELECT id, name, color FROM tags WHERE name = ? COLLATE NOCASE LIMIT 1',
                    (tag_name,)
                )
                tag_row = cursor.fetchone()
                if tag_row:
                    tag_records.append(dict(tag_row))
                    continue

                color = get_ai_tag_color(tag_name)
                try:
                    cursor.execute(
                        'INSERT INTO tags (name, color) VALUES (?, ?)',
                        (tag_name, color)
                    )
                    tag_records.append({
                        'id': cursor.lastrowid,
                        'name': tag_name,
                        'color': color
                    })
                except sqlite3.IntegrityError:
                    cursor.execute(
                        'SELECT id, name, color FROM tags WHERE name = ? COLLATE NOCASE LIMIT 1',
                        (tag_name,)
                    )
                    existing_row = cursor.fetchone()
                    if existing_row:
                        tag_records.append(dict(existing_row))

            conn.commit()
            return tag_records
        finally:
            conn.close()


    def build_novel_ai_messages(title, author, category_name, description, existing_tags, content_excerpt):
        """构建小说简介与标签生成提示词。"""
        context_blocks = [
            f'标题：{title or "未提供"}',
            f'作者：{author or "未提供"}',
            f'分类：{category_name or "未分类"}',
            f'已有简介：{description or "无"}',
            f'已有标签：{"、".join(existing_tags) if existing_tags else "无"}'
        ]

        if content_excerpt:
            context_blocks.append(f'正文片段：\n{content_excerpt[:4000]}')

        user_prompt = '\n\n'.join(context_blocks) + textwrap.dedent("""

    请根据以上信息，生成小说的标签和简介。

    要求：
    1. 只输出一个 JSON 对象，不要输出 Markdown。
    2. JSON 格式必须为：{"summary":"...","tags":["标签1","标签2"]}
    3. summary 使用中文，控制在 70 到 140 个汉字，语气自然，适合展示在书库卡片里。
    4. tags 返回 3 到 6 个简短标签，优先输出题材、风格、世界观、受众、节奏类标签。
    5. 信息不足时可以概括，但不要编造具体情节、人物或结局。
    6. 标签不要重复，不要带序号，不要带解释。
    """)

        return [
            {
                'role': 'system',
                'content': '你是一个小说资料整理助手，擅长为书库生成简洁简介和标签。'
            },
            {
                'role': 'user',
                'content': user_prompt.strip()
            }
        ]


    def build_novel_ai_request_context(data):
        """构建小说 AI 元数据请求上下文。"""
        payload = data or {}
        novel_id = payload.get('novel_id')
        base_novel = get_novel_detail_record(novel_id) if novel_id else None

        title = (payload.get('title') or (base_novel or {}).get('title') or '').strip()
        author = (payload.get('author') or (base_novel or {}).get('author') or '').strip()
        description = (payload.get('description') or (base_novel or {}).get('description') or '').strip()
        file_path = (payload.get('file_path') or (base_novel or {}).get('file_path') or '').strip()
        category_id = payload.get('category_id')
        category_name = (payload.get('category_name') or '').strip()

        if not category_name:
            if category_id:
                category_name = get_category_name_by_id(category_id)
            elif base_novel:
                category_name = (base_novel.get('category_name') or '').strip()

        tag_ids = payload.get('tag_ids')
        if tag_ids is None and base_novel:
            tag_ids = [tag['id'] for tag in base_novel.get('tags', [])]

        existing_tags = get_tag_names_by_ids(tag_ids or [])
        if not existing_tags and base_novel:
            existing_tags = [tag['name'] for tag in base_novel.get('tags', [])]

        content_excerpt = (payload.get('content_excerpt') or '').strip()
        if not content_excerpt:
            content_excerpt = extract_text_excerpt(file_path)

        return {
            'novel_id': novel_id,
            'base_novel': base_novel,
            'title': title,
            'author': author,
            'description': description,
            'file_path': file_path,
            'category_id': category_id,
            'category_name': category_name,
            'tag_ids': tag_ids or [],
            'existing_tags': existing_tags,
            'content_excerpt': content_excerpt,
        }


    def build_novel_ai_messages_from_context(context):
        """从小说 AI 请求上下文构建消息。"""
        return build_novel_ai_messages(
            title=context.get('title', ''),
            author=context.get('author', ''),
            category_name=context.get('category_name', ''),
            description=context.get('description', ''),
            existing_tags=context.get('existing_tags', []),
            content_excerpt=context.get('content_excerpt', '')
        )


    def should_fetch_gemini_safety_feedback(error_message):
        """判断当前错误是否值得额外请求 Gemini 原生安全反馈。"""
        normalized = (error_message or '').strip().lower()
        if not normalized:
            return False

        keywords = (
            '内容策略', '未返回内容', '空消息',
            'content_filter', 'prohibited_content', 'safety'
        )
        return any(keyword in normalized for keyword in keywords)


    def collect_novel_metadata_safety_feedback(messages, config=None):
        """使用 Gemini 原生接口获取官方安全反馈。"""
        native_client = get_native_gemini_client(config)
        if not native_client:
            return None

        feedback = native_client.get_safety_feedback(messages)
        if not feedback:
            return None

        return feedback


    def build_ai_test_config(data):
        """根据表单数据构建可测试的 AI 配置，支持未保存配置。"""
        payload = data or {}
        config_id = payload.get('id')
        existing_config = None

        if str(config_id).isdigit():
            existing_config = AIConfig.get_config(int(config_id))

        config = dict(existing_config or {})

        for field in ('name', 'provider', 'api_base', 'model', 'proxy_url'):
            value = payload.get(field)
            if value is not None:
                config[field] = value

        for field in ('temperature', 'max_tokens'):
            value = payload.get(field)
            if value is not None and value != '':
                config[field] = value

        if 'use_proxy' in payload:
            config['use_proxy'] = payload.get('use_proxy')

        api_key = payload.get('api_key')
        if isinstance(api_key, str):
            api_key = api_key.strip()
            if api_key and not api_key.startswith('***'):
                config['api_key'] = api_key
        elif api_key is not None:
            config['api_key'] = api_key

        return config


    def run_ai_config_test(config):
        """执行 AI 配置测试，并附带可选模型列表。"""
        client = AIClientFactory.create_client(config)
        success, message = client.test_connection()

        models = []
        model_discovery_message = ''
        if success:
            try:
                models = AIClientFactory.discover_models(config)
            except Exception as exc:
                model_discovery_message = str(exc)

        return {
            'success': success,
            'message': message,
            'data': {
                'models': models,
                'model_discovery_message': model_discovery_message,
                'model_count': len(models)
            }
        }

    @app.route('/api/ai/providers', methods=['GET'])
    def get_ai_providers():
        """获取可用的 AI 提供商列表"""
        return jsonify({
            'success': True,
            'data': AIClientFactory.get_available_providers()
        })


    @app.route('/api/ai/configs', methods=['GET'])
    def get_ai_configs():
        """获取所有 AI 配置"""
        configs = AIConfig.get_all_configs()

        # 隐藏 API 密钥
        for config in configs:
            if config.get('api_key'):
                config['api_key'] = '***' + config['api_key'][-4:]

        return jsonify({'success': True, 'data': configs})


    @app.route('/api/ai/configs/<int:config_id>', methods=['GET'])
    def get_ai_config(config_id):
        """获取指定 AI 配置"""
        config = AIConfig.get_config(config_id)

        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        # 隐藏 API 密钥
        if config.get('api_key'):
            config['api_key'] = '***' + config['api_key'][-4:]

        return jsonify({'success': True, 'data': config})


    @app.route('/api/ai/configs', methods=['POST'])
    def create_ai_config():
        """创建 AI 配置"""
        data = request.json

        if not data.get('name'):
            return jsonify({'success': False, 'message': '配置名称不能为空'}), 400

        if not data.get('provider'):
            return jsonify({'success': False, 'message': '提供商不能为空'}), 400

        try:
            config_id = AIConfig.save_config(data)
            return jsonify({'success': True, 'data': {'id': config_id}})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


    @app.route('/api/ai/configs/<int:config_id>', methods=['PUT'])
    def update_ai_config(config_id):
        """更新 AI 配置"""
        data = request.json
        data['id'] = config_id

        try:
            AIConfig.save_config(data)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


    @app.route('/api/ai/configs/<int:config_id>', methods=['DELETE'])
    def delete_ai_config(config_id):
        """删除 AI 配置"""
        try:
            AIConfig.delete_config(config_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


    @app.route('/api/ai/configs/<int:config_id>/activate', methods=['POST'])
    def activate_ai_config(config_id):
        """激活 AI 配置"""
        try:
            AIConfig.set_active_config(config_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


    @app.route('/api/ai/configs/<int:config_id>/test', methods=['POST'])
    def test_ai_config(config_id):
        """测试 AI 配置"""
        config = AIConfig.get_config(config_id)

        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        try:
            return jsonify(run_ai_config_test(config))
        except (ValueError, RuntimeError) as e:
            return jsonify({'success': False, 'message': str(e)}), 422
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


    @app.route('/api/ai/configs/test', methods=['POST'])
    def test_ai_config_payload():
        """测试当前表单中的 AI 配置，并返回可选模型。"""
        data = request.get_json(silent=True) or {}
        config = build_ai_test_config(data)

        if not config.get('provider'):
            return jsonify({'success': False, 'message': '请选择 AI 提供商'}), 400

        if not config.get('model'):
            return jsonify({'success': False, 'message': '请输入模型名称'}), 400

        requires_api_key = config.get('provider') not in ['ollama']
        if requires_api_key and not config.get('api_key'):
            return jsonify({'success': False, 'message': '请输入 API Key'}), 400

        try:
            return jsonify(run_ai_config_test(config))
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


    @app.route('/api/ai/chat', methods=['POST'])
    def ai_chat():
        """AI 聊天接口"""
        data = request.json
        messages = data.get('messages', [])

        if not messages:
            return jsonify({'success': False, 'message': '消息不能为空'}), 400

        client = get_ai_client()

        if not client:
            return jsonify({'success': False, 'message': 'AI 客户端未配置或配置无效'}), 400

        try:
            response = client.chat(messages, stream=False)
            return jsonify({'success': True, 'data': {'response': response}})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


    @app.route('/api/ai/novels/<int:novel_id>/reader-assistant', methods=['POST'])
    def reader_assistant_chat(novel_id):
        data = request.get_json(silent=True)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': '请求内容必须是 JSON 对象'}), 400

        question = normalize_reader_assistant_question(data.get('question'))
        if not question:
            return jsonify({'success': False, 'message': '问题不能为空'}), 400

        novel = get_novel_detail_record(novel_id)
        if not novel:
            return jsonify({'success': False, 'message': '小说不存在'}), 404

        client = get_ai_client()
        if not client:
            return jsonify({'success': False, 'message': '请先在 AI 配置中激活可用模型'}), 400

        try:
            chapter_index = data.get('chapter_index')
            chapter_index = int(chapter_index) if chapter_index is not None else None
        except (TypeError, ValueError):
            chapter_index = None

        try:
            novel_context = build_ai_context_for_novel(novel, focus_chapter_index=chapter_index)
            messages = build_reader_assistant_messages(
                novel_context,
                question=question,
                chapter_index=chapter_index,
                chapter_title=str(data.get('chapter_title') or '').strip(),
                conversation=data.get('conversation') if isinstance(data.get('conversation'), list) else [],
            )
            answer = client.chat(messages, stream=False)
            return jsonify({
                'success': True,
                'data': {
                    'answer': answer,
                    'context': summarize_novel_ai_context(novel_context),
                },
            })
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


    @app.route('/api/novels/<int:novel_id>/characters', methods=['GET'])
    def get_novel_character_analysis(novel_id):
        """获取单本小说的角色和关系分析结果。"""
        novel = get_novel_detail_record(novel_id)
        if not novel:
            return jsonify({'success': False, 'message': '小说不存在'}), 404

        return jsonify({
            'success': True,
            'data': serialize_character_analysis(novel_id)
        })


    @app.route('/api/novels/<int:novel_id>/settings', methods=['GET'])
    def get_novel_setting_analysis(novel_id):
        """获取单本小说的设定提取结果。"""
        novel = get_novel_detail_record(novel_id)
        if not novel:
            return jsonify({'success': False, 'message': '小说不存在'}), 404

        return jsonify({
            'success': True,
            'data': serialize_setting_analysis(novel_id)
        })


    @app.route('/api/novels/<int:novel_id>/writing-style', methods=['GET'])
    def get_novel_writing_style_analysis(novel_id):
        """Get a single novel's writing style analysis."""
        novel = get_novel_detail_record(novel_id)
        if not novel:
            return jsonify({'success': False, 'message': '小说不存在'}), 404

        return jsonify({
            'success': True,
            'data': serialize_writing_style_analysis(novel_id)
        })


    @app.route('/api/ai/novels/<int:novel_id>/characters/analyze', methods=['POST'])
    def analyze_novel_characters(novel_id):
        """使用 AI 分析单本小说角色和角色关系。"""
        novel = get_novel_detail_record(novel_id)
        if not novel:
            return jsonify({'success': False, 'message': '小说不存在'}), 404

        novel_context = build_ai_context_for_novel(novel)
        if not has_usable_novel_ai_context(novel, novel_context):
            return jsonify({'success': False, 'message': '请先填写书名，或提供可读取的 TXT/EPUB 文件'}), 400

        client = get_ai_client()
        if not client:
            return jsonify({'success': False, 'message': '请先在 AI 配置中激活可用模型'}), 400

        active_config = AIConfig.get_active_config() or {}
        model = active_config.get('model') or ''
        messages = build_character_analysis_messages(novel, novel_context)

        try:
            response_text = client.chat(messages, stream=False)
            response_data = extract_json_object(response_text)
            characters, relations = normalize_character_analysis_payload(response_data)

            if not characters:
                error_message = 'AI 未识别到可用角色卡，请换更多正文内容后重试'
                mark_character_analysis_failed(
                    novel_id,
                    error_message,
                    model=model,
                    source_excerpt_chars=novel_context['included_chars']
                )
                return jsonify({'success': False, 'message': error_message}), 500

            analysis = replace_character_analysis(
                novel_id,
                characters,
                relations,
                model=model,
                source_excerpt_chars=novel_context['included_chars']
            )
            analysis['used_excerpt'] = bool(novel_context.get('content_text'))
            analysis['context'] = summarize_novel_ai_context(novel_context)
            return jsonify({'success': True, 'data': analysis})
        except (ValueError, RuntimeError) as e:
            error_message = str(e)
            mark_character_analysis_failed(
                novel_id,
                error_message,
                model=model,
                source_excerpt_chars=novel_context['included_chars']
            )
            return jsonify({'success': False, 'message': error_message}), 422
        except Exception as e:
            error_message = str(e)
            mark_character_analysis_failed(
                novel_id,
                error_message,
                model=model,
                source_excerpt_chars=novel_context['included_chars']
            )
            return jsonify({'success': False, 'message': error_message}), 500


    @app.route('/api/ai/novels/<int:novel_id>/settings/analyze', methods=['POST'])
    def analyze_novel_settings(novel_id):
        """使用 AI 提取单本小说设定。"""
        novel = get_novel_detail_record(novel_id)
        if not novel:
            return jsonify({'success': False, 'message': '小说不存在'}), 404

        novel_context = build_ai_context_for_novel(novel)
        if not has_usable_novel_ai_context(novel, novel_context):
            return jsonify({'success': False, 'message': '请先填写书名，或提供可读取的 TXT/EPUB 文件'}), 400

        client = get_ai_client()
        if not client:
            return jsonify({'success': False, 'message': '请先在 AI 配置中激活可用模型'}), 400

        active_config = AIConfig.get_active_config() or {}
        model = active_config.get('model') or ''
        messages = build_setting_analysis_messages(novel, novel_context)

        try:
            response_text = client.chat(messages, stream=False)
            response_data = extract_json_object(response_text)
            settings = normalize_setting_analysis_payload(response_data)

            if not settings:
                error_message = 'AI 未识别到可用小说设定，请换更多正文内容后重试'
                mark_setting_analysis_failed(
                    novel_id,
                    error_message,
                    model=model,
                    source_excerpt_chars=novel_context['included_chars']
                )
                return jsonify({'success': False, 'message': error_message}), 500

            analysis = replace_setting_analysis(
                novel_id,
                settings,
                model=model,
                source_excerpt_chars=novel_context['included_chars']
            )
            analysis['used_excerpt'] = bool(novel_context.get('content_text'))
            analysis['context'] = summarize_novel_ai_context(novel_context)
            return jsonify({'success': True, 'data': analysis})
        except (ValueError, RuntimeError) as e:
            error_message = str(e)
            mark_setting_analysis_failed(
                novel_id,
                error_message,
                model=model,
                source_excerpt_chars=novel_context['included_chars']
            )
            return jsonify({'success': False, 'message': error_message}), 422
        except Exception as e:
            error_message = str(e)
            mark_setting_analysis_failed(
                novel_id,
                error_message,
                model=model,
                source_excerpt_chars=novel_context['included_chars']
            )
            return jsonify({'success': False, 'message': error_message}), 500


    @app.route('/api/ai/novels/<int:novel_id>/writing-style/analyze', methods=['POST'])
    def analyze_novel_writing_style(novel_id):
        """Use AI to analyze a single novel's writing style."""
        novel = get_novel_detail_record(novel_id)
        if not novel:
            return jsonify({'success': False, 'message': '小说不存在'}), 404

        novel_context = build_ai_context_for_novel(novel)
        if not has_usable_novel_ai_context(novel, novel_context):
            return jsonify({'success': False, 'message': '请先填写书名，或提供可读取的 TXT/EPUB 文件'}), 400

        client = get_ai_client()
        if not client:
            return jsonify({'success': False, 'message': '请先在 AI 配置中激活可用模型'}), 400

        active_config = AIConfig.get_active_config() or {}
        model = active_config.get('model') or ''
        messages = build_writing_style_analysis_messages(novel, novel_context)

        try:
            response_text = client.chat(messages, stream=False)
            response_data = extract_json_object(response_text)
            style = normalize_writing_style_analysis_payload(response_data)

            if not has_writing_style_content(style):
                error_message = 'AI 未识别到可用写作风格，请换更多正文内容后重试'
                mark_writing_style_analysis_failed(
                    novel_id,
                    error_message,
                    model=model,
                    source_excerpt_chars=novel_context['included_chars']
                )
                return jsonify({'success': False, 'message': error_message}), 500

            analysis = replace_writing_style_analysis(
                novel_id,
                style,
                model=model,
                source_excerpt_chars=novel_context['included_chars']
            )
            analysis['used_excerpt'] = bool(novel_context.get('content_text'))
            analysis['context'] = summarize_novel_ai_context(novel_context)
            return jsonify({'success': True, 'data': analysis})
        except (ValueError, RuntimeError) as e:
            error_message = str(e)
            mark_writing_style_analysis_failed(
                novel_id,
                error_message,
                model=model,
                source_excerpt_chars=novel_context['included_chars']
            )
            return jsonify({'success': False, 'message': error_message}), 422
        except Exception as e:
            error_message = str(e)
            mark_writing_style_analysis_failed(
                novel_id,
                error_message,
                model=model,
                source_excerpt_chars=novel_context['included_chars']
            )
            return jsonify({'success': False, 'message': error_message}), 500


    @app.route('/api/ai/novels/metadata/feedback', methods=['POST'])
    def get_novel_metadata_feedback():
        """Use Gemini native API to fetch official safety feedback for metadata generation."""
        data = request.get_json(silent=True) or {}
        context = build_novel_ai_request_context(data)

        if not context['title'] and not context['description'] and not context['content_excerpt']:
            return jsonify({'success': False, 'message': '\u8bf7\u5148\u586b\u5199\u4e66\u540d\uff0c\u6216\u63d0\u4f9b\u53ef\u8bfb\u53d6\u7684\u6587\u672c\u5185\u5bb9'}), 400

        active_config = AIConfig.get_active_config()
        if not is_gemini_compatible_config(active_config):
            return jsonify({'success': False, 'message': '\u5f53\u524d\u6fc0\u6d3b\u914d\u7f6e\u4e0d\u662f Gemini\uff0c\u65e0\u6cd5\u83b7\u53d6\u5b98\u65b9\u5b89\u5168\u53cd\u9988'}), 400

        messages = build_novel_ai_messages_from_context(context)

        try:
            feedback = collect_novel_metadata_safety_feedback(messages, active_config)
            if not feedback:
                return jsonify({'success': False, 'message': 'Gemini \u539f\u751f\u63a5\u53e3\u672a\u8fd4\u56de\u5b89\u5168\u53cd\u9988'}), 500
            return jsonify({'success': True, 'data': feedback})
        except (ValueError, RuntimeError) as e:
            return jsonify({'success': False, 'message': str(e)}), 422
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


    @app.route('/api/ai/novels/metadata', methods=['POST'])
    def generate_novel_metadata():
        """Use AI to generate novel summary and tags."""
        data = request.get_json(silent=True) or {}
        context = build_novel_ai_request_context(data)

        if not context['title'] and not context['description'] and not context['content_excerpt']:
            return jsonify({'success': False, 'message': '\u8bf7\u5148\u586b\u5199\u4e66\u540d\uff0c\u6216\u63d0\u4f9b\u53ef\u8bfb\u53d6\u7684\u6587\u672c\u5185\u5bb9'}), 400

        active_config = AIConfig.get_active_config()
        client = get_ai_client()
        if not client:
            return jsonify({'success': False, 'message': '\u8bf7\u5148\u5728 AI \u914d\u7f6e\u4e2d\u6fc0\u6d3b\u53ef\u7528\u6a21\u578b'}), 400

        messages = build_novel_ai_messages_from_context(context)

        try:
            response_text = client.chat(messages, stream=False)
            response_data = extract_json_object(response_text)

            summary = str(response_data.get('summary', '')).strip()
            summary = re.sub(r'\s+', ' ', summary)
            summary = summary.strip('\"')

            tag_names = normalize_ai_tag_names(response_data.get('tags', []))
            tag_records = ensure_tags_exist(tag_names)

            if not summary and not tag_records:
                return jsonify({'success': False, 'message': 'AI \u672a\u751f\u6210\u53ef\u7528\u7684\u7b80\u4ecb\u6216\u6807\u7b7e\uff0c\u8bf7\u91cd\u8bd5'}), 500

            return jsonify({
                'success': True,
                'data': {
                    'summary': summary,
                    'tags': tag_records,
                    'tag_names': [tag['name'] for tag in tag_records],
                    'used_excerpt': bool(context['content_excerpt'])
                }
            })
        except (ValueError, RuntimeError) as e:
            error_message = str(e)
            response_payload = {
                'success': False,
                'message': error_message
            }

            if is_gemini_compatible_config(active_config) and should_fetch_gemini_safety_feedback(error_message):
                try:
                    feedback = collect_novel_metadata_safety_feedback(messages, active_config)
                    if feedback:
                        response_payload['details'] = {
                            'safety_feedback': feedback
                        }
                        if feedback.get('summary') and feedback['summary'] not in error_message:
                            response_payload['details']['display_message'] = f"{error_message} | Gemini safety: {feedback['summary']}"
                except Exception as feedback_error:
                    response_payload['details'] = {
                        'safety_feedback_error': str(feedback_error)
                    }

            return jsonify(response_payload), 422
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
