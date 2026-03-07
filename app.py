"""
??????? - Flask??
"""
import json
import os
import sqlite3
import re
import html
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import requests

# ??????????
NOVEL_EXTENSIONS = {'.txt', '.epub', '.pdf', '.mobi', '.azw3', '.doc', '.docx', '.rtf'}

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

DATABASE = 'novels.db'
APP_ROOT = Path(__file__).resolve().parent
UPLOAD_ROOT = APP_ROOT / 'library'
TEXT_READABLE_EXTENSIONS = {'.txt'}
CRAWLER_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0 Safari/537.36'
CRAWLER_STATUSES = {'pending', 'running', 'completed', 'failed'}

crawler_threads = {}
crawler_threads_lock = threading.Lock()


def get_db():
    """???????"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    """???????"""
    conn = get_db()
    cursor = conn.cursor()
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    # ???
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            description TEXT,
            file_path TEXT,
            category_id INTEGER,
            cover_path TEXT,
            status INTEGER DEFAULT 0,  -- 0:?? 1:??? 2:???
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')

    # ???
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ???
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#3498db',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ??-?????
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novel_tags (
            novel_id INTEGER,
            tag_id INTEGER,
            PRIMARY KEY (novel_id, tag_id),
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_novels_file_path ON novels(file_path)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_novels_category_status_updated ON novels(category_id, status, updated_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_novel_tags_tag_novel ON novel_tags(tag_id, novel_id)')
    cursor.execute('''
        DELETE FROM novel_tags
        WHERE novel_id NOT IN (SELECT id FROM novels)
           OR tag_id NOT IN (SELECT id FROM tags)
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawler_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            title TEXT,
            author TEXT,
            description TEXT,
            category_id INTEGER,
            tag_ids_json TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            total_chapters INTEGER DEFAULT 0,
            crawled_chapters INTEGER DEFAULT 0,
            novel_id INTEGER,
            file_path TEXT,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE SET NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_crawler_tasks_status_updated ON crawler_tasks(status, updated_at DESC)')

    conn.commit()
    conn.close()


def sanitize_storage_name(name):
    """???????????????????"""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', (name or '').strip())
    cleaned = cleaned.strip(' .')
    return cleaned or 'untitled'


def sanitize_relative_storage_path(relative_path, fallback_name='untitled.txt'):
    """????????????????"""
    normalized = (relative_path or fallback_name).replace('\\', '/')
    raw_parts = Path(normalized).parts
    safe_parts = []

    for part in raw_parts:
        if part in ('', '.', '..'):
            continue
        safe_parts.append(sanitize_storage_name(part))

    if not safe_parts:
        safe_parts.append(sanitize_storage_name(fallback_name))

    return Path(*safe_parts)


def is_supported_novel_file(file_name):
    return Path(file_name or '').suffix.lower() in NOVEL_EXTENSIONS


def store_uploaded_file(file_storage, relative_path=None, namespace='manual', reuse_existing=False):
    """????????????????????"""
    original_name = Path(file_storage.filename or 'untitled.txt').name
    target_rel = Path(namespace) / sanitize_relative_storage_path(relative_path, original_name)
    target_abs = UPLOAD_ROOT / target_rel
    target_abs.parent.mkdir(parents=True, exist_ok=True)

    if reuse_existing and target_abs.exists():
        return str(Path('library') / target_rel).replace('\\', '/')

    final_rel = target_rel
    final_abs = target_abs
    counter = 1
    while not reuse_existing and final_abs.exists():
        final_rel = target_rel.with_name(f'{target_rel.stem}_{counter}{target_rel.suffix}')
        final_abs = UPLOAD_ROOT / final_rel
        counter += 1

    file_storage.save(final_abs)
    return str(Path('library') / final_rel).replace('\\', '/')


def resolve_novel_file_path(file_path):
    """????????????"""
    if not file_path:
        return None, []

    file_path_normalized = file_path.replace('/', os.sep).replace('\\\\', os.sep)
    possible_paths = [
        file_path,
        file_path_normalized,
        os.path.join(os.getcwd(), file_path),
        os.path.join(os.getcwd(), file_path_normalized),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path_normalized),
    ]

    possible_paths = list(dict.fromkeys(possible_paths))
    checked_paths = []

    for path in possible_paths:
        checked_paths.append(path)
        if os.path.exists(path) and os.path.isfile(path):
            return path, checked_paths

    return None, checked_paths


def is_text_readable_file(file_path):
    return Path(file_path or '').suffix.lower() in TEXT_READABLE_EXTENSIONS


def _normalize_novel_ids(novel_ids):
    normalized = []
    seen = set()

    for novel_id in novel_ids or []:
        try:
            current_id = int(novel_id)
        except (TypeError, ValueError):
            continue

        if current_id <= 0 or current_id in seen:
            continue

        seen.add(current_id)
        normalized.append(current_id)

    return normalized


def _cleanup_empty_parent_dirs(file_path):
    try:
        upload_root = UPLOAD_ROOT.resolve()
        current = Path(file_path).resolve().parent
    except Exception:
        return

    while current != upload_root and upload_root in current.parents:
        try:
            next(current.iterdir())
            break
        except StopIteration:
            current.rmdir()
            current = current.parent
        except OSError:
            break


def _collect_novel_file_deletion_targets(cursor, novel_ids):
    normalized_ids = _normalize_novel_ids(novel_ids)
    if not normalized_ids:
        return [], [], set()

    placeholders = ','.join(['?' for _ in normalized_ids])
    cursor.execute(
        f'SELECT id, title, file_path FROM novels WHERE id IN ({placeholders})',
        normalized_ids
    )
    rows = cursor.fetchall()

    file_paths = sorted({row['file_path'] for row in rows if row['file_path']})
    if not file_paths:
        return rows, [], set()

    file_placeholders = ','.join(['?' for _ in file_paths])
    cursor.execute(
        f'''SELECT file_path, COUNT(*) AS ref_count
            FROM novels
            WHERE file_path IN ({file_placeholders})
              AND id NOT IN ({placeholders})
            GROUP BY file_path''',
        file_paths + normalized_ids
    )
    shared_paths = {row['file_path'] for row in cursor.fetchall() if row['ref_count'] > 0}
    deletion_targets = [file_path for file_path in file_paths if file_path not in shared_paths]
    return rows, deletion_targets, shared_paths


def _delete_novel_files(file_paths):
    result = {
        'deleted': [],
        'missing': [],
        'failed': []
    }

    for file_path in file_paths:
        actual_path, _ = resolve_novel_file_path(file_path)
        if not actual_path:
            result['missing'].append(file_path)
            continue

        try:
            os.remove(actual_path)
            result['deleted'].append({'file_path': file_path, 'actual_path': actual_path})
            _cleanup_empty_parent_dirs(actual_path)
        except Exception as exc:
            result['failed'].append({
                'file_path': file_path,
                'actual_path': actual_path,
                'error': str(exc)
            })

    return result


def _build_file_delete_error_message(failed_items):
    preview = []
    for item in failed_items[:3]:
        preview.append(f"{item['file_path']}: {item['error']}")
    return '?????????' + '?'.join(preview)


def parse_import_request():
    """??????????? JSON ? multipart/form-data"""
    if request.files:
        try:
            novels = json.loads(request.form.get('novels', '[]'))
            tag_ids = json.loads(request.form.get('tag_ids', '[]'))
        except json.JSONDecodeError:
            raise ValueError('导入数据格式无效')

        default_status = int(request.form.get('default_status', 0))
        files = request.files.getlist('files')
        relative_paths = request.form.getlist('relative_paths')

        if len(files) != len(novels):
            raise ValueError('上传文件数量和导入条目不一致')

        prepared_novels = []
        for index, file_storage in enumerate(files):
            if not file_storage or not file_storage.filename:
                raise ValueError('存在未选择的导入文件')

            relative_path = relative_paths[index] if index < len(relative_paths) else file_storage.filename
            if not is_supported_novel_file(relative_path):
                raise ValueError(f'不支持的文件格式: {relative_path}')

            stored_path = store_uploaded_file(
                file_storage,
                relative_path=relative_path,
                namespace='imports',
                reuse_existing=True
            )

            novel_data = dict(novels[index])
            novel_data['file_path'] = stored_path
            prepared_novels.append(novel_data)

        return prepared_novels, tag_ids, default_status

    data = request.get_json(silent=True) or {}
    novels = data.get('novels', [])
    tag_ids = data.get('tag_ids', [])
    default_status = data.get('default_status', 0)
    return novels, tag_ids, default_status

@app.route('/')
def index():
    return render_template('index.html')


# ==================== API: 小说管理 ====================

@app.route('/api/novels', methods=['GET'])
def get_novels():
    """获取小说列表，支持搜索和筛选"""
    conn = get_db()
    cursor = conn.cursor()

    # 查询参数
    keyword = request.args.get('keyword', '')
    category_id = request.args.get('category_id', '')
    tag_ids = request.args.getlist('tag_ids')
    status = request.args.get('status', '')

    query = '''
        SELECT n.*, c.name as category_name
        FROM novels n
        LEFT JOIN categories c ON n.category_id = c.id
        WHERE 1=1
    '''
    params = []

    if keyword:
        query += ' AND (n.title LIKE ? OR n.author LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%'])

    if category_id:
        query += ' AND n.category_id = ?'
        params.append(category_id)

    if status:
        query += ' AND n.status = ?'
        params.append(status)

    # 如果有标签筛选，使用子查询
    if tag_ids:
        # 将tag_ids转换为整数列表
        tag_id_list = [int(tid) for tid in tag_ids if tid.isdigit()]
        if tag_id_list:
            placeholders = ','.join(['?' for _ in tag_id_list])
            query += f''' AND n.id IN (
                SELECT novel_id FROM novel_tags
                WHERE tag_id IN ({placeholders})
                GROUP BY novel_id
                HAVING COUNT(DISTINCT tag_id) = ?
            )'''
            params.extend(tag_id_list)
            params.append(len(tag_id_list))

    query += ' ORDER BY n.updated_at DESC'

    cursor.execute(query, params)
    novels = [dict(row) for row in cursor.fetchall()]

    # 获取每本小说的标签
    for novel in novels:
        cursor.execute('''
            SELECT t.id, t.name, t.color
            FROM tags t
            JOIN novel_tags nt ON t.id = nt.tag_id
            WHERE nt.novel_id = ?
        ''', (novel['id'],))
        novel['tags'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify({'success': True, 'data': novels})


# ==================== 小说阅读功能 ====================

import re
import os

# 章节识别正则表达式模式
CHAPTER_PATTERNS = [
    # 第X章/回/节/集/卷
    r'^(第[\s]*[零一二三四五六七八九十百千万\d]+[\s]*[章回节集卷])',
    # Chapter X / CHAPTER X
    r'^(Chapter[\s]+\d+)',  # 英文章节
    # 数字开头 + 章节名
    r'^(\d+[\.\s、]+[^\n]+)',
    # 第X章：标题
    r'^(第[\s]*[零一二三四五六七八九十百千万\d]+[\s]*[章回节集卷][：:].+)',
    # 【第X章】
    r'^[【\[](第[\s]*[零一二三四五六七八九十百千万\d]+[\s]*[章回节集卷])[】\]]',
]


def detect_encoding(file_path):
    """检测文件编码"""
    import chardet
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        return result['encoding'] or 'utf-8'


def parse_chapters(content):
    """解析章节"""
    chapters = []
    lines = content.split('\n')

    # 合并所有模式
    combined_pattern = '|'.join(f'({p})' for p in CHAPTER_PATTERNS)
    chapter_regex = re.compile(combined_pattern, re.IGNORECASE)

    current_chapter = None
    current_content = []

    for line_num, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # 检查是否是章节标题
        match = chapter_regex.match(line)
        if match:
            # 保存上一章节
            if current_chapter:
                current_chapter['content'] = '\n'.join(current_content)
                chapters.append(current_chapter)

            # 开始新章节
            current_chapter = {
                'title': line,
                'content': '',
                'line_num': line_num
            }
            current_content = []
        else:
            if current_chapter:
                current_content.append(line)

    # 保存最后一章
    if current_chapter:
        current_chapter['content'] = '\n'.join(current_content)
        chapters.append(current_chapter)

    # 如果没有识别到章节，将全文作为一章
    if not chapters and content.strip():
        chapters = [{
            'title': '全文',
            'content': content.strip(),
            'line_num': 0
        }]

    return chapters


@app.route('/api/novels/<int:novel_id>/read', methods=['GET'])
def read_novel(novel_id):
    """获取小说阅读内容"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM novels WHERE id = ?', (novel_id,))
    novel = cursor.fetchone()
    conn.close()

    if not novel:
        return jsonify({'success': False, 'message': '小说不存在'}), 404

    novel = dict(novel)

    file_path = novel.get('file_path')
    if not file_path:
        return jsonify({'success': False, 'message': '小说未设置文件路径'}), 400

    actual_path, checked_paths = resolve_novel_file_path(file_path)
    if not actual_path:
        return jsonify({
            'success': False,
            'message': f'文件不存在: {file_path}',
            'data': {
                'novel': novel,
                'checked_paths': checked_paths,
                'current_working_dir': os.getcwd(),
                'chapters': [{'title': '文件未找到', 'content': f'请在服务器上确认文件存在:\n{file_path}\n\n已检查路径:\n' + '\n'.join(checked_paths)}]
            }
        }), 404

    if not is_text_readable_file(actual_path):
        return jsonify({
            'success': False,
            'message': '当前仅支持 TXT 文件在线阅读，请使用下载功能打开原文件',
            'data': {'novel': novel, 'checked_paths': checked_paths}
        }), 400

    try:
        encoding = detect_encoding(actual_path)
        with open(actual_path, 'r', encoding=encoding, errors='ignore') as f:
            content = f.read()

        chapters = parse_chapters(content)

        return jsonify({
            'success': True,
            'data': {
                'novel': novel,
                'chapters': [{'title': c['title'], 'line_num': c['line_num']} for c in chapters],
                'total_chars': len(content),
                'encoding': encoding
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'读取文件失败: {str(e)}'}), 500


@app.route('/api/novels/<int:novel_id>/chapters/<int:chapter_index>', methods=['GET'])
def get_chapter_content(novel_id, chapter_index):
    """获取指定章节内容"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM novels WHERE id = ?', (novel_id,))
    novel = cursor.fetchone()
    conn.close()

    if not novel:
        return jsonify({'success': False, 'message': '小说不存在'}), 404

    file_path = novel['file_path']
    if not file_path:
        return jsonify({'success': False, 'message': '小说未设置文件路径'}), 400

    actual_path, _ = resolve_novel_file_path(file_path)
    if not actual_path:
        return jsonify({'success': False, 'message': f'文件不存在: {file_path}'}), 404

    if not is_text_readable_file(actual_path):
        return jsonify({'success': False, 'message': '当前仅支持 TXT 文件在线阅读'}), 400

    try:
        encoding = detect_encoding(actual_path)
        with open(actual_path, 'r', encoding=encoding, errors='ignore') as f:
            content = f.read()

        chapters = parse_chapters(content)

        if chapter_index < 0 or chapter_index >= len(chapters):
            return jsonify({'success': False, 'message': '章节不存在'}), 404

        chapter = chapters[chapter_index]

        return jsonify({
            'success': True,
            'data': {
                'chapter': {
                    'index': chapter_index,
                    'title': chapter['title'],
                    'content': chapter['content'],
                    'total_chapters': len(chapters)
                }
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/novels/<int:novel_id>', methods=['GET'])
def get_novel(novel_id):
    """获取单本小说详情"""
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
        return jsonify({'success': False, 'message': '小说不存在'}), 404

    novel = dict(novel)

    # 获取标签
    cursor.execute('''
        SELECT t.id, t.name, t.color
        FROM tags t
        JOIN novel_tags nt ON t.id = nt.tag_id
        WHERE nt.novel_id = ?
    ''', (novel_id,))
    novel['tags'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify({'success': True, 'data': novel})


@app.route('/api/novels/<int:novel_id>/download', methods=['GET'])
def download_novel(novel_id):
    """下载小说文件"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM novels WHERE id = ?', (novel_id,))
    novel = cursor.fetchone()
    conn.close()

    if not novel:
        return jsonify({'success': False, 'message': '小说不存在'}), 404

    novel = dict(novel)
    file_path = novel.get('file_path')

    if not file_path:
        return jsonify({'success': False, 'message': '小说未设置文件路径'}), 400

    # 标准化路径
    file_path_normalized = file_path.replace('/', os.sep).replace('\\\\', os.sep)

    possible_paths = [
        file_path,
        file_path_normalized,
        os.path.join(os.getcwd(), file_path),
        os.path.join(os.getcwd(), file_path_normalized),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path_normalized),
    ]

    possible_paths = list(dict.fromkeys(possible_paths))

    actual_path = None
    for path in possible_paths:
        if os.path.exists(path) and os.path.isfile(path):
            actual_path = path
            break

    if not actual_path:
        return jsonify({
            'success': False,
            'message': f'文件不存在: {file_path}'
        }), 404

    try:
        # 获取文件名
        filename = os.path.basename(actual_path)

        # 处理中文文件名编码 (RFC 5987)
        from urllib.parse import quote
        from werkzeug.http import dump_options_header

        # RFC 5987 编码的完整文件名
        encoded_filename = quote(filename, safe='')

        # 生成 latin-1 安全的基础文件名（中文字符会被替换）
        latin1_filename = filename.encode('latin-1', 'replace').decode('latin-1').replace('?', '_')
        if not latin1_filename:
            latin1_filename = 'novel.txt'

        # 构建 Content-Disposition 头
        # 格式: attachment; filename="ascii_version"; filename*=UTF-8''encoded_version
        disposition = dump_options_header(
            'attachment',
            {'filename': latin1_filename, 'filename*': f"UTF-8''{encoded_filename}"}
        )

        # 发送文件
        response = send_file(
            actual_path,
            as_attachment=False,
            mimetype='application/octet-stream'
        )

        # werkzeug 的 Headers 类会自动处理非 latin-1 字符
        response.headers.set('Content-Disposition', disposition)

        return response
    except Exception as e:
        return jsonify({'success': False, 'message': f'下载失败: {str(e)}'}), 500


@app.route('/api/files/upload', methods=['POST'])
def upload_novel_file():
    """上传单个小说文件到项目库"""
    file_storage = request.files.get('file')
    relative_path = request.form.get('relative_path', '')

    if not file_storage or not file_storage.filename:
        return jsonify({'success': False, 'message': '请选择要上传的文件'}), 400

    if not is_supported_novel_file(relative_path or file_storage.filename):
        return jsonify({'success': False, 'message': '不支持的文件格式'}), 400

    try:
        stored_path = store_uploaded_file(
            file_storage,
            relative_path=relative_path or file_storage.filename,
            namespace='manual'
        )
        return jsonify({'success': True, 'data': {'file_path': stored_path}})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/novels', methods=['POST'])
def create_novel():
    """添加新小说"""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO novels (title, author, description, file_path, category_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data.get('title'),
            data.get('author'),
            data.get('description'),
            data.get('file_path'),
            data.get('category_id'),
            data.get('status', 0)
        ))

        novel_id = cursor.lastrowid

        # 添加标签关联
        tag_ids = data.get('tag_ids', [])
        for tag_id in tag_ids:
            cursor.execute('INSERT INTO novel_tags (novel_id, tag_id) VALUES (?, ?)',
                         (novel_id, tag_id))

        conn.commit()
        return jsonify({'success': True, 'data': {'id': novel_id}})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/novels/<int:novel_id>', methods=['PUT'])
def update_novel(novel_id):
    """更新小说信息"""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            UPDATE novels
            SET title = ?, author = ?, description = ?, file_path = ?,
                category_id = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            data.get('title'),
            data.get('author'),
            data.get('description'),
            data.get('file_path'),
            data.get('category_id'),
            data.get('status'),
            novel_id
        ))

        # 更新标签关联
        cursor.execute('DELETE FROM novel_tags WHERE novel_id = ?', (novel_id,))
        tag_ids = data.get('tag_ids', [])
        for tag_id in tag_ids:
            cursor.execute('INSERT INTO novel_tags (novel_id, tag_id) VALUES (?, ?)',
                         (novel_id, tag_id))

        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/novels/<int:novel_id>', methods=['DELETE'])
def delete_novel(novel_id):
    """????"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        rows, deletion_targets, shared_paths = _collect_novel_file_deletion_targets(cursor, [novel_id])
        if not rows:
            return jsonify({'success': False, 'message': '?????'}), 404

        file_delete_result = _delete_novel_files(deletion_targets)
        if file_delete_result['failed']:
            return jsonify({'success': False, 'message': _build_file_delete_error_message(file_delete_result['failed'])}), 500

        cursor.execute('DELETE FROM novels WHERE id = ?', (novel_id,))
        conn.commit()
        return jsonify({
            'success': True,
            'data': {
                'deleted': cursor.rowcount,
                'deleted_files': len(file_delete_result['deleted']),
                'missing_files': len(file_delete_result['missing']),
                'shared_files': len(shared_paths)
            }
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

    try:
        cursor.execute('DELETE FROM novels WHERE id = ?', (novel_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


# ==================== API: 分类管理 ====================

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """获取所有分类"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT c.*, COUNT(n.id) as novel_count
        FROM categories c
        LEFT JOIN novels n ON c.id = n.category_id
        GROUP BY c.id
        ORDER BY c.created_at DESC
    ''')
    categories = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify({'success': True, 'data': categories})


@app.route('/api/categories', methods=['POST'])
def create_category():
    """创建分类"""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('INSERT INTO categories (name, description) VALUES (?, ?)',
                     (data.get('name'), data.get('description')))
        conn.commit()
        return jsonify({'success': True, 'data': {'id': cursor.lastrowid}})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': '分类名称已存在'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    """更新分类"""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('UPDATE categories SET name = ?, description = ? WHERE id = ?',
                     (data.get('name'), data.get('description'), category_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """删除分类"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 将该分类下的小说设为无分类
        cursor.execute('UPDATE novels SET category_id = NULL WHERE category_id = ?', (category_id,))
        cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


# ==================== API: 标签管理 ====================

@app.route('/api/tags', methods=['GET'])
def get_tags():
    """获取所有标签"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT t.*, COUNT(nt.novel_id) as novel_count
        FROM tags t
        LEFT JOIN novel_tags nt ON t.id = nt.tag_id
        GROUP BY t.id
        ORDER BY t.created_at DESC
    ''')
    tags = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify({'success': True, 'data': tags})


@app.route('/api/tags', methods=['POST'])
def create_tag():
    """创建标签"""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('INSERT INTO tags (name, color) VALUES (?, ?)',
                     (data.get('name'), data.get('color', '#3498db')))
        conn.commit()
        return jsonify({'success': True, 'data': {'id': cursor.lastrowid}})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': '标签名称已存在'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/tags/<int:tag_id>', methods=['PUT'])
def update_tag(tag_id):
    """更新标签"""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('UPDATE tags SET name = ?, color = ? WHERE id = ?',
                     (data.get('name'), data.get('color'), tag_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/tags/<int:tag_id>', methods=['DELETE'])
def delete_tag(tag_id):
    """删除标签"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM tags WHERE id = ?', (tag_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


# ==================== 统计信息 ====================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计数据"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) as total FROM novels')
    total_novels = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM categories')
    total_categories = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM tags')
    total_tags = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM novels WHERE status = 2')
    finished_novels = cursor.fetchone()['total']

    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'total_novels': total_novels,
            'total_categories': total_categories,
            'total_tags': total_tags,
            'finished_novels': finished_novels
        }
    })


# ==================== 小说阅读功能 ====================

# ==================== 文件路径修复工具 ====================

@app.route('/api/fix-paths', methods=['POST'])
def fix_all_paths():
    """批量修复小说文件路径"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取所有记录
    cursor.execute("SELECT id, file_path FROM novels")
    rows = cursor.fetchall()

    fixed_count = 0
    errors = []

    for row in rows:
        novel_id = row['id']
        old_path = row['file_path']

        # 检查是否需要修复（以特定字符开头）
        if old_path and len(old_path) > 3:
            # 检查前几个字节是否匹配 "小说"
            first_chars = old_path[:3]

            # 如果是相对路径 "小说/xxx" 格式，替换为绝对路径
            if '小说' in first_chars or first_chars.startswith('С'):
                # 替换路径前缀
                new_path = old_path
                if '/' in new_path:
                    new_path = 'D:/' + new_path.replace('小说/', '小说/')
                elif '\\' in new_path:
                    new_path = 'D:/' + new_path.replace('小说\\', '小说/')

                # 确保使用正确的分隔符
                new_path = new_path.replace('/', os.sep).replace('\\\\', os.sep)

                try:
                    cursor.execute(
                        "UPDATE novels SET file_path = ? WHERE id = ?",
                        (new_path, novel_id)
                    )
                    fixed_count += 1
                except Exception as e:
                    errors.append(f"ID {novel_id}: {str(e)}")

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'fixed': fixed_count,
            'errors': errors
        }
    })


# ==================== 文件路径检查 ====================

@app.route('/api/novels/<int:novel_id>/check-file', methods=['GET'])
def check_novel_file(novel_id):
    """检查小说文件是否存在，返回详细路径信息"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM novels WHERE id = ?', (novel_id,))
    novel = cursor.fetchone()
    conn.close()

    if not novel:
        return jsonify({'success': False, 'message': '小说不存在'}), 404

    file_path = novel['file_path']

    # 标准化路径
    file_path_normalized = file_path.replace('/', os.sep).replace('\\\\', os.sep)

    possible_paths = [
        file_path,
        file_path_normalized,
        os.path.join(os.getcwd(), file_path),
        os.path.join(os.getcwd(), file_path_normalized),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path_normalized),
    ]

    possible_paths = list(dict.fromkeys(possible_paths))

    results = []
    actual_path = None
    for path in possible_paths:
        exists = os.path.exists(path) and os.path.isfile(path)
        results.append({
            'path': path,
            'exists': exists
        })
        if exists and not actual_path:
            actual_path = path

    return jsonify({
        'success': True,
        'data': {
            'file_path_in_db': file_path,
            'current_working_dir': os.getcwd(),
            'script_dir': os.path.dirname(os.path.abspath(__file__)),
            'checked_paths': results,
            'file_found': actual_path is not None,
            'actual_path': actual_path
        }
    })


# ==================== AI 配置 API ====================

from ai_client import AIConfig, AIClientFactory, get_ai_client, get_native_gemini_client, is_gemini_compatible_config

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

    user_prompt = '\n\n'.join(context_blocks) + """

请根据以上信息，生成小说的标签和简介。

要求：
1. 只输出一个 JSON 对象，不要输出 Markdown。
2. JSON 格式必须为：{"summary":"...","tags":["标签1","标签2"]}
3. summary 使用中文，控制在 70 到 140 个汉字，语气自然，适合展示在书库卡片里。
4. tags 返回 3 到 6 个简短标签，优先输出题材、风格、世界观、受众、节奏类标签。
5. 信息不足时可以概括，但不要编造具体情节、人物或结局。
6. 标签不要重复，不要带序号，不要带解释。
"""

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

    for field in ('name', 'provider', 'api_base', 'model'):
        value = payload.get(field)
        if value is not None:
            config[field] = value

    for field in ('temperature', 'max_tokens'):
        value = payload.get(field)
        if value is not None and value != '':
            config[field] = value

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



def _now_timestamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _safe_json_list(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _serialize_crawler_task(row):
    item = dict(row)
    item['tag_ids'] = [int(tag_id) for tag_id in _safe_json_list(item.get('tag_ids_json')) if str(tag_id).isdigit()]
    item.pop('tag_ids_json', None)
    return item


def _update_crawler_task(task_id, **fields):
    if not fields:
        return

    conn = get_db()
    cursor = conn.cursor()

    assignments = []
    params = []
    for key, value in fields.items():
        assignments.append(f'{key} = ?')
        params.append(value)

    assignments.append('updated_at = ?')
    params.append(_now_timestamp())
    params.append(task_id)

    cursor.execute(f"UPDATE crawler_tasks SET {', '.join(assignments)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def _fetch_crawler_task(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ct.*, c.name AS category_name, n.title AS novel_title
        FROM crawler_tasks ct
        LEFT JOIN categories c ON ct.category_id = c.id
        LEFT JOIN novels n ON ct.novel_id = n.id
        WHERE ct.id = ?
    ''', (task_id,))
    row = cursor.fetchone()
    conn.close()
    return _serialize_crawler_task(row) if row else None


def _guess_title_from_url(url):
    parsed = urlparse(url)
    name = Path(unquote(parsed.path or '')).stem
    name = re.sub(r'[-_]+', ' ', name).strip()
    return name or parsed.netloc or '未命名小说'


def _request_url(url):
    response = requests.get(
        url,
        headers={'User-Agent': CRAWLER_USER_AGENT},
        timeout=20
    )
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == 'iso-8859-1':
        response.encoding = response.apparent_encoding or 'utf-8'
    return response


def _extract_balanced_tag_block(html_text, start_index, tag_name):
    open_pattern = re.compile(rf'<{tag_name}\b', re.IGNORECASE)
    close_pattern = re.compile(rf'</{tag_name}\s*>', re.IGNORECASE)
    first_open = open_pattern.search(html_text, start_index)
    if not first_open:
        return ''

    depth = 1
    position = first_open.end()

    while True:
        next_open = open_pattern.search(html_text, position)
        next_close = close_pattern.search(html_text, position)
        if not next_close:
            return html_text[first_open.start():]
        if next_open and next_open.start() < next_close.start():
            depth += 1
            position = next_open.end()
            continue
        depth -= 1
        position = next_close.end()
        if depth == 0:
            return html_text[first_open.start():position]


def _html_to_text(raw_html):
    text = re.sub(r'(?is)<(script|style|noscript|iframe).*?>.*?</\1>', '\n', raw_html)
    text = re.sub(r'(?is)<!--.*?-->', '\n', text)
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</(p|div|h1|h2|h3|h4|li|tr|section|article|dd|dt)>', '\n', text)
    text = re.sub(r'(?is)<[^>]+>', '', text)
    text = html.unescape(text)

    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r'\s+', ' ', raw_line).strip()
        if not line:
            if lines and lines[-1] != '':
                lines.append('')
            continue
        if line in {'目录', '返回目录', '下一章', '上一章', '加入书签'}:
            continue
        lines.append(line)

    compact = []
    last_blank = False
    for line in lines:
        if line == '':
            if compact and not last_blank:
                compact.append('')
            last_blank = True
            continue
        compact.append(line)
        last_blank = False

    return '\n'.join(compact).strip()


def _extract_preferred_html_block(raw_html):
    lower_html = raw_html.lower()
    keywords = [
        'id="content"', "id='content'",
        'id="chaptercontent"', "id='chaptercontent'",
        'id="readcontent"', "id='readcontent'",
        'id="txt"', "id='txt'",
        'class="content"', "class='content'",
        'class="chapter"', "class='chapter'",
        'class="article"', "class='article'",
        'class="read-content"', "class='read-content'",
        'class="bookcontent"', "class='bookcontent'",
    ]

    for keyword in keywords:
        keyword_index = lower_html.find(keyword)
        if keyword_index == -1:
            continue
        for tag_name in ('div', 'article', 'section', 'td'):
            tag_start = lower_html.rfind(f'<{tag_name}', 0, keyword_index)
            if tag_start != -1:
                block = _extract_balanced_tag_block(raw_html, tag_start, tag_name)
                if block:
                    return block

    body_match = re.search(r'(?is)<body[^>]*>(.*)</body>', raw_html)
    if body_match:
        return body_match.group(1)

    return raw_html


def _extract_main_text(raw_html):
    block = _extract_preferred_html_block(raw_html)
    text = _html_to_text(block)
    if len(text) >= 120:
        return text
    return _html_to_text(raw_html)


def _extract_page_title(raw_html):
    for pattern in (
        r'(?is)<h1[^>]*>(.*?)</h1>',
        r'(?is)<title[^>]*>(.*?)</title>'
    ):
        match = re.search(pattern, raw_html)
        if not match:
            continue
        title = _html_to_text(match.group(1))
        title = re.sub(r'\s+', ' ', title).strip(' -_|')
        if title:
            return title
    return ''


def _extract_chapter_links(raw_html, base_url):
    link_pattern = re.compile(r'(?is)<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>')
    base_host = urlparse(base_url).netloc
    links = []
    seen = set()

    for href, label_html in link_pattern.findall(raw_html):
        href = html.unescape((href or '').strip())
        if not href or href.startswith(('javascript:', '#', 'mailto:')):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme not in ('http', 'https'):
            continue
        if base_host and parsed.netloc and parsed.netloc != base_host:
            continue

        full_url = full_url.split('#', 1)[0]
        if full_url == base_url:
            continue

        label = _html_to_text(label_html)
        label = re.sub(r'\s+', ' ', label).strip()
        if not label or len(label) > 64:
            continue

        text_match = re.search(r'(第.{0,12}[章节回卷集部篇]|chapter\s*\d+|序章|楔子|尾声|终章|番外)', label, re.IGNORECASE)
        href_match = re.search(r'(chapter|read|book|\d{2,}|\.html?$)', parsed.path, re.IGNORECASE)
        if not (text_match or href_match):
            continue

        dedupe_key = full_url.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        links.append({'url': full_url, 'title': label})

    return links


def _store_crawled_text(title, content):
    target_rel = Path('crawlers') / sanitize_relative_storage_path(f'{sanitize_storage_name(title)}.txt')
    target_abs = UPLOAD_ROOT / target_rel
    target_abs.parent.mkdir(parents=True, exist_ok=True)

    final_rel = target_rel
    final_abs = target_abs
    counter = 1
    while final_abs.exists():
        final_rel = target_rel.with_name(f'{target_rel.stem}_{counter}{target_rel.suffix}')
        final_abs = UPLOAD_ROOT / final_rel
        counter += 1

    with open(final_abs, 'w', encoding='utf-8') as output_file:
        output_file.write(content)

    return str(Path('library') / final_rel).replace('\\', '/')


def _save_crawler_novel(task, crawl_result):
    conn = get_db()
    cursor = conn.cursor()

    file_path = _store_crawled_text(crawl_result['title'], crawl_result['content'])
    title = crawl_result['title']
    author = crawl_result.get('author') or task.get('author') or ''
    description = task.get('description') or ''
    category_id = task.get('category_id')
    novel_id = task.get('novel_id')

    try:
        existing_novel_id = None
        if novel_id:
            cursor.execute('SELECT id FROM novels WHERE id = ?', (novel_id,))
            existing = cursor.fetchone()
            if existing:
                existing_novel_id = existing['id']

        if existing_novel_id:
            cursor.execute('''
                UPDATE novels
                SET title = ?, author = ?, description = ?, file_path = ?, category_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (title, author, description, file_path, category_id, existing_novel_id))
            novel_id = existing_novel_id
            cursor.execute('DELETE FROM novel_tags WHERE novel_id = ?', (novel_id,))
        else:
            cursor.execute('''
                INSERT INTO novels (title, author, description, file_path, category_id, status)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (title, author, description, file_path, category_id))
            novel_id = cursor.lastrowid

        for tag_id in task.get('tag_ids', []):
            cursor.execute('INSERT OR IGNORE INTO novel_tags (novel_id, tag_id) VALUES (?, ?)', (novel_id, tag_id))

        conn.commit()
        return novel_id, file_path
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _crawl_task_content(task_id, task):
    response = _request_url(task['source_url'])
    content_type = (response.headers.get('Content-Type') or '').lower()

    if 'text/plain' in content_type or task['source_url'].lower().endswith('.txt'):
        text_content = response.text.strip()
        if not text_content:
            raise RuntimeError('抓取结果为空，请检查链接是否可直接访问文本内容')
        return {
            'title': task.get('title') or _guess_title_from_url(task['source_url']),
            'author': task.get('author') or '',
            'content': text_content,
            'chapter_count': 1
        }

    raw_html = response.text
    chapter_links = _extract_chapter_links(raw_html, task['source_url'])
    title = task.get('title') or _extract_page_title(raw_html) or _guess_title_from_url(task['source_url'])

    if len(chapter_links) >= 2:
        total = min(len(chapter_links), 500)
        _update_crawler_task(task_id, total_chapters=total, crawled_chapters=0, progress=0)
        sections = []

        for index, chapter in enumerate(chapter_links[:total], start=1):
            chapter_response = _request_url(chapter['url'])
            chapter_title = chapter.get('title') or _extract_page_title(chapter_response.text) or f'第{index}章'
            chapter_text = _extract_main_text(chapter_response.text)
            if chapter_text:
                sections.append(f'{chapter_title}\n\n{chapter_text}')
            _update_crawler_task(
                task_id,
                total_chapters=total,
                crawled_chapters=index,
                progress=int(index * 100 / total)
            )

        if not sections:
            raise RuntimeError('未能从目录页抓取到有效章节内容，请换一个目录页链接重试')

        return {
            'title': title,
            'author': task.get('author') or '',
            'content': '\n\n'.join(sections),
            'chapter_count': len(sections)
        }

    main_text = _extract_main_text(raw_html)
    if len(main_text) < 80:
        raise RuntimeError('未能提取正文内容，请确认链接为小说详情页、目录页或正文页')

    _update_crawler_task(task_id, total_chapters=1, crawled_chapters=1, progress=100)
    return {
        'title': title,
        'author': task.get('author') or '',
        'content': main_text,
        'chapter_count': 1
    }


def _run_crawler_task(task_id):
    try:
        task = _fetch_crawler_task(task_id)
        if not task:
            return

        _update_crawler_task(
            task_id,
            status='running',
            progress=0,
            total_chapters=0,
            crawled_chapters=0,
            last_error=None,
            started_at=_now_timestamp(),
            finished_at=None
        )

        crawl_result = _crawl_task_content(task_id, task)
        novel_id, file_path = _save_crawler_novel(task, crawl_result)

        _update_crawler_task(
            task_id,
            title=crawl_result['title'],
            author=crawl_result.get('author') or task.get('author') or '',
            status='completed',
            progress=100,
            total_chapters=crawl_result['chapter_count'],
            crawled_chapters=crawl_result['chapter_count'],
            novel_id=novel_id,
            file_path=file_path,
            last_error=None,
            finished_at=_now_timestamp()
        )
    except Exception as error:
        _update_crawler_task(
            task_id,
            status='failed',
            last_error=str(error),
            finished_at=_now_timestamp()
        )
    finally:
        with crawler_threads_lock:
            crawler_threads.pop(task_id, None)


def _start_crawler_thread(task_id):
    with crawler_threads_lock:
        existing_thread = crawler_threads.get(task_id)
        if existing_thread and existing_thread.is_alive():
            return False

        worker = threading.Thread(target=_run_crawler_task, args=(task_id,), daemon=True)
        crawler_threads[task_id] = worker
        worker.start()
        return True


@app.route('/api/crawler/stats', methods=['GET'])
def get_crawler_stats():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) AS total FROM crawler_tasks')
    total_tasks = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) AS total FROM crawler_tasks WHERE status = 'running'")
    running_tasks = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) AS total FROM crawler_tasks WHERE status = 'completed'")
    completed_tasks = cursor.fetchone()['total']
    cursor.execute('SELECT COUNT(DISTINCT novel_id) AS total FROM crawler_tasks WHERE novel_id IS NOT NULL')
    downloaded_novels = cursor.fetchone()['total']
    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'total_tasks': total_tasks,
            'running_tasks': running_tasks,
            'completed_tasks': completed_tasks,
            'downloaded_novels': downloaded_novels
        }
    })


@app.route('/api/crawler/tasks', methods=['GET'])
def get_crawler_tasks():
    keyword = (request.args.get('keyword') or '').strip()
    status = (request.args.get('status') or '').strip()

    conn = get_db()
    cursor = conn.cursor()

    query = '''
        SELECT ct.*, c.name AS category_name, n.title AS novel_title
        FROM crawler_tasks ct
        LEFT JOIN categories c ON ct.category_id = c.id
        LEFT JOIN novels n ON ct.novel_id = n.id
        WHERE 1 = 1
    '''
    params = []

    if keyword:
        query += ' AND (ct.name LIKE ? OR ct.title LIKE ? OR ct.author LIKE ? OR ct.source_url LIKE ?)'
        keyword_like = f'%{keyword}%'
        params.extend([keyword_like, keyword_like, keyword_like, keyword_like])

    if status in CRAWLER_STATUSES:
        query += ' AND ct.status = ?'
        params.append(status)

    query += ' ORDER BY CASE ct.status WHEN "running" THEN 0 WHEN "failed" THEN 1 ELSE 2 END, ct.updated_at DESC, ct.id DESC'
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return jsonify({'success': True, 'data': [_serialize_crawler_task(row) for row in rows]})


@app.route('/api/crawler/tasks', methods=['POST'])
def create_crawler_task():
    data = request.get_json(silent=True) or {}
    source_url = (data.get('source_url') or '').strip()
    if not source_url:
        return jsonify({'success': False, 'message': '请填写要抓取的网页链接'}), 400
    if not source_url.startswith(('http://', 'https://')):
        return jsonify({'success': False, 'message': '链接必须以 http:// 或 https:// 开头'}), 400

    tag_ids = []
    for value in data.get('tag_ids', []):
        try:
            tag_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    category_id = data.get('category_id')
    if category_id in ('', None):
        category_id = None
    else:
        try:
            category_id = int(category_id)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': '分类参数无效'}), 400

    name = (data.get('name') or data.get('title') or _guess_title_from_url(source_url)).strip()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO crawler_tasks (name, source_url, title, author, description, category_id, tag_ids_json, status, progress)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0)
    ''', (
        name,
        source_url,
        (data.get('title') or '').strip(),
        (data.get('author') or '').strip(),
        (data.get('description') or '').strip(),
        category_id,
        json.dumps(sorted(set(tag_ids)))
    ))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()

    if bool(data.get('start_immediately', True)):
        _start_crawler_thread(task_id)

    return jsonify({'success': True, 'data': _fetch_crawler_task(task_id)})


@app.route('/api/crawler/tasks/<int:task_id>/run', methods=['POST'])
def run_crawler_task(task_id):
    task = _fetch_crawler_task(task_id)
    if not task:
        return jsonify({'success': False, 'message': '爬虫任务不存在'}), 404

    if task['status'] == 'running':
        return jsonify({'success': False, 'message': '任务已在运行中'}), 400

    if not _start_crawler_thread(task_id):
        return jsonify({'success': False, 'message': '任务启动失败，请稍后重试'}), 400

    return jsonify({'success': True, 'message': '任务已启动'})


@app.route('/api/crawler/tasks/<int:task_id>', methods=['DELETE'])
def delete_crawler_task(task_id):
    task = _fetch_crawler_task(task_id)
    if not task:
        return jsonify({'success': False, 'message': '爬虫任务不存在'}), 404

    if task['status'] == 'running':
        return jsonify({'success': False, 'message': '运行中的任务暂不支持删除，请稍后重试'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM crawler_tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


def scan_folder(folder_path, create_category_from_folder=True):
    """扫描文件夹中的小说文件

    Args:
        folder_path: 要扫描的文件夹路径
        create_category_from_folder: 是否将文件夹名作为分类

    Returns:
        list: 发现的小说文件列表，每个元素包含 file_path, title, category_name
    """
    novels = []
    folder_path = Path(folder_path)

    if not folder_path.exists():
        return novels

    # 遍历文件夹
    for root, dirs, files in os.walk(folder_path):
        root_path = Path(root)

        # 计算相对于扫描根目录的分类
        category_name = None
        if create_category_from_folder:
            try:
                rel_path = root_path.relative_to(folder_path)
                if rel_path.parts:
                    # 使用第一级子文件夹作为分类名
                    category_name = rel_path.parts[0]
            except ValueError:
                pass

        for filename in files:
            file_ext = Path(filename).suffix.lower()
            if file_ext in NOVEL_EXTENSIONS:
                file_path = root_path / filename

                # 清理文件名作为标题
                title = Path(filename).stem
                # 移除常见的数字前缀和分隔符
                title = re.sub(r'^\d+[\s\-_\.]+', '', title)
                title = title.strip()

                novels.append({
                    'file_path': str(file_path),
                    'title': title,
                    'category_name': category_name,
                    'file_size': file_path.stat().st_size
                })

    return novels


@app.route('/api/import/scan', methods=['POST'])
def scan_folder_api():
    """扫描文件夹API"""
    data = request.json
    folder_path = data.get('folder_path', '').strip()

    if not folder_path:
        return jsonify({'success': False, 'message': '请提供文件夹路径'}), 400

    if not os.path.exists(folder_path):
        return jsonify({'success': False, 'message': '文件夹不存在'}), 400

    if not os.path.isdir(folder_path):
        return jsonify({'success': False, 'message': '提供的路径不是文件夹'}), 400

    try:
        novels = scan_folder(folder_path)
        return jsonify({
            'success': True,
            'data': {
                'total': len(novels),
                'novels': novels
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/import/batch', methods=['POST'])
def batch_import():
    """批量导入小说"""
    try:
        novels, tag_ids, default_status = parse_import_request()
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400

    if not novels:
        return jsonify({'success': False, 'message': '没有要导入的小说'}), 400

    conn = get_db()
    cursor = conn.cursor()

    imported = 0
    skipped = 0
    failed = 0
    errors = []

    try:
        for novel_data in novels:
            if not novel_data.get('selected', True):
                continue

            try:
                cursor.execute('SELECT id FROM novels WHERE file_path = ?',
                             (novel_data.get('file_path'),))
                if cursor.fetchone():
                    skipped += 1
                    continue

                category_id = None
                category_name = novel_data.get('category_name')
                if category_name:
                    cursor.execute('SELECT id FROM categories WHERE name = ?', (category_name,))
                    result = cursor.fetchone()
                    if result:
                        category_id = result['id']
                    else:
                        cursor.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
                        category_id = cursor.lastrowid

                cursor.execute('''
                    INSERT INTO novels (title, author, file_path, category_id, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    novel_data.get('title', '未命名'),
                    novel_data.get('author', ''),
                    novel_data.get('file_path'),
                    category_id,
                    default_status
                ))

                novel_id = cursor.lastrowid

                for tag_id in tag_ids:
                    cursor.execute('INSERT OR IGNORE INTO novel_tags (novel_id, tag_id) VALUES (?, ?)',
                                 (novel_id, tag_id))

                imported += 1

            except Exception as e:
                failed += 1
                errors.append(f"{novel_data.get('title', 'Unknown')}: {str(e)}")

        conn.commit()

        return jsonify({
            'success': True,
            'data': {
                'imported': imported,
                'skipped': skipped,
                'failed': failed,
                'errors': errors[:10]
            }
        })

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/novels/batch/tags', methods=['POST'])
def batch_add_tags():
    """批量为小说添加或移除标签"""
    data = request.json
    novel_ids = data.get('novel_ids', [])
    tag_ids = data.get('tag_ids', [])
    mode = data.get('mode', 'add')  # 'add', 'remove', 'set'

    if not novel_ids:
        return jsonify({'success': False, 'message': '未选择小说'}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        if mode == 'set':
            # 设置为指定标签（先删除所有标签，再添加）
            placeholders = ','.join(['?' for _ in novel_ids])
            cursor.execute(f'DELETE FROM novel_tags WHERE novel_id IN ({placeholders})', novel_ids)

        for novel_id in novel_ids:
            for tag_id in tag_ids:
                if mode == 'remove':
                    cursor.execute('DELETE FROM novel_tags WHERE novel_id = ? AND tag_id = ?',
                                 (novel_id, tag_id))
                else:  # add or set
                    # 使用 INSERT OR IGNORE 避免重复
                    cursor.execute('INSERT OR IGNORE INTO novel_tags (novel_id, tag_id) VALUES (?, ?)',
                                 (novel_id, tag_id))

        conn.commit()
        return jsonify({'success': True, 'data': {'affected': len(novel_ids)}})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/novels/batch/category', methods=['POST'])
def batch_set_category():
    """批量设置小说分类"""
    data = request.json
    novel_ids = data.get('novel_ids', [])
    category_id = data.get('category_id')

    if not novel_ids:
        return jsonify({'success': False, 'message': '未选择小说'}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        placeholders = ','.join(['?' for _ in novel_ids])
        cursor.execute(f'''
            UPDATE novels
            SET category_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
        ''', [category_id] + novel_ids)

        conn.commit()
        return jsonify({'success': True, 'data': {'affected': cursor.rowcount}})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/novels/batch/status', methods=['POST'])
def batch_set_status():
    """批量设置小说阅读状态"""
    data = request.json
    novel_ids = data.get('novel_ids', [])
    status = data.get('status')

    if not novel_ids:
        return jsonify({'success': False, 'message': '未选择小说'}), 400

    if status not in [0, 1, 2]:
        return jsonify({'success': False, 'message': '无效的状态值'}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        placeholders = ','.join(['?' for _ in novel_ids])
        cursor.execute(f'''
            UPDATE novels
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
        ''', [status] + novel_ids)

        conn.commit()
        return jsonify({'success': True, 'data': {'affected': cursor.rowcount}})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/novels/batch/delete', methods=['POST'])
def batch_delete_novels():
    """??????"""
    data = request.json
    novel_ids = _normalize_novel_ids((data or {}).get('novel_ids', []))

    if not novel_ids:
        return jsonify({'success': False, 'message': '?????'}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        rows, deletion_targets, shared_paths = _collect_novel_file_deletion_targets(cursor, novel_ids)
        if not rows:
            return jsonify({'success': False, 'message': '?????????'}), 404

        file_delete_result = _delete_novel_files(deletion_targets)
        if file_delete_result['failed']:
            return jsonify({'success': False, 'message': _build_file_delete_error_message(file_delete_result['failed'])}), 500

        placeholders = ','.join(['?' for _ in novel_ids])
        cursor.execute(f'DELETE FROM novels WHERE id IN ({placeholders})', novel_ids)

        conn.commit()
        return jsonify({
            'success': True,
            'data': {
                'deleted': cursor.rowcount,
                'deleted_files': len(file_delete_result['deleted']),
                'missing_files': len(file_delete_result['missing']),
                'shared_files': len(shared_paths)
            }
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

# ==================== 启动 ====================

if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("本地小说管理器已启动!")
    print("访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
