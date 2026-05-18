"""本地小说管理器 - Flask application composition root."""
import os
import secrets
from pathlib import Path

from flask import Flask, render_template
from flask_cors import CORS

from admin_routes import ensure_management_schema, register_admin_routes
from ai_routes import ensure_character_analysis_schema, register_ai_routes
from batch_routes import register_batch_routes
from character_routes import register_character_routes
from crawler_routes import (
    _ensure_crawler_site_rule_schema,
    _ensure_crawler_task_schema,
    _recover_interrupted_crawler_tasks,
    _seed_default_crawler_site_rules,
    register_crawler_routes,
)
from db_utils import connect_database, enable_wal
from import_routes import register_import_routes, scan_folder
from novel_routes import register_novel_routes
from reader_routes import register_reader_routes
from reader_utils import detect_encoding, get_cached_reader_file, parse_chapters
from storage_utils import (
    UPLOAD_ROOT,
    is_text_readable_file,
    resolve_novel_file_path,
)
from taxonomy_routes import register_taxonomy_routes


app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)


def _load_or_create_secret_key():
    configured_secret = os.getenv('APP_SECRET_KEY')
    if configured_secret:
        return configured_secret

    secret_path = Path(app.instance_path) / 'app_secret.key'
    try:
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        if secret_path.exists():
            saved_secret = secret_path.read_text(encoding='utf-8').strip()
            if saved_secret:
                return saved_secret

        generated_secret = secrets.token_hex(32)
        secret_path.write_text(generated_secret, encoding='utf-8')
        return generated_secret
    except OSError:
        return secrets.token_hex(32)


app.config['SECRET_KEY'] = _load_or_create_secret_key()

DATABASE = 'novels.db'


def get_db():
    """获取数据库连接"""
    return connect_database(DATABASE, foreign_keys=True)


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
        'last_read_at': 'TIMESTAMP',
        'file_size': 'INTEGER',
        'content_hash': 'TEXT',
        'original_filename': 'TEXT'
    })


def init_db():
    """初始化数据库"""
    conn = get_db()
    enable_wal(conn)
    cursor = conn.cursor()
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            description TEXT,
            file_path TEXT,
            category_id INTEGER,
            cover_path TEXT,
            status INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#3498db',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

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
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_novels_content_hash ON novels(content_hash)')
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
    ensure_character_analysis_schema(cursor)
    ensure_management_schema(cursor)

    conn.commit()
    conn.close()


@app.route('/')
def index():
    return render_template('index.html')


register_novel_routes(app, get_db=get_db)
register_reader_routes(
    app,
    get_db=get_db,
    resolve_novel_file_path=resolve_novel_file_path,
    is_text_readable_file=is_text_readable_file,
)
register_taxonomy_routes(app, get_db=get_db)
register_import_routes(app, get_db=get_db)
register_batch_routes(app, get_db=get_db)
register_ai_routes(
    app,
    get_db=get_db,
    resolve_novel_file_path=resolve_novel_file_path,
    is_text_readable_file=is_text_readable_file,
    detect_encoding=detect_encoding,
)
register_character_routes(
    app,
    get_db=get_db,
    resolve_novel_file_path=resolve_novel_file_path,
    is_text_readable_file=is_text_readable_file,
    detect_encoding=detect_encoding,
)
register_crawler_routes(app, get_db=get_db)
register_admin_routes(app, get_db=get_db)


if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("本地小说管理器已启动!")
    print("访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
