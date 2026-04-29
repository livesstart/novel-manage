"""
本地小说管理器 - Flask 后端
"""
import os
import sqlite3
import re
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS


app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

DATABASE = 'novels.db'
def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _ensure_table_columns(cursor, table_name, required_columns):
    cursor.execute(f'PRAGMA table_info({table_name})')
    existing_columns = {row['name'] for row in cursor.fetchall()}

    for column_name, definition in required_columns.items():
        if column_name not in existing_columns:
            cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}')


def _ensure_novel_schema(cursor):
    _ensure_table_columns(cursor, 'novels', {
        'last_read_chapter_index': 'INTEGER DEFAULT 0',
        'last_read_scroll_percent': 'REAL DEFAULT 0',
        'last_read_at': 'TIMESTAMP'
    })


def init_db():
    """初始化数据库"""
    conn = get_db()
    cursor = conn.cursor()
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    # 小说表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            description TEXT,
            file_path TEXT,
            category_id INTEGER,
            cover_path TEXT,
            status INTEGER DEFAULT 0,  -- 0:未读 1:阅读中 2:已读
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')

    # 分类表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 标签表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#3498db',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 小说-标签关联表
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
    _ensure_novel_schema(cursor)
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
            site_rule_id INTEGER,
            tag_ids_json TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            total_chapters INTEGER DEFAULT 0,
            crawled_chapters INTEGER DEFAULT 0,
            attempt_count INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            novel_id INTEGER,
            file_path TEXT,
            last_error TEXT,
            last_error_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
            FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE SET NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawler_site_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            host_pattern TEXT NOT NULL UNIQUE,
            title_selector TEXT,
            content_selector TEXT,
            listing_link_selector TEXT,
            related_thread_selector TEXT,
            chapter_link_selector TEXT,
            chapter_title_selector TEXT,
            remove_selectors TEXT,
            notes TEXT,
            sort_order INTEGER DEFAULT 100,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_crawler_tasks_status_updated ON crawler_tasks(status, updated_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_crawler_site_rules_active_sort ON crawler_site_rules(is_active, sort_order ASC, host_pattern ASC)')
    _ensure_crawler_task_schema(cursor)
    _ensure_crawler_site_rule_schema(cursor)
    _seed_default_crawler_site_rules(cursor)
    _recover_interrupted_crawler_tasks(cursor)

    conn.commit()
    conn.close()


from storage_utils import (
    NOVEL_EXTENSIONS,
    UPLOAD_ROOT,
    _build_file_delete_error_message,
    _collect_novel_file_deletion_targets,
    _delete_novel_files,
    _normalize_novel_ids,
    is_supported_novel_file,
    is_text_readable_file,
    parse_import_request,
    resolve_novel_file_path,
    store_uploaded_file,
)

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
    untagged_only = request.args.get('untagged_only', '').strip().lower() in {'1', 'true', 'yes', 'on'}

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

    if untagged_only:
        query += ' AND NOT EXISTS (SELECT 1 FROM novel_tags nt WHERE nt.novel_id = n.id)'

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


# ==================== Reader routes ====================
from reader_utils import detect_encoding, parse_chapters


def _serialize_reading_progress(novel, chapter_count=None):
    max_index = max((chapter_count or 1) - 1, 0)
    try:
        chapter_index = int(novel.get('last_read_chapter_index') or 0)
    except (TypeError, ValueError):
        chapter_index = 0
    try:
        scroll_percent = float(novel.get('last_read_scroll_percent') or 0)
    except (TypeError, ValueError):
        scroll_percent = 0

    return {
        'chapter_index': max(0, min(chapter_index, max_index)),
        'scroll_percent': max(0, min(scroll_percent, 100)),
        'last_read_at': novel.get('last_read_at')
    }


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
                'reading_progress': _serialize_reading_progress(novel, len(chapters)),
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


@app.route('/api/novels/<int:novel_id>/reading-progress', methods=['PUT'])
def update_reading_progress(novel_id):
    """保存小说阅读进度"""
    data = request.get_json(silent=True) or {}
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM novels WHERE id = ?', (novel_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'message': '小说不存在'}), 404

    novel = dict(row)
    try:
        chapter_index = int(data.get('chapter_index', 0))
    except (TypeError, ValueError):
        chapter_index = 0
    try:
        scroll_percent = float(data.get('scroll_percent', 0))
    except (TypeError, ValueError):
        scroll_percent = 0

    chapter_count = 1
    file_path = novel.get('file_path')
    actual_path, _ = resolve_novel_file_path(file_path)
    if actual_path and is_text_readable_file(actual_path):
        try:
            encoding = detect_encoding(actual_path)
            with open(actual_path, 'r', encoding=encoding, errors='ignore') as handle:
                chapter_count = max(len(parse_chapters(handle.read())), 1)
        except Exception:
            chapter_count = 1

    progress = {
        'last_read_chapter_index': max(0, min(chapter_index, chapter_count - 1)),
        'last_read_scroll_percent': max(0, min(scroll_percent, 100))
    }

    cursor.execute('''
        UPDATE novels
        SET last_read_chapter_index = ?,
            last_read_scroll_percent = ?,
            last_read_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        progress['last_read_chapter_index'],
        progress['last_read_scroll_percent'],
        novel_id
    ))
    conn.commit()

    cursor.execute('SELECT * FROM novels WHERE id = ?', (novel_id,))
    updated = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'reading_progress': _serialize_reading_progress(updated, chapter_count)
        }
    })


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
        rows, deletion_targets, shared_paths = _collect_novel_file_deletion_targets(cursor, [novel_id])
        if not rows:
            return jsonify({'success': False, 'message': '小说不存在'}), 404

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
from ai_routes import register_ai_routes
from crawler_routes import (
    _ensure_crawler_site_rule_schema,
    _ensure_crawler_task_schema,
    _recover_interrupted_crawler_tasks,
    _seed_default_crawler_site_rules,
    register_crawler_routes,
)

register_ai_routes(
    app,
    get_db=get_db,
    resolve_novel_file_path=resolve_novel_file_path,
    is_text_readable_file=is_text_readable_file,
    detect_encoding=detect_encoding,
)

register_crawler_routes(app, get_db=get_db)

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
    novel_ids = _normalize_novel_ids((data or {}).get('novel_ids', []))

    if not novel_ids:
        return jsonify({'success': False, 'message': '请选择小说'}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        rows, deletion_targets, shared_paths = _collect_novel_file_deletion_targets(cursor, novel_ids)
        if not rows:
            return jsonify({'success': False, 'message': '所选小说不存在'}), 404

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
