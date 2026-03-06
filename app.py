"""
??????? - Flask??
"""
import json
import os
import sqlite3
import re
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS

# ??????????
NOVEL_EXTENSIONS = {'.txt', '.epub', '.pdf', '.mobi', '.azw3', '.doc', '.docx', '.rtf'}

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

DATABASE = 'novels.db'
APP_ROOT = Path(__file__).resolve().parent
UPLOAD_ROOT = APP_ROOT / 'library'
TEXT_READABLE_EXTENSIONS = {'.txt'}


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
    """删除小说"""
    conn = get_db()
    cursor = conn.cursor()

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

from ai_client import AIConfig, AIClientFactory, get_ai_client

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


@app.route('/api/ai/novels/metadata', methods=['POST'])
def generate_novel_metadata():
    """使用 AI 为小说生成简介和标签。"""
    data = request.get_json(silent=True) or {}
    novel_id = data.get('novel_id')
    base_novel = get_novel_detail_record(novel_id) if novel_id else None

    title = (data.get('title') or (base_novel or {}).get('title') or '').strip()
    author = (data.get('author') or (base_novel or {}).get('author') or '').strip()
    description = (data.get('description') or (base_novel or {}).get('description') or '').strip()
    file_path = (data.get('file_path') or (base_novel or {}).get('file_path') or '').strip()
    category_id = data.get('category_id')
    category_name = (data.get('category_name') or '').strip()

    if not category_name:
        if category_id:
            category_name = get_category_name_by_id(category_id)
        elif base_novel:
            category_name = (base_novel.get('category_name') or '').strip()

    tag_ids = data.get('tag_ids')
    if tag_ids is None and base_novel:
        tag_ids = [tag['id'] for tag in base_novel.get('tags', [])]
    existing_tags = get_tag_names_by_ids(tag_ids or [])
    if not existing_tags and base_novel:
        existing_tags = [tag['name'] for tag in base_novel.get('tags', [])]

    content_excerpt = (data.get('content_excerpt') or '').strip()
    if not content_excerpt:
        content_excerpt = extract_text_excerpt(file_path)

    if not title and not description and not content_excerpt:
        return jsonify({'success': False, 'message': '请先填写书名，或提供可读取的文本内容'}), 400

    client = get_ai_client()
    if not client:
        return jsonify({'success': False, 'message': '请先在 AI 配置中激活可用模型'}), 400

    try:
        messages = build_novel_ai_messages(
            title=title,
            author=author,
            category_name=category_name,
            description=description,
            existing_tags=existing_tags,
            content_excerpt=content_excerpt
        )
        response_text = client.chat(messages, stream=False)
        response_data = extract_json_object(response_text)

        summary = str(response_data.get('summary', '')).strip()
        summary = re.sub(r'\s+', ' ', summary)
        summary = summary.strip('"“”')

        tag_names = normalize_ai_tag_names(response_data.get('tags', []))
        tag_records = ensure_tags_exist(tag_names)

        if not summary and not tag_records:
            return jsonify({'success': False, 'message': 'AI 未生成可用的简介或标签，请重试'}), 500

        return jsonify({
            'success': True,
            'data': {
                'summary': summary,
                'tags': tag_records,
                'tag_names': [tag['name'] for tag in tag_records],
                'used_excerpt': bool(content_excerpt)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== 批量导入 ====================

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
    """批量删除小说"""
    data = request.json
    novel_ids = data.get('novel_ids', [])

    if not novel_ids:
        return jsonify({'success': False, 'message': '未选择小说'}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        placeholders = ','.join(['?' for _ in novel_ids])
        cursor.execute(f'DELETE FROM novels WHERE id IN ({placeholders})', novel_ids)

        conn.commit()
        return jsonify({'success': True, 'data': {'deleted': cursor.rowcount}})
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
