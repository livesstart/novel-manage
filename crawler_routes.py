"""Crawler site rules, extraction helpers, and task routes."""
import asyncio
import base64
import hashlib
import html
import ipaddress
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from flask import jsonify, request
import requests

from storage_utils import UPLOAD_ROOT, sanitize_relative_storage_path, sanitize_storage_name

try:
    import websockets
except Exception:
    websockets = None


_get_db = None


def get_db():
    if _get_db is None:
        raise RuntimeError('crawler_routes has not been registered with a database provider')
    return _get_db()


CRAWLER_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0 Safari/537.36'
CRAWLER_STATUSES = {'pending', 'running', 'completed', 'failed'}
CRAWLER_CONNECT_TIMEOUT = 10
CRAWLER_READ_TIMEOUT = 30
CRAWLER_REQUEST_RETRIES = 3
CRAWLER_RETRY_BACKOFF_SECONDS = 1.5
CRAWLER_DEFAULT_MAX_ATTEMPTS = 3
CRAWLER_MAX_ALLOWED_ATTEMPTS = 5
CRAWLER_RESPONSE_SIZE_LIMIT = 5 * 1024 * 1024
CRAWLER_LISTING_BATCH_MAX = 50
CRAWLER_ALLOW_PRIVATE_TARGETS = os.getenv('ALLOW_PRIVATE_CRAWLER_TARGETS', '').strip().lower() in {'1', 'true', 'yes', 'on'}
ALICESW_HOST = 'www.alicesw.com'
KAKUYOMU_HOST_KEYWORDS = ('kakuyomu.jp',)
SYOSETU_HOST_KEYWORDS = ('syosetu.com',)
PIXIV_HOST_KEYWORDS = ('pixiv.net',)
ALPHAPOLIS_HOST_KEYWORDS = ('alphapolis.co.jp',)
HAMELN_HOST_KEYWORDS = ('syosetu.org',)
LINOVELIB_HOST_KEYWORDS = ('linovelib.com', 'bilinovel.com')
LINOVELIB_CHAPTER_PATH_PATTERN = re.compile(r'^/novel/(?P<book_id>\d+)/(?P<chapter_id>\d+)(?:_(?P<page>\d+))?\.html$', re.IGNORECASE)
KAKUYOMU_WORK_PATH_PATTERN = re.compile(r'^/works/(?P<work_id>\d+)(?:/episodes/(?P<episode_id>\d+))?/?$')
PIXIV_SERIES_PATH_PATTERN = re.compile(r'^/novel/series/(?P<series_id>\d+)/?$')
PIXIV_NOVEL_SHOW_PATH = '/novel/show.php'
EDGE_BROWSER_PATHS = tuple(
    path
    for path in (
        Path(os.environ.get('PROGRAMFILES(X86)', '')) / 'Microsoft/Edge/Application/msedge.exe'
        if os.environ.get('PROGRAMFILES(X86)')
        else None,
        Path(os.environ.get('PROGRAMFILES', '')) / 'Microsoft/Edge/Application/msedge.exe'
        if os.environ.get('PROGRAMFILES')
        else None,
        Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'),
        Path('C:/Program Files/Microsoft/Edge/Application/msedge.exe'),
    )
    if path is not None
)
EDGE_CDP_BOOT_TIMEOUT_SECONDS = 15.0
EDGE_CDP_PAGE_TIMEOUT_SECONDS = 45.0
EDGE_CDP_POLL_INTERVAL_SECONDS = 1.0
LINOVELIB_NOISE_LINE_MARKERS = (
    '最新网址',
    '请记住本书首发域名',
    '请收藏',
    '下一页',
    '上一页',
)
LINOVELIB_NEXT_PAGE_LABELS = {
    '下一页',
    '下一頁',
    '下一章',
    'next',
    'next page',
    '次へ',
}
ALICESW_READER_TOKEN_PREFIX = 'B3wlP9Tzo$0RIdlvX&^sg30^0&feAox%'
ALICESW_READER_TOKEN_SUFFIX = 'Rs4qM7mGrQ6aTMr8HHvv3WikTcY&kW8R'
ALICESW_READER_PRIVATE_KEY = '''-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAnOUiABBEw9zzOqivp4uJxTd3D5Givmwx2i+JLVdyj9iO2S1E
crWOaO5k6lD4fbL0MnMH+luJhO3ySm1xDZy22ruzvPHhd+Sh3nH56+hOcj1jfpBx
lDPlwyo2nDshY0VFr/3fonFjepp5PP+eZKYt9YWtxrVMWOc0yNH6HuRA+zwUX28W
RlP/4vMWi6vEYt0XLt+lTBGqyvwxPYJBYivIehGz4exC7K1bpvX8LJWVARkvEIuf
Y3sQHtC/BTeYoEsipfZYafTgQHJ+KAOZSq/CET0USeTt+Evfn6YcbWX577DrRyGt
siJjojMEG5TKdDQWmGKTQb4E2+EpTrQYaCcaowIDAQABAoIBAC8L9noWZshkxPre
Am43RYTB8Q3WGfsH7psCjhvukQfZZFxzWocbMiz8733j8d+ffeJy4/2K3V3jDDiN
QM1YJOzKREdwMLAG+xL9EnhPHNbc2azmG2jZdxhi3CVVBdoCt7biZeEMJ0xobdqA
vDpqKnXpNAbV7qLqEcX2UQ5aW7H6BdCgGk9HRBKXs/ll65NZmxORXLoAVg+w7Vzi
XaLP6+43KNXUPLz0EPndDH9VkGlMcyu6q7pWLoz6eN0fNiP4Jfl9PbV4KFlye2xo
4FI+Go8luM0onDL1+bKE5RJHXqfS+ow9hYzBJSz39jyNpiH7j8Hg8mMDPm0VIYtM
sOF/RgECgYEAzuuziQzrT74ZW27AQqMFQFLvqMmnrhR4CPg0mRq/PMHSzh+Bs+nS
Gib2d1ulkKIDHPOG9EWKXBOUvHOBmGro+sOS9fnfoJYeNhLmX5K1xcDJpsBOMdZv
euEit2i7yy+KAc26fP+SoCQEHm1mlgZG1vcfJlPDofqwRyBeKHPAkGMCgYEAwhvb
Fw3udE0hws92+9GYmjES8jNauBaP3hlu3lmxcnjlVqlkHbc9PkvddmCsSB/5TUCH
7qJRgYLo+uov40zNNavXv8cTqWvDrJxTuDFn0OSjeIvqS9kXeVHjpBP6d4CCLAZM
b6owfM8JtBFx9ef9ll5mwBekZDrspEXOgoCQwMECgYBujaILvFpQ7alQn5ibQcxB
dM5VKQCs0oTbjflUP+UjCg+eT1kWDfxSOrT+SnnoD5eINVjKVAk7br7N/QylqaE2
sZ1oTIu9mdckXu6064aw1HMo46AjooVHatgIlC2ZvpmGoytbM5VceEG3HA5uY4Yf
vkLnUGO6vFzIc7O6+zVMLwKBgFmIab0vkt6YOUtXUIWEvwPYQOnwoBaraX7Dcm0j
KAMqGnanuWMvgxM6ARO6MZ0vCloEuu5qdnfrfzVFUgNhCIKKGgD+fWY3K9FxZfhe
6Yjj/Tb8Kn0DzJ0MFZk4Ed6PKvvNh/I1qRnYkZw6M7t+X2y9bF2MSiplN4PqIv/0
90/BAoGAQXzOzA3q+vcA9mwKvwXrPiSscmZMekV6RBUxf1riRzTnds9uWSTKz8QM
LpEoNB3tKSB+4raK6xJGJ914b+jc/B7ayHDksStOLeJLV6t5+bmoKjk6qBrUjTQX
y8x2rsHReaJw0SbZy+4x55nYTi/0mdzomR7N27EzYtzM7iWk5w0=
-----END RSA PRIVATE KEY-----'''

crawler_threads = {}
crawler_threads_lock = threading.Lock()


class CrawlerError(RuntimeError):
    pass


class CrawlerPermanentError(CrawlerError):
    pass


class CrawlerRetryableError(CrawlerError):
    pass

def _now_timestamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _ensure_table_columns(cursor, table_name, required_columns):
    cursor.execute(f'PRAGMA table_info({table_name})')
    existing_columns = {row['name'] for row in cursor.fetchall()}

    for column_name, definition in required_columns.items():
        if column_name not in existing_columns:
            cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}')


def _ensure_crawler_task_schema(cursor):
    _ensure_table_columns(cursor, 'crawler_tasks', {
        'attempt_count': 'INTEGER DEFAULT 0',
        'max_attempts': f'INTEGER DEFAULT {CRAWLER_DEFAULT_MAX_ATTEMPTS}',
        'last_error_at': 'TIMESTAMP',
        'site_rule_id': 'INTEGER'
    })


def _ensure_crawler_site_rule_schema(cursor):
    _ensure_table_columns(cursor, 'crawler_site_rules', {
        'title_selector': 'TEXT',
        'content_selector': 'TEXT',
        'listing_link_selector': 'TEXT',
        'related_thread_selector': 'TEXT',
        'chapter_link_selector': 'TEXT',
        'chapter_title_selector': 'TEXT',
        'remove_selectors': 'TEXT',
        'notes': 'TEXT',
        'sort_order': 'INTEGER DEFAULT 100',
        'is_active': 'INTEGER DEFAULT 1',
        'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
    })


def _seed_default_crawler_site_rules(cursor):
    defaults = [
        {
            'name': 'cool18 禁忌书屋帖子页',
            'host_pattern': 'www.cool18.com',
            'title_selector': '.main-title',
            'content_selector': '.post-content',
            'listing_link_selector': 'table a[href*="app=forum&act=threadview&tid="]',
            'related_thread_selector': '.post-content a[href*="app=forum&act=threadview&tid="]',
            'chapter_link_selector': '',
            'chapter_title_selector': '.main-title',
            'remove_selectors': '.view_ad_incontent\n.ad-container\n.top-nav-container\nscript\nstyle',
            'notes': '适用于 cool18 禁忌书屋 threadview 帖子页；建议直接粘贴帖子详情页链接，不要使用版块首页列表链接。',
            'sort_order': 80,
            'is_active': 1,
        },
        {
            'name': 'AliceSW 小说页',
            'host_pattern': ALICESW_HOST,
            'title_selector': '.novel_title',
            'content_selector': '.j_readContent',
            'listing_link_selector': '',
            'related_thread_selector': '',
            'chapter_link_selector': (
                '.mulu_list a[href*="/book/"]\n'
                '.book_newchap a[href*="/other/chapters/id/"]\n'
                '.book_newchap a[href*="/book/"]'
            ),
            'chapter_title_selector': '.j_chapterName',
            'remove_selectors': 'script\nstyle\n.header\n.footer\n.read-header',
            'notes': '适用于 alicesw 的小说详情页、目录页与章节页；章节正文需要通过站点接口解密提取。',
            'sort_order': 90,
            'is_active': 1,
        },
        {
            'name': 'Linovelib 轻小说',
            'host_pattern': '*.linovelib.com',
            'title_selector': 'h1.book-title\nh1',
            'content_selector': '#acontent\n#TextContent\n.read-content',
            'listing_link_selector': '',
            'related_thread_selector': '',
            'chapter_link_selector': '.volume-list .chapter-list a[href]\n#volumes li a[href]',
            'chapter_title_selector': 'h1\n.title',
            'remove_selectors': '.cgo\n#footlink\n.mlfy_page\nscript\nstyle',
            'notes': '支持 Linovelib 目录与正文抓取，并合并同章节分页。',
            'sort_order': 95,
            'is_active': 1,
        },
        {
            'name': 'Bilinovel 轻小说',
            'host_pattern': '*.bilinovel.com',
            'title_selector': 'h1.book-title\nh1',
            'content_selector': '#acontent\n#TextContent\n.read-content',
            'listing_link_selector': '',
            'related_thread_selector': '',
            'chapter_link_selector': '.volume-list .chapter-list a[href]\n#volumes li a[href]',
            'chapter_title_selector': 'h1\n.title',
            'remove_selectors': '.cgo\n#footlink\n.mlfy_page\nscript\nstyle',
            'notes': '支持 Bilinovel 目录与正文抓取，并合并同章节分页。',
            'sort_order': 96,
            'is_active': 1,
        },
        {
            'name': 'Kakuyomu',
            'host_pattern': 'kakuyomu.jp',
            'title_selector': 'h1#workTitle\nh1',
            'content_selector': '.widget-episodeBody\n.js-episode-body',
            'listing_link_selector': '',
            'related_thread_selector': '',
            'chapter_link_selector': '',
            'chapter_title_selector': '.widget-episodeTitle\nh1',
            'remove_selectors': '.widget-toc\nscript\nstyle',
            'notes': '优先从 __NEXT_DATA__ / __APOLLO_STATE__ 提取目录。',
            'sort_order': 97,
            'is_active': 1,
        },
        {
            'name': '小説家になろう',
            'host_pattern': '*.syosetu.com',
            'title_selector': '.p-novel__title\n.novel_title\nh1',
            'content_selector': '.p-novel__text\n#novel_honbun',
            'listing_link_selector': '',
            'related_thread_selector': '',
            'chapter_link_selector': '.p-eplist a[href]\n.index_box a[href]\n.novel_sublist a[href]\n.novel_sublist2 a[href]',
            'chapter_title_selector': '.p-novel__title\n.novel_subtitle\nh1',
            'remove_selectors': 'script\nstyle',
            'notes': '适用于 syosetu / ncode 的目录与正文抓取。',
            'sort_order': 98,
            'is_active': 1,
        },
        {
            'name': 'Novel18',
            'host_pattern': 'novel18.syosetu.com',
            'title_selector': '.p-novel__title\n.novel_title\nh1',
            'content_selector': '.p-novel__text\n#novel_honbun',
            'listing_link_selector': '',
            'related_thread_selector': '',
            'chapter_link_selector': '.p-eplist a[href]\n.index_box a[href]\n.novel_sublist a[href]\n.novel_sublist2 a[href]',
            'chapter_title_selector': '.p-novel__title\n.novel_subtitle\nh1',
            'remove_selectors': 'script\nstyle',
            'notes': '适用于 Novel18，抓取时自动附带 over18 cookie。',
            'sort_order': 99,
            'is_active': 1,
        },
        {
            'name': 'Pixiv 小说',
            'host_pattern': 'www.pixiv.net',
            'title_selector': 'h1\ntitle',
            'content_selector': '',
            'listing_link_selector': '',
            'related_thread_selector': '',
            'chapter_link_selector': '',
            'chapter_title_selector': 'h1\ntitle',
            'remove_selectors': 'script\nstyle',
            'notes': '支持 Pixiv 单篇与系列；目录和正文通过 ajax 接口抓取。',
            'sort_order': 100,
            'is_active': 1,
        },
        {
            'name': 'Hameln',
            'host_pattern': 'syosetu.org',
            'title_selector': 'h1\n.title',
            'content_selector': '#honbun',
            'listing_link_selector': '',
            'related_thread_selector': '',
            'chapter_link_selector': 'table tr a[href$=".html"]',
            'chapter_title_selector': 'h1\n.title',
            'remove_selectors': 'script\nstyle',
            'notes': '支持 Hameln 目录与正文抓取，正文会附加后记内容。',
            'sort_order': 101,
            'is_active': 1,
        },
        {
            'name': 'Alphapolis',
            'host_pattern': 'www.alphapolis.co.jp',
            'title_selector': 'h1\ntitle',
            'content_selector': '#novelBody',
            'listing_link_selector': '',
            'related_thread_selector': '',
            'chapter_link_selector': '',
            'chapter_title_selector': 'h1\n.title',
            'remove_selectors': '.dots-indicator\n.g-recaptcha\n#LoadingEpisode\nscript\nstyle',
            'notes': '优先解析 #app-cover-data；必要时通过 Edge CDP 会话兜底抓取。',
            'sort_order': 102,
            'is_active': 1,
        }
    ]

    for item in defaults:
        cursor.execute(
            '''
            SELECT id, listing_link_selector, related_thread_selector, chapter_title_selector, title_selector,
                   content_selector, chapter_link_selector, remove_selectors
            FROM crawler_site_rules
            WHERE host_pattern = ?
            ''',
            (item['host_pattern'],)
        )
        existing = cursor.fetchone()
        if existing:
            updates = []
            params = []
            if not (existing['listing_link_selector'] or '').strip() and item.get('listing_link_selector'):
                updates.append('listing_link_selector = ?')
                params.append(item['listing_link_selector'])
            if not (existing['related_thread_selector'] or '').strip() and item.get('related_thread_selector'):
                updates.append('related_thread_selector = ?')
                params.append(item['related_thread_selector'])
            if not (existing['chapter_title_selector'] or '').strip() and item.get('chapter_title_selector'):
                updates.append('chapter_title_selector = ?')
                params.append(item['chapter_title_selector'])
            if not (existing['title_selector'] or '').strip() and item.get('title_selector'):
                updates.append('title_selector = ?')
                params.append(item['title_selector'])
            if not (existing['content_selector'] or '').strip() and item.get('content_selector'):
                updates.append('content_selector = ?')
                params.append(item['content_selector'])
            if not (existing['chapter_link_selector'] or '').strip() and item.get('chapter_link_selector'):
                updates.append('chapter_link_selector = ?')
                params.append(item['chapter_link_selector'])
            if not (existing['remove_selectors'] or '').strip() and item.get('remove_selectors'):
                updates.append('remove_selectors = ?')
                params.append(item['remove_selectors'])
            if updates:
                updates.append('updated_at = ?')
                params.append(_now_timestamp())
                params.append(existing['id'])
                cursor.execute(f'UPDATE crawler_site_rules SET {", ".join(updates)} WHERE id = ?', params)
            continue
        cursor.execute(
            '''
            INSERT INTO crawler_site_rules (
                name, host_pattern, title_selector, content_selector, listing_link_selector, related_thread_selector,
                chapter_link_selector, chapter_title_selector,
                remove_selectors, notes, sort_order, is_active, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                item['name'],
                item['host_pattern'],
                item['title_selector'],
                item['content_selector'],
                item['listing_link_selector'],
                item['related_thread_selector'],
                item['chapter_link_selector'],
                item['chapter_title_selector'],
                item['remove_selectors'],
                item['notes'],
                item['sort_order'],
                item['is_active'],
                _now_timestamp(),
            )
        )


def _recover_interrupted_crawler_tasks(cursor):
    now = _now_timestamp()
    cursor.execute(
        '''
        UPDATE crawler_tasks
        SET status = 'pending',
            progress = 0,
            total_chapters = 0,
            crawled_chapters = 0,
            started_at = NULL,
            finished_at = NULL,
            last_error = ?,
            last_error_at = ?,
            updated_at = ?
        WHERE status = 'running'
        ''',
        ('任务在服务重启后已恢复为待执行状态，请重新开始抓取', now, now)
    )


def _sanitize_crawler_max_attempts(value):
    try:
        attempts = int(value)
    except (TypeError, ValueError):
        attempts = CRAWLER_DEFAULT_MAX_ATTEMPTS

    return max(1, min(attempts, CRAWLER_MAX_ALLOWED_ATTEMPTS))


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


def _sanitize_crawler_rule_sort_order(value):
    try:
        return max(0, min(int(value), 9999))
    except (TypeError, ValueError):
        return 100


def _sanitize_crawler_listing_limit(value):
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = 10
    return max(1, min(limit, CRAWLER_LISTING_BATCH_MAX))


def _normalize_crawler_host_pattern(value):
    host = str(value or '').strip().lower()
    host = re.sub(r'^[a-z]+://', '', host)
    host = host.split('/', 1)[0].split('?', 1)[0].split('#', 1)[0].strip()
    if not host:
        raise ValueError('请填写站点域名，例如 example.com 或 *.example.com')

    is_wildcard = host.startswith('*.')
    normalized = host[2:] if is_wildcard else host
    normalized = normalized.split(':', 1)[0].strip('.')

    if not normalized or '.' not in normalized:
        raise ValueError('站点域名格式不正确，例如 example.com 或 *.example.com')
    if '..' in normalized or normalized.startswith('-') or normalized.endswith('-'):
        raise ValueError('站点域名格式不正确')
    if not re.fullmatch(r'[a-z0-9.-]+', normalized):
        raise ValueError('站点域名仅支持字母、数字、点和短横线')

    return f'*.{normalized}' if is_wildcard else normalized


def _iter_crawler_selectors(value):
    for raw_line in str(value or '').splitlines():
        selector = raw_line.strip()
        if selector:
            yield selector


def _import_bs4():
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup
    except ImportError as exc:
        raise CrawlerPermanentError('缺少爬虫规则解析依赖，请先安装 beautifulsoup4') from exc


def _serialize_crawler_site_rule(row):
    item = dict(row)
    item['sort_order'] = _sanitize_crawler_rule_sort_order(item.get('sort_order'))
    item['is_active'] = bool(item.get('is_active', 1))
    item['host_pattern'] = _normalize_crawler_host_pattern(item.get('host_pattern'))
    for key in (
        'title_selector',
        'content_selector',
        'listing_link_selector',
        'related_thread_selector',
        'chapter_link_selector',
        'chapter_title_selector',
        'remove_selectors',
        'notes',
    ):
        item[key] = str(item.get(key) or '').strip()
    return item


def _fetch_crawler_site_rule(rule_id):
    if not rule_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM crawler_site_rules WHERE id = ?', (rule_id,))
    row = cursor.fetchone()
    conn.close()
    return _serialize_crawler_site_rule(row) if row else None


def _fetch_crawler_site_rules(active_only=False):
    conn = get_db()
    cursor = conn.cursor()
    query = 'SELECT * FROM crawler_site_rules'
    params = []
    if active_only:
        query += ' WHERE is_active = 1'
    query += ' ORDER BY sort_order ASC, LENGTH(host_pattern) DESC, host_pattern ASC'
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [_serialize_crawler_site_rule(row) for row in rows]


def _build_crawler_site_rule_payload(data):
    payload = {
        'name': str((data or {}).get('name') or '').strip(),
        'host_pattern': _normalize_crawler_host_pattern((data or {}).get('host_pattern') or ''),
        'title_selector': str((data or {}).get('title_selector') or '').strip(),
        'content_selector': str((data or {}).get('content_selector') or '').strip(),
        'listing_link_selector': str((data or {}).get('listing_link_selector') or '').strip(),
        'related_thread_selector': str((data or {}).get('related_thread_selector') or '').strip(),
        'chapter_link_selector': str((data or {}).get('chapter_link_selector') or '').strip(),
        'chapter_title_selector': str((data or {}).get('chapter_title_selector') or '').strip(),
        'remove_selectors': str((data or {}).get('remove_selectors') or '').strip(),
        'notes': str((data or {}).get('notes') or '').strip(),
        'sort_order': _sanitize_crawler_rule_sort_order((data or {}).get('sort_order')),
        'is_active': 1 if bool((data or {}).get('is_active', True)) else 0,
    }

    if not payload['name']:
        raise ValueError('请填写规则名称')
    if not payload['content_selector']:
        raise ValueError('请至少填写正文选择器')

    return payload


def _host_matches_crawler_pattern(hostname, pattern):
    hostname = str(hostname or '').strip().lower().strip('.')
    pattern = str(pattern or '').strip().lower().strip('.')
    if not hostname or not pattern:
        return False
    if pattern.startswith('*.'):
        suffix = pattern[2:]
        return hostname == suffix or hostname.endswith(f'.{suffix}')
    return hostname == pattern


def _resolve_crawler_site_rule(source_url, preferred_rule_id=None, rules=None):
    if preferred_rule_id:
        explicit_rule = _fetch_crawler_site_rule(preferred_rule_id)
        if explicit_rule:
            return explicit_rule

    hostname = (urlparse(source_url or '').hostname or '').strip().lower()
    if not hostname:
        return None

    candidates = rules if rules is not None else _fetch_crawler_site_rules(active_only=True)
    matched = [rule for rule in candidates if rule.get('is_active') and _host_matches_crawler_pattern(hostname, rule.get('host_pattern'))]
    if not matched:
        return None

    matched.sort(key=lambda item: (
        1 if str(item.get('host_pattern') or '').startswith('*.') else 0,
        -len(str(item.get('host_pattern') or '')),
        _sanitize_crawler_rule_sort_order(item.get('sort_order')),
        item.get('id') or 0,
    ))
    return matched[0]


def _select_first_crawler_element(soup, selector_text):
    for selector in _iter_crawler_selectors(selector_text):
        try:
            element = soup.select_one(selector)
        except Exception:
            continue
        if element is not None:
            return element
    return None


def _select_many_crawler_elements(soup, selector_text):
    for selector in _iter_crawler_selectors(selector_text):
        try:
            elements = soup.select(selector)
        except Exception:
            continue
        if elements:
            return elements
    return []


def _remove_crawler_elements(scope, selector_text):
    for selector in _iter_crawler_selectors(selector_text):
        try:
            elements = scope.select(selector)
        except Exception:
            continue
        for element in elements:
            element.decompose()


def _extract_rule_selected_text(raw_html, selector_text, remove_selectors=''):
    if not str(selector_text or '').strip():
        return ''

    BeautifulSoup = _import_bs4()
    soup = BeautifulSoup(raw_html or '', 'html.parser')
    target = _select_first_crawler_element(soup, selector_text)
    if target is None:
        return ''

    target = BeautifulSoup(str(target), 'html.parser')
    if remove_selectors:
        _remove_crawler_elements(target, remove_selectors)
    return _html_to_text(str(target)).strip()


def _extract_chapter_links_with_rule(raw_html, base_url, rule):
    selector_text = (rule or {}).get('chapter_link_selector')
    if not str(selector_text or '').strip():
        return []

    BeautifulSoup = _import_bs4()
    soup = BeautifulSoup(raw_html or '', 'html.parser')
    source_host = (urlparse(base_url or '').hostname or '').strip().lower()
    host_pattern = str((rule or {}).get('host_pattern') or '').strip().lower()
    links = []
    seen = set()

    for element in _select_many_crawler_elements(soup, selector_text):
        candidates = [element] if getattr(element, 'name', None) == 'a' and element.get('href') else element.select('a[href]')
        for anchor in candidates:
            href = html.unescape((anchor.get('href') or '').strip())
            if not href or href.startswith(('javascript:', '#', 'mailto:')):
                continue

            full_url = urljoin(base_url, href).split('#', 1)[0]
            parsed = urlparse(full_url)
            if parsed.scheme not in ('http', 'https'):
                continue
            target_host = (parsed.hostname or '').strip().lower()
            if host_pattern:
                if target_host and not _host_matches_crawler_pattern(target_host, host_pattern):
                    continue
            elif source_host and target_host and target_host != source_host:
                continue

            label = _html_to_text(str(anchor)).strip()
            if not label:
                label = _html_to_text(anchor.get_text(' ', strip=True)).strip()
            if not label:
                continue

            dedupe_key = full_url.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            links.append({'url': full_url, 'title': label})

    return links


def _extract_listing_thread_links(raw_html, base_url, rule=None):
    selector_text = (rule or {}).get('listing_link_selector')
    host_pattern = str((rule or {}).get('host_pattern') or '').strip().lower()
    source_host = (urlparse(base_url or '').hostname or '').strip().lower()
    navigation_labels = {'书库藏文', '本版精华区', '人气热贴', '返回禁忌书屋首页'}

    def _append_link(results, seen, href, label):
        href = html.unescape((href or '').strip())
        if not href or href.startswith(('javascript:', '#', 'mailto:')):
            return

        full_url = urljoin(base_url, href).split('#', 1)[0]
        parsed = urlparse(full_url)
        if parsed.scheme not in ('http', 'https'):
            return

        target_host = (parsed.hostname or '').strip().lower()
        if host_pattern:
            if target_host and not _host_matches_crawler_pattern(target_host, host_pattern):
                return
        elif source_host and target_host and target_host != source_host:
            return

        lowered_url = full_url.lower()
        if 'threadview' not in lowered_url or 'tid=' not in lowered_url:
            return

        clean_label = re.sub(r'\s+', ' ', (label or '')).strip()
        if not clean_label or clean_label.isdigit() or clean_label in navigation_labels:
            return
        if len(clean_label) > 120:
            return

        dedupe_key = full_url.lower()
        if dedupe_key in seen:
            return
        seen.add(dedupe_key)
        results.append({'url': full_url, 'title': clean_label})

    results = []
    seen = set()

    if selector_text:
        BeautifulSoup = _import_bs4()
        soup = BeautifulSoup(raw_html or '', 'html.parser')
        for element in _select_many_crawler_elements(soup, selector_text):
            candidates = [element] if getattr(element, 'name', None) == 'a' and element.get('href') else element.select('a[href]')
            for anchor in candidates:
                _append_link(results, seen, anchor.get('href'), _html_to_text(str(anchor)))
        if results:
            return results

    link_pattern = re.compile(r'(?is)<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>')
    for href, label_html in link_pattern.findall(raw_html or ''):
        _append_link(results, seen, href, _html_to_text(label_html))

    return results


def _normalize_crawler_sequence_text(value):
    text = str(value or '')
    fullwidth_digits = str.maketrans('０１２３４５６７８９', '0123456789')
    return text.translate(fullwidth_digits)


def _extract_crawler_sequence_start(value):
    text = _normalize_crawler_sequence_text(value)
    match = re.search(r'(\d{1,4})(?:\s*[-~—－到至]\s*\d{1,4})?', text)
    if match:
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return 10 ** 9
    return 10 ** 9


def _extract_related_thread_links(raw_html, base_url, rule=None):
    selector_text = (rule or {}).get('related_thread_selector')
    if not str(selector_text or '').strip():
        return []

    BeautifulSoup = _import_bs4()
    soup = BeautifulSoup(raw_html or '', 'html.parser')
    source_host = (urlparse(base_url or '').hostname or '').strip().lower()
    host_pattern = str((rule or {}).get('host_pattern') or '').strip().lower()
    current_url = urljoin(base_url, '').split('#', 1)[0].lower()
    links = []
    seen = set()

    for element in _select_many_crawler_elements(soup, selector_text):
        candidates = [element] if getattr(element, 'name', None) == 'a' and element.get('href') else element.select('a[href]')
        for anchor in candidates:
            href = html.unescape((anchor.get('href') or '').strip())
            if not href or href.startswith(('javascript:', '#', 'mailto:')):
                continue

            full_url = urljoin(base_url, href).split('#', 1)[0]
            parsed = urlparse(full_url)
            if parsed.scheme not in ('http', 'https'):
                continue

            target_host = (parsed.hostname or '').strip().lower()
            if host_pattern:
                if target_host and not _host_matches_crawler_pattern(target_host, host_pattern):
                    continue
            elif source_host and target_host and target_host != source_host:
                continue

            lowered_url = full_url.lower()
            if lowered_url == current_url or 'threadview' not in lowered_url or 'tid=' not in lowered_url:
                continue

            label = _html_to_text(str(anchor)).strip()
            if not label or label in {'返回主帖', '返回目录', '返回列表'}:
                continue

            dedupe_key = lowered_url
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            links.append({'url': full_url, 'title': label})

    links.sort(key=lambda item: (_extract_crawler_sequence_start(item.get('title')), item.get('url') or ''))
    return links


def _apply_effective_rule_to_crawler_task(item, rules=None):
    rule = _resolve_crawler_site_rule(
        item.get('source_url'),
        preferred_rule_id=item.get('site_rule_id'),
        rules=rules,
    )
    item['effective_site_rule_id'] = rule.get('id') if rule else None
    item['effective_site_rule_name'] = rule.get('name') if rule else '通用规则'
    item['effective_site_rule_host_pattern'] = rule.get('host_pattern') if rule else ''
    item['effective_site_rule_mode'] = 'manual' if item.get('site_rule_id') else ('auto' if rule else 'default')
    return item


def _serialize_crawler_task(row, rules=None):
    item = dict(row)
    item['attempt_count'] = max(0, int(item.get('attempt_count') or 0))
    item['max_attempts'] = _sanitize_crawler_max_attempts(item.get('max_attempts'))
    item['tag_ids'] = [int(tag_id) for tag_id in _safe_json_list(item.get('tag_ids_json')) if str(tag_id).isdigit()]
    item['site_rule_id'] = int(item['site_rule_id']) if str(item.get('site_rule_id') or '').isdigit() else None
    item.pop('tag_ids_json', None)
    return _apply_effective_rule_to_crawler_task(item, rules=rules)


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
    rules = _fetch_crawler_site_rules(active_only=True) if row else None
    return _serialize_crawler_task(row, rules=rules) if row else None


def _guess_title_from_url(url):
    parsed = urlparse(url)
    name = Path(unquote(parsed.path or '')).stem
    name = re.sub(r'[-_]+', ' ', name).strip()
    return name or parsed.netloc or '未命名小说'


def _is_disallowed_crawler_ip(ip_obj):
    return any((
        ip_obj.is_private,
        ip_obj.is_loopback,
        ip_obj.is_link_local,
        ip_obj.is_multicast,
        ip_obj.is_reserved,
        ip_obj.is_unspecified
    ))


def _resolve_crawler_target_ips(hostname):
    normalized = (hostname or '').strip().strip('[]')
    if not normalized:
        raise CrawlerPermanentError('抓取链接缺少有效域名')

    try:
        return [ipaddress.ip_address(normalized)]
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(normalized, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise CrawlerRetryableError(f'无法解析目标地址: {normalized}') from exc

    resolved_ips = []
    seen = set()
    for _, _, _, _, sockaddr in infos:
        ip_text = (sockaddr[0] or '').split('%', 1)[0]
        if not ip_text or ip_text in seen:
            continue
        seen.add(ip_text)
        resolved_ips.append(ipaddress.ip_address(ip_text))

    if not resolved_ips:
        raise CrawlerRetryableError(f'无法解析目标地址: {normalized}')

    return resolved_ips


def _validate_crawler_target_url(url):
    parsed = urlparse((url or '').strip())
    if parsed.scheme not in ('http', 'https'):
        raise CrawlerPermanentError('仅支持抓取 http:// 或 https:// 链接')

    if not parsed.netloc or not parsed.hostname:
        raise CrawlerPermanentError('抓取链接缺少有效域名')

    if CRAWLER_ALLOW_PRIVATE_TARGETS:
        return parsed.geturl()

    hostname = parsed.hostname.strip().lower()
    if hostname == 'localhost':
        raise CrawlerPermanentError('默认禁止抓取本地或内网地址；如需开启，请设置 ALLOW_PRIVATE_CRAWLER_TARGETS=1')

    for ip_obj in _resolve_crawler_target_ips(hostname):
        if _is_disallowed_crawler_ip(ip_obj):
            raise CrawlerPermanentError('默认禁止抓取本地或内网地址；如需开启，请设置 ALLOW_PRIVATE_CRAWLER_TARGETS=1')

    return parsed.geturl()


def _host_matches_keywords(source_url, keywords):
    hostname = (urlparse(source_url or '').hostname or '').strip().lower()
    return any(hostname == keyword or hostname.endswith(f'.{keyword}') for keyword in keywords)


def _is_linovelib_url(source_url):
    return _host_matches_keywords(source_url, LINOVELIB_HOST_KEYWORDS)


def _is_kakuyomu_url(source_url):
    return _host_matches_keywords(source_url, KAKUYOMU_HOST_KEYWORDS)


def _is_syosetu_url(source_url):
    hostname = (urlparse(source_url or '').hostname or '').strip().lower()
    return _host_matches_keywords(source_url, SYOSETU_HOST_KEYWORDS) and 'novel18.' not in hostname


def _is_novel18_url(source_url):
    hostname = (urlparse(source_url or '').hostname or '').strip().lower()
    return hostname == 'novel18.syosetu.com' or hostname.endswith('.novel18.syosetu.com')


def _is_pixiv_url(source_url):
    return _host_matches_keywords(source_url, PIXIV_HOST_KEYWORDS)


def _is_hameln_url(source_url):
    return _host_matches_keywords(source_url, HAMELN_HOST_KEYWORDS)


def _is_alphapolis_url(source_url):
    return _host_matches_keywords(source_url, ALPHAPOLIS_HOST_KEYWORDS)


def _pixiv_novel_id_from_url(source_url):
    parsed = urlparse(source_url or '')
    if parsed.path != PIXIV_NOVEL_SHOW_PATH:
        return None
    novel_id = parse_qs(parsed.query or '').get('id', [''])[0].strip()
    return novel_id or None


def _pixiv_series_id_from_url(source_url):
    match = PIXIV_SERIES_PATH_PATTERN.match(urlparse(source_url or '').path)
    if not match:
        return None
    series_id = (match.group('series_id') or '').strip()
    return series_id or None


def _kakuyomu_work_id_from_url(source_url):
    match = KAKUYOMU_WORK_PATH_PATTERN.match(urlparse(source_url or '').path)
    if not match:
        return None
    work_id = (match.group('work_id') or '').strip()
    return work_id or None


def _build_crawler_request_headers(url, referer=None, extra_headers=None):
    parsed = urlparse(url or '')
    origin_referer = referer or (f'{parsed.scheme}://{parsed.netloc}/' if parsed.scheme and parsed.netloc else '')
    headers = {
        'User-Agent': CRAWLER_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    if origin_referer:
        headers['Referer'] = origin_referer

    if _is_syosetu_url(url) or _is_novel18_url(url) or _is_hameln_url(url):
        headers['Accept-Language'] = 'ja,en;q=0.9'
        headers['Accept-Encoding'] = 'identity'
    elif _is_pixiv_url(url):
        headers['Accept-Language'] = 'ja,en;q=0.9'

    if extra_headers:
        for key, value in extra_headers.items():
            if value is None:
                continue
            headers[str(key)] = str(value)

    return headers


def _build_crawler_request_cookies(url, cookies=None):
    merged = {}
    if cookies:
        for key, value in cookies.items():
            if key and value is not None:
                merged[str(key)] = str(value)

    if _is_syosetu_url(url) or _is_novel18_url(url):
        merged.setdefault('over18', 'yes')
    return merged or None


def _request_url(url, referer=None, extra_headers=None, cookies=None):
    validated_url = _validate_crawler_target_url(url)
    last_error = None

    for attempt in range(1, CRAWLER_REQUEST_RETRIES + 1):
        response = None

        try:
            request_headers = _build_crawler_request_headers(
                validated_url,
                referer=referer,
                extra_headers=extra_headers,
            )
            request_cookies = _build_crawler_request_cookies(validated_url, cookies=cookies)
            response = requests.get(
                validated_url,
                headers=request_headers,
                cookies=request_cookies,
                timeout=(CRAWLER_CONNECT_TIMEOUT, CRAWLER_READ_TIMEOUT),
                stream=True
            )
            _validate_crawler_target_url(response.url or validated_url)

            if response.status_code in {429, 500, 502, 503, 504}:
                raise CrawlerRetryableError(f'目标站点暂时不可用，返回 HTTP {response.status_code}')

            response.raise_for_status()

            payload = bytearray()
            for chunk in response.iter_content(chunk_size=16384):
                if not chunk:
                    continue
                payload.extend(chunk)
                if len(payload) > CRAWLER_RESPONSE_SIZE_LIMIT:
                    limit_mb = CRAWLER_RESPONSE_SIZE_LIMIT // (1024 * 1024)
                    raise CrawlerPermanentError(f'抓取内容过大，超过 {limit_mb} MB 限制')

            response._content = bytes(payload)
            response._content_consumed = True

            if not response.encoding or response.encoding.lower() == 'iso-8859-1':
                response.encoding = response.apparent_encoding or 'utf-8'

            return response
        except CrawlerPermanentError:
            raise
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else 'unknown'
            if status_code in {429, 500, 502, 503, 504}:
                last_error = CrawlerRetryableError(f'目标站点暂时不可用，返回 HTTP {status_code}')
            else:
                raise CrawlerPermanentError(f'目标站点返回 HTTP {status_code}') from exc
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = CrawlerRetryableError(f'网络请求失败: {exc}')
        except requests.RequestException as exc:
            last_error = CrawlerRetryableError(f'抓取请求失败: {exc}')
        finally:
            if response is not None:
                response.close()

        if attempt < CRAWLER_REQUEST_RETRIES:
            time.sleep(CRAWLER_RETRY_BACKOFF_SECONDS * attempt)

    if last_error:
        raise CrawlerRetryableError(
            f'{last_error}（已自动重试 {CRAWLER_REQUEST_RETRIES} 次）'
        ) from last_error

    raise CrawlerRetryableError('抓取请求失败，请稍后重试')


def _import_crawler_crypto():
    try:
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5, AES
        return RSA, PKCS1_v1_5, AES
    except Exception as exc:
        raise CrawlerPermanentError('缺少 pycryptodome 依赖，无法抓取 AliceSW 章节正文') from exc


def _is_alicesw_site_rule(rule=None, source_url=''):
    host_pattern = str((rule or {}).get('host_pattern') or '').strip().lower()
    if host_pattern and (
        host_pattern == ALICESW_HOST
        or host_pattern.endswith('.alicesw.com')
        or host_pattern == '*.alicesw.com'
    ):
        return True

    hostname = (urlparse(source_url or '').hostname or '').strip().lower()
    return hostname == ALICESW_HOST or hostname.endswith('.alicesw.com')


def _looks_like_alicesw_placeholder_text(text):
    sample = str(text or '')
    if not sample:
        return True
    return (
        '章节加载中' in sample
        or ('加载中' in sample and '快速导航' in sample and '最近阅读' in sample)
    )


def _extract_alicesw_chapter_request_params(raw_html):
    block_match = re.search(r'book\.initial\s*=\s*\{(.*?)\}\s*;', raw_html or '', re.IGNORECASE | re.DOTALL)
    if not block_match:
        return None

    block = block_match.group(1)

    def _extract(pattern):
        match = re.search(pattern, block, re.IGNORECASE)
        return (match.group(1) if match else '').strip()

    source_id = _extract(r'source_id\s*:\s*(\d+)')
    chapter_id = _extract(r'chapter_id\s*:\s*[\'"]([^\'"]+)[\'"]')
    chapter_t = _extract(r'\bt\s*:\s*[\'"]?(\d+)[\'"]?')
    chapter_sign = _extract(r'sign\s*:\s*[\'"]([^\'"]+)[\'"]')

    if not all((source_id, chapter_id, chapter_t, chapter_sign)):
        return None

    return {
        'source_id': source_id,
        'chapter_id': chapter_id,
        'chapter_t': chapter_t,
        'chapter_sign': chapter_sign,
    }


def _build_alicesw_reader_token(timestamp, source_id, chapter_id):
    message = f'{ALICESW_READER_TOKEN_PREFIX}{timestamp}{source_id}{chapter_id}{ALICESW_READER_TOKEN_SUFFIX}'
    return hashlib.sha256(message.encode('utf-8')).hexdigest()


def _request_alicesw_chapter_payload(chapter_url, params):
    source_id = str((params or {}).get('source_id') or '').strip()
    chapter_id = str((params or {}).get('chapter_id') or '').strip()
    chapter_t = str((params or {}).get('chapter_t') or '').strip()
    chapter_sign = str((params or {}).get('chapter_sign') or '').strip()
    if not all((source_id, chapter_id, chapter_t, chapter_sign)):
        raise CrawlerRetryableError('AliceSW 章节参数不完整，无法请求章节接口')

    api_url = (
        f'https://{ALICESW_HOST}/home/chapter/info'
        f'?id={source_id}&key={chapter_id}&t={chapter_t}&sign={chapter_sign}'
    )
    validated_api_url = _validate_crawler_target_url(api_url)
    validated_referer_url = _validate_crawler_target_url(chapter_url)
    last_error = None

    for attempt in range(1, CRAWLER_REQUEST_RETRIES + 1):
        response = None
        try:
            timestamp = str(int(time.time()))
            token = _build_alicesw_reader_token(timestamp, source_id, chapter_id)
            response = requests.get(
                validated_api_url,
                headers={
                    'User-Agent': CRAWLER_USER_AGENT,
                    'Referer': validated_referer_url,
                    'X-Requested-With': 'XMLHttpRequest',
                    'x-request-timestamp': timestamp,
                    'x-request-token': token,
                },
                timeout=(CRAWLER_CONNECT_TIMEOUT, CRAWLER_READ_TIMEOUT),
            )
            _validate_crawler_target_url(response.url or validated_api_url)
            response.raise_for_status()
            payload = response.json()
            if int(payload.get('code') or 0) != 1:
                raise CrawlerRetryableError(f'AliceSW 章节接口返回异常: {payload.get("msg") or "unknown"}')
            return payload
        except CrawlerPermanentError:
            raise
        except ValueError as exc:
            last_error = CrawlerRetryableError('AliceSW 章节接口返回非 JSON 数据')
            if attempt >= CRAWLER_REQUEST_RETRIES:
                raise last_error from exc
        except requests.RequestException as exc:
            last_error = CrawlerRetryableError(f'AliceSW 章节接口请求失败: {exc}')
            if attempt >= CRAWLER_REQUEST_RETRIES:
                raise last_error from exc
        except CrawlerError as exc:
            last_error = exc
            if attempt >= CRAWLER_REQUEST_RETRIES:
                raise
        finally:
            if response is not None:
                response.close()

        time.sleep(CRAWLER_RETRY_BACKOFF_SECONDS * attempt)

    if last_error:
        raise last_error
    raise CrawlerRetryableError('AliceSW 章节接口请求失败')


def _decrypt_alicesw_chapter_html(chapter_payload):
    chapter = ((chapter_payload or {}).get('data') or {}).get('chapter') or {}
    content_encrypt = str(chapter.get('content_encrypt') or '').strip()
    aes_key_encrypt = str(chapter.get('aes_key_encrypt') or '').strip()
    iv_encoded = str(chapter.get('iv') or '').strip()
    if not (content_encrypt and aes_key_encrypt and iv_encoded):
        return ''

    RSA, PKCS1_v1_5, AES = _import_crawler_crypto()
    rsa_key = RSA.import_key(ALICESW_READER_PRIVATE_KEY)
    rsa_cipher = PKCS1_v1_5.new(rsa_key)

    try:
        decrypted_key = rsa_cipher.decrypt(base64.b64decode(aes_key_encrypt), b'')
        if not decrypted_key:
            return ''
        aes_key = base64.b64decode(decrypted_key.decode('utf-8'))
        iv_bytes = base64.b64decode(iv_encoded)
        cipher_bytes = base64.b64decode(content_encrypt)
    except Exception as exc:
        raise CrawlerRetryableError(f'AliceSW 章节解密参数解析失败: {exc}') from exc

    if len(aes_key) not in {16, 24, 32}:
        raise CrawlerRetryableError('AliceSW 章节解密密钥长度异常')
    if len(iv_bytes) != 16:
        raise CrawlerRetryableError('AliceSW 章节解密向量长度异常')

    try:
        plain_bytes = AES.new(aes_key, AES.MODE_CBC, iv_bytes).decrypt(cipher_bytes)
    except Exception as exc:
        raise CrawlerRetryableError(f'AliceSW 章节解密失败: {exc}') from exc

    padding = plain_bytes[-1] if plain_bytes else 0
    if 1 <= padding <= 16 and plain_bytes.endswith(bytes([padding]) * padding):
        plain_bytes = plain_bytes[:-padding]

    return plain_bytes.decode('utf-8', errors='ignore').strip()


def _extract_alicesw_chapter_content(raw_html, chapter_url):
    params = _extract_alicesw_chapter_request_params(raw_html)
    if not params:
        return '', ''

    payload = _request_alicesw_chapter_payload(chapter_url, params)
    chapter = ((payload or {}).get('data') or {}).get('chapter') or {}
    chapter_title = str(chapter.get('title') or '').strip()
    html_content = _decrypt_alicesw_chapter_html(payload)
    if not html_content:
        return chapter_title, ''

    return chapter_title, _html_to_text(html_content)


def _expand_alicesw_chapter_links(raw_html, base_url, rule, links):
    chapter_links = list(links or [])
    if not _is_alicesw_site_rule(rule, base_url):
        return chapter_links

    listing_url = ''
    for item in chapter_links:
        current_url = str((item or {}).get('url') or '')
        if '/other/chapters/' in current_url:
            listing_url = current_url
            break

    if not listing_url:
        listing_match = re.search(r'(?is)href=["\']([^"\']*/other/chapters/[^"\']+)["\']', raw_html or '')
        if listing_match:
            listing_url = urljoin(base_url, html.unescape(listing_match.group(1))).split('#', 1)[0]

    if not listing_url:
        return chapter_links

    listing_response = _request_url(listing_url)
    listing_links = _extract_chapter_links_with_rule(listing_response.text, listing_url, rule)
    if len(listing_links) >= 2:
        return listing_links
    return chapter_links


def _is_probable_linovelib_page(soup):
    return bool(
        soup.select_one('#volumes')
        or soup.select_one('#volume-list')
        or soup.select_one('.volume-list')
        or soup.select_one('#acontent')
        or soup.select_one('#TextContent')
        or soup.select_one("[property='og:novel:book_name']")
    )


def _extract_linovelib_volume_blocks(soup, base_url):
    items = []
    seen = set()

    for volume in soup.select('.volume-list .volume'):
        volume_title = ''
        title_node = volume.select_one('.volume-info h2, h2.v-line, h3')
        if title_node and title_node.get_text(' ', strip=True):
            volume_title = title_node.get_text(' ', strip=True)

        for anchor in volume.select('.chapter-list a[href], ul.chapter-list a[href]'):
            href = str(anchor.get('href', '')).strip()
            chapter_title = anchor.get_text(' ', strip=True)
            if not href or not chapter_title or href.startswith('javascript:'):
                continue
            absolute_url = urljoin(base_url, href).split('#', 1)[0]
            if absolute_url in seen:
                continue
            seen.add(absolute_url)
            if volume_title:
                chapter_title = f'{volume_title} - {chapter_title}'
            items.append({'title': chapter_title[:180], 'url': absolute_url})

    return items


def _extract_linovelib_chapters(soup, base_url):
    items = _extract_linovelib_volume_blocks(soup, base_url)
    if items:
        return items

    items = []
    seen = set()
    current_volume = ''

    for node in soup.select('#volumes li'):
        classes = node.get('class') or []
        text = node.get_text(' ', strip=True)
        if not text:
            continue

        if 'chapter-bar' in classes:
            current_volume = text
            continue

        anchor = node.find('a', href=True)
        if anchor is None:
            continue

        href = str(anchor.get('href', '')).strip()
        chapter_title = anchor.get_text(' ', strip=True) or text
        if not href or not chapter_title:
            continue

        absolute_url = urljoin(base_url, href).split('#', 1)[0]
        if absolute_url in seen:
            continue
        seen.add(absolute_url)

        if current_volume:
            chapter_title = f'{current_volume} - {chapter_title}'
        items.append({'title': chapter_title[:180], 'url': absolute_url})

    return items


def _kakuyomu_state_from_html(raw_html):
    BeautifulSoup = _import_bs4()
    soup = BeautifulSoup(raw_html or '', 'html.parser')
    script = soup.select_one('#__NEXT_DATA__')
    payload_text = ''
    if script is not None:
        payload_text = script.string or script.get_text('', strip=True)
    if not payload_text:
        return {}

    try:
        payload = json.loads(payload_text)
    except Exception:
        return {}

    state = (payload.get('props') or {}).get('pageProps', {}).get('__APOLLO_STATE__')
    return state if isinstance(state, dict) else {}


def _kakuyomu_chapters_from_state(state, source_url):
    work_id = _kakuyomu_work_id_from_url(source_url)
    if not work_id:
        return []
    work = state.get(f'Work:{work_id}')
    if not isinstance(work, dict):
        return []

    items = []
    seen = set()
    origin = 'https://kakuyomu.jp'

    for toc_ref in work.get('tableOfContents', []):
        ref_key = toc_ref.get('__ref') if isinstance(toc_ref, dict) else None
        toc = state.get(str(ref_key or ''))
        if not isinstance(toc, dict):
            continue

        chapter_title = ''
        chapter_ref = toc.get('chapter')
        if isinstance(chapter_ref, dict):
            chapter_meta = state.get(str(chapter_ref.get('__ref') or ''))
            if isinstance(chapter_meta, dict):
                chapter_title = str(chapter_meta.get('title') or chapter_meta.get('name') or '').strip()

        for episode_ref in toc.get('episodeUnions', []):
            episode_key = episode_ref.get('__ref') if isinstance(episode_ref, dict) else None
            episode = state.get(str(episode_key or ''))
            if not isinstance(episode, dict):
                continue
            episode_id = str(episode.get('id') or '').strip()
            episode_title = str(episode.get('title') or '').strip()
            if not episode_id or not episode_title:
                continue

            title = f'{chapter_title} - {episode_title}' if chapter_title else episode_title
            chapter_url = f'{origin}/works/{work_id}/episodes/{episode_id}'
            if chapter_url in seen:
                continue
            seen.add(chapter_url)
            items.append({'title': title[:180], 'url': chapter_url})

    return items


def _syosetu_chapters_from_soup(soup, base_url):
    items = []
    seen = set()
    current_heading = ''

    for node in soup.select('.p-eplist > *'):
        classes = node.get('class') or []
        if 'p-eplist__chapter-title' in classes:
            current_heading = node.get_text(' ', strip=True)
            continue
        if 'p-eplist__sublist' not in classes:
            continue
        anchor = node.select_one('a[href]')
        if anchor is None:
            continue
        href = str(anchor.get('href') or '').strip()
        title = anchor.get_text(' ', strip=True)
        if not href or not title:
            continue
        absolute_url = urljoin(base_url, href).split('#', 1)[0]
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        if current_heading and current_heading not in title:
            title = f'{current_heading} - {title}'
        items.append({'title': title[:180], 'url': absolute_url})

    if items:
        return items

    current_heading = ''
    for node in soup.select('.index_box > *, .novel_sublist2, .novel_sublist, .chapter_title'):
        classes = node.get('class') or []
        class_text = ' '.join(classes)
        if 'chapter_title' in class_text:
            current_heading = node.get_text(' ', strip=True)
            continue

        anchor = node.select_one('a[href]')
        if anchor is None:
            continue
        href = str(anchor.get('href') or '').strip()
        title = anchor.get_text(' ', strip=True)
        if not href or not title:
            continue
        absolute_url = urljoin(base_url, href).split('#', 1)[0]
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        if current_heading and current_heading not in title:
            title = f'{current_heading} - {title}'
        items.append({'title': title[:180], 'url': absolute_url})

    return items


def _hameln_chapters_from_soup(soup, base_url):
    items = []
    seen = set()

    for anchor in soup.select("table tr a[href$='.html']"):
        href = str(anchor.get('href') or '').strip()
        title = anchor.get_text(' ', strip=True)
        if not href or not title:
            continue
        absolute_url = urljoin(base_url, href).split('#', 1)[0]
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        items.append({'title': title[:180], 'url': absolute_url})

    return items


def _hameln_chapter_text(soup):
    body = soup.select_one('#honbun')
    if body is None:
        return ''
    parts = [body.get_text('\n', strip=True)]
    afterword = soup.select_one('#atogaki')
    if afterword is not None:
        afterword_text = afterword.get_text('\n', strip=True)
        if afterword_text:
            parts.append(f'后记\n{afterword_text}')
    return '\n\n'.join(part.strip() for part in parts if part.strip()).strip()


def _pixiv_api_headers(referer=None):
    return {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ja,en;q=0.9',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': referer or 'https://www.pixiv.net/',
    }


def _pixiv_content_to_text(content):
    value = str(content or '').replace('\r\n', '\n').replace('\r', '\n')
    value = value.replace('[newpage]', '\n\n')
    value = re.sub(r'\[\[rb:([^>]+)\s*>\s*([^\]]+)\]\]', r'\1(\2)', value)
    value = re.sub(r'\[\[jumpuri:([^>]+)\s*>\s*([^\]]+)\]\]', r'\1(\2)', value)
    value = re.sub(r'\[jump:(\d+)\]', '', value)
    value = re.sub(r'\[chapter:[^\]]+\]', '', value)
    value = re.sub(r'\n{3,}', '\n\n', value)
    return value.strip()


def _fetch_pixiv_json(api_url, referer=None):
    response = _request_url(
        api_url,
        referer=referer or 'https://www.pixiv.net/',
        extra_headers=_pixiv_api_headers(referer=referer),
    )
    try:
        payload = response.json()
    except Exception as exc:
        raise CrawlerRetryableError('Pixiv API 返回了非 JSON 数据') from exc

    if bool(payload.get('error')):
        raise CrawlerRetryableError(f'Pixiv API 返回错误: {payload.get("message") or "unknown"}')

    return payload.get('body')


def _extract_pixiv_series_chapters(series_id, source_url):
    body = _fetch_pixiv_json(
        f'https://www.pixiv.net/ajax/novel/series/{series_id}',
        referer=source_url,
    )
    titles_body = _fetch_pixiv_json(
        f'https://www.pixiv.net/ajax/novel/series/{series_id}/content_titles',
        referer=source_url,
    )
    if not isinstance(body, dict) or not isinstance(titles_body, list):
        return []

    items = []
    seen = set()
    for index, item in enumerate(titles_body, start=1):
        if not isinstance(item, dict):
            continue
        novel_id = str(item.get('id') or '').strip()
        if not novel_id:
            continue
        available = item.get('available')
        if available is False:
            continue
        title = str(item.get('title') or f'Chapter {index}').strip()
        chapter_url = f'https://www.pixiv.net/novel/show.php?id={novel_id}'
        if chapter_url in seen:
            continue
        seen.add(chapter_url)
        items.append({'title': title[:180], 'url': chapter_url})

    return items


def _alphapolis_cover_data_from_html(raw_html):
    BeautifulSoup = _import_bs4()
    soup = BeautifulSoup(raw_html or '', 'html.parser')
    node = soup.select_one('#app-cover-data')
    if node is None:
        return {}
    try:
        payload = json.loads(node.get_text(strip=True))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _alphapolis_chapters_from_cover_data(data, base_url):
    items = []
    seen = set()

    for group in data.get('chapterEpisodes') or []:
        if not isinstance(group, dict):
            continue
        group_title = str(group.get('title') or '').strip()
        episodes = group.get('episodes') or []
        if not isinstance(episodes, list):
            continue

        for episode in episodes:
            if not isinstance(episode, dict):
                continue
            if episode.get('isPublic') is False:
                continue

            episode_title = str(episode.get('mainTitle') or episode.get('title') or '').strip()
            href = str(episode.get('url') or '').strip()
            if not episode_title or not href:
                continue

            title = episode_title if not group_title or group_title in episode_title else f'{group_title} / {episode_title}'
            absolute_url = urljoin(base_url, href).split('#', 1)[0]
            if absolute_url in seen:
                continue
            seen.add(absolute_url)
            items.append({'title': title[:180], 'url': absolute_url})

    return items


def _extract_site_specific_chapter_links(raw_html, base_url):
    BeautifulSoup = _import_bs4()
    soup = BeautifulSoup(raw_html or '', 'html.parser')

    if _is_kakuyomu_url(base_url):
        state = _kakuyomu_state_from_html(raw_html)
        if state:
            links = _kakuyomu_chapters_from_state(state, base_url)
            if links:
                return links
        work_id = _kakuyomu_work_id_from_url(base_url)
        links = []
        seen = set()
        for anchor in soup.select("a[href*='/episodes/']"):
            href = str(anchor.get('href') or '').strip()
            if not href:
                continue
            chapter_url = urljoin(base_url, href).split('#', 1)[0]
            path = urlparse(chapter_url).path
            if work_id and f'/works/{work_id}/episodes/' not in path:
                continue
            title = re.sub(r'\s+\d{4}年\d{1,2}月\d{1,2}日\s*公開.*$', '', anchor.get_text(' ', strip=True)).strip()
            if not title or title in {'1話目から読む'}:
                continue
            if chapter_url in seen:
                continue
            seen.add(chapter_url)
            links.append({'title': title[:180], 'url': chapter_url})
        if links:
            return links

    if _is_syosetu_url(base_url) or _is_novel18_url(base_url):
        links = _syosetu_chapters_from_soup(soup, base_url)
        if links:
            return links

    if _is_hameln_url(base_url):
        links = _hameln_chapters_from_soup(soup, base_url)
        if links:
            return links

    if _is_linovelib_url(base_url):
        links = []
        if _is_probable_linovelib_page(soup):
            links = _extract_linovelib_chapters(soup, base_url)
            if links:
                return links

        catalog_candidates = []
        seen_catalog = set()
        for anchor in soup.select("a[href*='/catalog'], a[href*='/novel/'][href*='catalog']"):
            href = str(anchor.get('href') or '').strip()
            if not href:
                continue
            catalog_url = urljoin(base_url, href).split('#', 1)[0]
            if catalog_url in seen_catalog:
                continue
            seen_catalog.add(catalog_url)
            catalog_candidates.append(catalog_url)

        if not catalog_candidates:
            book_match = re.search(r'/novel/(\d+)', urlparse(base_url).path)
            if book_match:
                catalog_candidates.append(urljoin(base_url, f'/novel/{book_match.group(1)}/catalog'))

        BeautifulSoup = _import_bs4()
        for catalog_url in catalog_candidates[:3]:
            try:
                catalog_response = _request_url(catalog_url, referer=base_url)
            except Exception:
                continue
            catalog_html = catalog_response.text
            catalog_base = catalog_response.url or catalog_url
            catalog_soup = BeautifulSoup(catalog_html or '', 'html.parser')
            links = _extract_linovelib_chapters(catalog_soup, catalog_base)
            if links:
                return links

        # 避免回落到通用规则时误抓导航链接
        return []

    if _is_pixiv_url(base_url):
        series_id = _pixiv_series_id_from_url(base_url)
        if series_id:
            links = _extract_pixiv_series_chapters(series_id, base_url)
            if links:
                return links

    if _is_alphapolis_url(base_url):
        cover_data = _alphapolis_cover_data_from_html(raw_html)
        cover_base_url = base_url
        if not cover_data and _looks_like_alphapolis_block_page(raw_html):
            try:
                preview_html, resolved_url = _fetch_alphapolis_preview_html(base_url)
                cover_data = _alphapolis_cover_data_from_html(preview_html)
                if resolved_url:
                    cover_base_url = resolved_url
            except Exception:
                cover_data = {}
        if cover_data:
            links = _alphapolis_chapters_from_cover_data(cover_data, cover_base_url)
            if links:
                return links

    return []


def _looks_like_alphapolis_block_page(raw_html):
    sample = str(raw_html or '').lower()
    return any(
        marker in sample
        for marker in (
            'window.gokuprops',
            'awswaf',
            'g-recaptcha',
            '403 error',
            'request could not be satisfied',
            'javascript is disabled',
            'captcha',
        )
    )


def _find_edge_executable():
    for candidate in EDGE_BROWSER_PATHS:
        if candidate.exists():
            return candidate
    return None


def _reserve_local_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def _list_edge_targets(port):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1) as response:
        payload = response.read().decode('utf-8', errors='replace')
    result = json.loads(payload)
    return result if isinstance(result, list) else []


async def _wait_for_edge_page_target(port, timeout_seconds):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            targets = await asyncio.to_thread(_list_edge_targets, port)
        except Exception:
            await asyncio.sleep(0.25)
            continue
        for target in targets:
            if target.get('type') == 'page' and target.get('webSocketDebuggerUrl'):
                return str(target['webSocketDebuggerUrl'])
        await asyncio.sleep(0.25)
    raise CrawlerRetryableError('未能连接到 Edge DevTools 页面目标')


async def _cdp_send_command(
    websocket,
    method,
    params=None,
    timeout_seconds=20.0,
    _state={'id': 0},
):
    _state['id'] += 1
    command_id = _state['id']
    await websocket.send(json.dumps({'id': command_id, 'method': method, 'params': params or {}}))

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        raw = await asyncio.wait_for(websocket.recv(), timeout=max(0.1, deadline - time.monotonic()))
        payload = json.loads(raw)
        if payload.get('id') == command_id:
            if 'error' in payload:
                error_payload = payload.get('error')
                message = error_payload.get('message') if isinstance(error_payload, dict) else error_payload
                raise CrawlerRetryableError(f'Edge DevTools 调用失败: {method} -> {message}')
            return payload
    raise CrawlerRetryableError(f'等待 Edge DevTools 返回超时: {method}')


async def _cdp_evaluate(websocket, expression, await_promise=False):
    response = await _cdp_send_command(
        websocket,
        'Runtime.evaluate',
        {
            'expression': expression,
            'returnByValue': True,
            'awaitPromise': await_promise,
        },
    )
    result = response.get('result', {}).get('result', {})
    if 'value' in result:
        return result['value']
    if result.get('type') == 'undefined':
        return None
    return result.get('description')


async def _fetch_with_edge_cdp_async(
    url,
    ready_expression,
    headless=False,
    timeout_seconds=EDGE_CDP_PAGE_TIMEOUT_SECONDS,
    blocked_message='',
):
    edge_path = _find_edge_executable()
    if edge_path is None:
        raise CrawlerPermanentError('未找到 Microsoft Edge，无法启用浏览器会话兜底抓取')
    if websockets is None:
        raise CrawlerPermanentError('缺少 websockets 依赖，无法启用浏览器会话兜底抓取')

    port = _reserve_local_port()
    user_data_dir = Path(tempfile.mkdtemp(prefix='novel-edge-cdp-'))
    launch_args = [
        str(edge_path),
        f'--remote-debugging-port={port}',
        '--disable-gpu',
        '--disable-extensions',
        '--no-first-run',
        '--no-default-browser-check',
        f'--user-data-dir={user_data_dir}',
        'about:blank',
    ]
    if headless:
        launch_args.insert(2, '--headless=new')
    else:
        launch_args.insert(2, '--start-minimized')

    process = subprocess.Popen(launch_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = await _wait_for_edge_page_target(port, EDGE_CDP_BOOT_TIMEOUT_SECONDS)
        async with websockets.connect(ws_url, max_size=100_000_000) as websocket:
            await _cdp_send_command(websocket, 'Page.enable')
            await _cdp_send_command(websocket, 'Runtime.enable')
            await _cdp_send_command(websocket, 'Network.enable')
            await _cdp_send_command(websocket, 'Page.navigate', {'url': url})

            deadline = time.monotonic() + timeout_seconds
            last_title = ''
            last_url = url
            while time.monotonic() < deadline:
                ready = bool(await _cdp_evaluate(websocket, ready_expression))
                last_title = str(await _cdp_evaluate(websocket, "document.title || ''") or '')
                last_url = str(await _cdp_evaluate(websocket, "location.href || ''") or url)
                if ready:
                    html_value = str(await _cdp_evaluate(websocket, "document.documentElement.outerHTML || ''") or '')
                    return html_value, (last_url or url)
                await asyncio.sleep(EDGE_CDP_POLL_INTERVAL_SECONDS)

            html_value = str(await _cdp_evaluate(websocket, "document.documentElement.outerHTML || ''") or '')
            if 'request could not be satisfied' in last_title.lower() or '403 error' in html_value.lower():
                raise CrawlerRetryableError(blocked_message or '浏览器会话仍被目标站点拦截')
            raise CrawlerRetryableError(f'浏览器会话加载超时: {url}')
    finally:
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.wait(timeout=10)
        except Exception:
            pass
        shutil.rmtree(user_data_dir, ignore_errors=True)


def _fetch_with_edge_cdp(url, ready_expression, headless=False, timeout_seconds=EDGE_CDP_PAGE_TIMEOUT_SECONDS, blocked_message=''):
    return asyncio.run(
        _fetch_with_edge_cdp_async(
            url,
            ready_expression=ready_expression,
            headless=headless,
            timeout_seconds=timeout_seconds,
            blocked_message=blocked_message,
        )
    )


def _fetch_alphapolis_preview_html(source_url):
    return _fetch_with_edge_cdp(
        source_url,
        headless=True,
        ready_expression="""
            (() => {
                const html = document.documentElement.outerHTML || '';
                return Boolean(document.querySelector('#app-cover-data')) && !html.includes('window.gokuProps');
            })()
        """,
        blocked_message='Alphapolis 浏览器会话仍被 AWS WAF 拦截，暂时无法抓取目录。',
    )


def _fetch_alphapolis_chapter_html(chapter_url):
    return _fetch_with_edge_cdp(
        chapter_url,
        headless=False,
        ready_expression="""
            (() => {
                const html = document.documentElement.outerHTML || '';
                if (html.includes('window.gokuProps')) return false;
                const body = document.querySelector('#novelBody');
                if (!body) return false;
                const inner = body.innerHTML || '';
                const text = body.innerText || '';
                const imageCount = body.querySelectorAll('img').length;
                const blocked = inner.includes('g-recaptcha') || inner.includes('LoadingEpisode');
                return !blocked && (text.trim().length >= 20 || imageCount > 0);
            })()
        """,
        blocked_message='Alphapolis 章节正文仍触发验证码或防护，暂时无法自动抓取。',
    )


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


def _extract_main_text(raw_html, rule=None):
    if rule:
        selector_text = rule.get('content_selector')
        remove_selectors = '\n'.join(filter(None, [
            rule.get('remove_selectors', ''),
            rule.get('related_thread_selector', ''),
        ]))
        rule_text = _extract_rule_selected_text(
            raw_html,
            selector_text,
            remove_selectors=remove_selectors,
        )
        if len(rule_text) >= 20:
            return rule_text
        if str(selector_text or '').strip():
            return ''

    block = _extract_preferred_html_block(raw_html)
    text = _html_to_text(block)
    if len(text) >= 120:
        return text
    return _html_to_text(raw_html)


def _extract_linovelib_page_text(soup):
    content_node = soup.select_one('#acontent, #TextContent, .read-content')
    if content_node is None:
        return ''

    for selector in ('.cgo', 'script', 'style', '#footlink', '.mlfy_page'):
        for node in content_node.select(selector):
            node.decompose()

    text = content_node.get_text('\n', strip=True)
    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r'\s+', ' ', raw_line).strip()
        if not line:
            continue
        if any(marker in line for marker in LINOVELIB_NOISE_LINE_MARKERS):
            continue
        lines.append(line)

    return '\n'.join(lines).strip()


def _extract_linovelib_next_page(raw_html, current_url):
    BeautifulSoup = _import_bs4()
    soup = BeautifulSoup(raw_html or '', 'html.parser')
    for anchor in soup.select('.mlfy_page a[href], #footlink a[href]'):
        label = re.sub(r'\s+', ' ', anchor.get_text(' ', strip=True)).strip().lower()
        href = str(anchor.get('href') or '').strip()
        if not href:
            continue
        if label in LINOVELIB_NEXT_PAGE_LABELS:
            return urljoin(current_url, href).split('#', 1)[0]

    match = re.search(r"url_next\s*[:=]\s*'([^']+)'", raw_html or '')
    if not match:
        match = re.search(r'url_next\s*[:=]\s*"([^"]+)"', raw_html or '')
    if not match:
        return None
    candidate = match.group(1).strip()
    if not candidate:
        return None
    return urljoin(current_url, candidate).split('#', 1)[0]


def _same_linovelib_chapter(source_url, candidate_url):
    source_match = LINOVELIB_CHAPTER_PATH_PATTERN.match(urlparse(source_url or '').path)
    candidate_match = LINOVELIB_CHAPTER_PATH_PATTERN.match(urlparse(candidate_url or '').path)
    if not source_match or not candidate_match:
        return False
    return (
        source_match.group('book_id') == candidate_match.group('book_id')
        and source_match.group('chapter_id') == candidate_match.group('chapter_id')
    )


def _fetch_linovelib_chapter_text(chapter_url):
    page_url = chapter_url
    parts = []
    visited = set()

    while page_url and page_url not in visited:
        visited.add(page_url)
        response = _request_url(page_url, referer=chapter_url)
        BeautifulSoup = _import_bs4()
        soup = BeautifulSoup(response.text or '', 'html.parser')
        text = _extract_linovelib_page_text(soup)
        if text:
            parts.append(text)

        next_page = _extract_linovelib_next_page(response.text, response.url or page_url)
        if not next_page or not _same_linovelib_chapter(chapter_url, next_page):
            break
        page_url = next_page

    return '\n\n'.join(part for part in parts if part.strip()).strip()


def _extract_syosetu_chapter_text(raw_html):
    BeautifulSoup = _import_bs4()
    soup = BeautifulSoup(raw_html or '', 'html.parser')
    blocks = soup.select('.p-novel__text')
    if not blocks:
        body = soup.select_one('#novel_honbun')
        if body is not None:
            blocks = [body]
    text_parts = [block.get_text('\n', strip=True) for block in blocks if block is not None]
    merged = '\n\n'.join(part.strip() for part in text_parts if str(part).strip())
    return merged.strip()


def _extract_kakuyomu_chapter_text(raw_html):
    BeautifulSoup = _import_bs4()
    soup = BeautifulSoup(raw_html or '', 'html.parser')
    body = soup.select_one('.widget-episodeBody, .js-episode-body')
    if body is None:
        return ''

    for selector in ('script', 'style', '.widget-toc', '.widget-episodeTitle'):
        for node in body.select(selector):
            node.decompose()

    return body.get_text('\n', strip=True).strip()


def _extract_hameln_chapter_text(raw_html):
    BeautifulSoup = _import_bs4()
    soup = BeautifulSoup(raw_html or '', 'html.parser')
    return _hameln_chapter_text(soup)


def _extract_alphapolis_chapter_text(raw_html):
    BeautifulSoup = _import_bs4()
    soup = BeautifulSoup(raw_html or '', 'html.parser')
    body = soup.select_one('#novelBody')
    if body is None:
        return ''

    for selector in ('script', 'style', '.dots-indicator', '.g-recaptcha', '#LoadingEpisode'):
        for node in body.select(selector):
            node.decompose()

    text = body.get_text('\n', strip=True).strip()
    return text


def _fetch_pixiv_chapter_text(chapter_url):
    novel_id = _pixiv_novel_id_from_url(chapter_url)
    if not novel_id:
        return '', ''

    body = _fetch_pixiv_json(
        f'https://www.pixiv.net/ajax/novel/{novel_id}',
        referer=chapter_url,
    )
    if not isinstance(body, dict):
        return '', ''

    title = str(body.get('title') or '').strip()
    text = _pixiv_content_to_text(body.get('content') or '')
    return title, text


def _extract_site_specific_chapter_content(chapter_url, raw_html):
    if _is_linovelib_url(chapter_url):
        return '', _fetch_linovelib_chapter_text(chapter_url)
    if _is_kakuyomu_url(chapter_url):
        return '', _extract_kakuyomu_chapter_text(raw_html)
    if _is_syosetu_url(chapter_url) or _is_novel18_url(chapter_url):
        return '', _extract_syosetu_chapter_text(raw_html)
    if _is_hameln_url(chapter_url):
        return '', _extract_hameln_chapter_text(raw_html)
    if _is_pixiv_url(chapter_url):
        return _fetch_pixiv_chapter_text(chapter_url)
    if _is_alphapolis_url(chapter_url):
        chapter_text = _extract_alphapolis_chapter_text(raw_html)
        if chapter_text:
            return '', chapter_text
        if _looks_like_alphapolis_block_page(raw_html):
            try:
                chapter_html, _ = _fetch_alphapolis_chapter_html(chapter_url)
                return '', _extract_alphapolis_chapter_text(chapter_html)
            except Exception:
                return '', ''
        return '', ''
    return '', ''


def _extract_page_title(raw_html, rule=None, for_chapter=False):
    if rule:
        selector_text = rule.get('chapter_title_selector') if for_chapter else rule.get('title_selector')
        if not selector_text and for_chapter:
            selector_text = rule.get('title_selector')
        title = _extract_rule_selected_text(raw_html, selector_text)
        title = re.sub(r'\s+', ' ', title).strip(' -_|')
        if title:
            return title

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


def _extract_chapter_links(raw_html, base_url, rule=None):
    if _is_alphapolis_url(base_url) and '/episode/' in (urlparse(base_url or '').path or ''):
        return []

    site_specific_links = _extract_site_specific_chapter_links(raw_html, base_url)
    if len(site_specific_links) >= 1:
        return site_specific_links

    if rule:
        rule_links = _extract_chapter_links_with_rule(raw_html, base_url, rule)
        if len(rule_links) >= 1:
            return rule_links

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


def _crawl_task_content_legacy(task_id, task):
    response = _request_url(task['source_url'])
    content_type = (response.headers.get('Content-Type') or '').lower()
    active_rules = _fetch_crawler_site_rules(active_only=True)
    site_rule = _resolve_crawler_site_rule(
        task.get('source_url'),
        preferred_rule_id=task.get('site_rule_id'),
        rules=active_rules,
    )

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
    chapter_links = _extract_chapter_links(raw_html, task['source_url'], rule=site_rule)
    chapter_links = _expand_alicesw_chapter_links(raw_html, task['source_url'], rule=site_rule, links=chapter_links)
    title = task.get('title') or _extract_page_title(raw_html, rule=site_rule) or _guess_title_from_url(task['source_url'])

    if len(chapter_links) >= 2:
        total = min(len(chapter_links), 500)
        _update_crawler_task(task_id, total_chapters=total, crawled_chapters=0, progress=0)
        sections = []
        failed_chapters = 0
        allowed_failed_chapters = max(2, min(10, total // 5 or 1))

        for index, chapter in enumerate(chapter_links[:total], start=1):
            chapter_title = chapter.get('title') or f'第{index}章'

            try:
                chapter_response = _request_url(chapter['url'])
                extracted_chapter_title = _extract_page_title(chapter_response.text, rule=site_rule, for_chapter=True)
                if extracted_chapter_title and '加载中' not in extracted_chapter_title:
                    chapter_title = extracted_chapter_title
                chapter_text = _extract_main_text(chapter_response.text, rule=site_rule)
                if _is_alicesw_site_rule(site_rule, chapter.get('url') or task['source_url']):
                    api_title, api_text = _extract_alicesw_chapter_content(chapter_response.text, chapter['url'])
                    if api_title:
                        chapter_title = api_title
                    if api_text:
                        chapter_text = api_text
                    elif _looks_like_alicesw_placeholder_text(chapter_text):
                        chapter_text = ''
                if not chapter_text:
                    raise CrawlerRetryableError('未提取到章节正文')
                sections.append(f'{chapter_title}\n\n{chapter_text}')
            except Exception:
                failed_chapters += 1
                if failed_chapters > allowed_failed_chapters and not sections:
                    raise
            finally:
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

    related_thread_links = _extract_related_thread_links(raw_html, task['source_url'], rule=site_rule)
    if related_thread_links:
        related_candidates = [{'url': task['source_url'], 'title': title, 'raw_html': raw_html}] + related_thread_links
        related_candidates.sort(key=lambda item: (_extract_crawler_sequence_start(item.get('title')), item.get('url') or ''))
        total = min(len(related_candidates), CRAWLER_LISTING_BATCH_MAX)
        _update_crawler_task(task_id, total_chapters=total, crawled_chapters=0, progress=0)
        sections = []

        for index, item in enumerate(related_candidates[:total], start=1):
            try:
                current_html = item.get('raw_html')
                if not current_html:
                    current_html = _request_url(item['url']).text
                section_title = _extract_page_title(current_html, rule=site_rule, for_chapter=True) or item.get('title') or f'第{index}篇'
                section_text = _extract_main_text(current_html, rule=site_rule)
                if not section_text:
                    raise CrawlerRetryableError('未提取到关联帖子正文')
                sections.append(f'{section_title}\n\n{section_text}')
            finally:
                _update_crawler_task(
                    task_id,
                    total_chapters=total,
                    crawled_chapters=index,
                    progress=int(index * 100 / total)
                )

        if sections:
            return {
                'title': title,
                'author': task.get('author') or '',
                'content': '\n\n'.join(sections),
                'chapter_count': len(sections)
            }

    main_text = _extract_main_text(raw_html, rule=site_rule)
    if _is_alicesw_site_rule(site_rule, task['source_url']) and _looks_like_alicesw_placeholder_text(main_text):
        api_title, api_text = _extract_alicesw_chapter_content(raw_html, task['source_url'])
        if api_title and '\u52a0\u8f7d\u4e2d' not in api_title:
            title = api_title
        if api_text:
            main_text = api_text
        else:
            main_text = ''
    if len(main_text) < 80:
        raise RuntimeError('未能提取正文内容，请确认链接为小说详情页、目录页或正文页')

    _update_crawler_task(task_id, total_chapters=1, crawled_chapters=1, progress=100)
    return {
        'title': title,
        'author': task.get('author') or '',
        'content': main_text,
        'chapter_count': 1
    }


def _crawl_task_content(task_id, task):
    source_url = task['source_url']
    response = None
    raw_html = ''
    resolved_source_url = source_url
    content_type = ''

    try:
        response = _request_url(source_url, referer=source_url)
        resolved_source_url = response.url or source_url
        content_type = (response.headers.get('Content-Type') or '').lower()
        raw_html = response.text
    except CrawlerError:
        if not _is_alphapolis_url(source_url):
            raise
        raw_html, resolved_source_url = _fetch_alphapolis_preview_html(source_url)
        content_type = 'text/html'

    if _is_alphapolis_url(resolved_source_url) and _looks_like_alphapolis_block_page(raw_html):
        try:
            raw_html, resolved_source_url = _fetch_alphapolis_preview_html(resolved_source_url)
            content_type = 'text/html'
        except Exception:
            pass
    active_rules = _fetch_crawler_site_rules(active_only=True)
    site_rule = _resolve_crawler_site_rule(
        resolved_source_url,
        preferred_rule_id=task.get('site_rule_id'),
        rules=active_rules,
    )

    if 'text/plain' in content_type or resolved_source_url.lower().endswith('.txt'):
        if response is None:
            raise RuntimeError('未获取到纯文本响应内容')
        text_content = response.text.strip()
        if not text_content:
            raise RuntimeError('抓取结果为空，请检查链接是否可直接访问文本内容')
        return {
            'title': task.get('title') or _guess_title_from_url(resolved_source_url),
            'author': task.get('author') or '',
            'content': text_content,
            'chapter_count': 1
        }

    chapter_links = _extract_chapter_links(raw_html, resolved_source_url, rule=site_rule)
    chapter_links = _expand_alicesw_chapter_links(raw_html, resolved_source_url, rule=site_rule, links=chapter_links)
    title = task.get('title') or _extract_page_title(raw_html, rule=site_rule) or _guess_title_from_url(resolved_source_url)

    if len(chapter_links) >= 2:
        total = min(len(chapter_links), 500)
        _update_crawler_task(task_id, total_chapters=total, crawled_chapters=0, progress=0)
        sections = []
        failed_chapters = 0
        allowed_failed_chapters = max(2, min(10, total // 5 or 1))

        for index, chapter in enumerate(chapter_links[:total], start=1):
            chapter_url = str(chapter.get('url') or '').strip()
            chapter_title = chapter.get('title') or f'第{index}章'
            if not chapter_url:
                failed_chapters += 1
                continue

            try:
                try:
                    chapter_response = _request_url(chapter_url, referer=resolved_source_url)
                    chapter_html = chapter_response.text
                except CrawlerError:
                    if not _is_alphapolis_url(chapter_url):
                        raise
                    chapter_html, chapter_resolved_url = _fetch_alphapolis_chapter_html(chapter_url)
                    if chapter_resolved_url:
                        chapter_url = chapter_resolved_url
                if _is_alphapolis_url(chapter_url) and _looks_like_alphapolis_block_page(chapter_html):
                    try:
                        chapter_html, chapter_resolved_url = _fetch_alphapolis_chapter_html(chapter_url)
                        if chapter_resolved_url:
                            chapter_url = chapter_resolved_url
                    except Exception:
                        pass

                extracted_chapter_title = _extract_page_title(chapter_html, rule=site_rule, for_chapter=True)
                if extracted_chapter_title and '加载中' not in extracted_chapter_title:
                    chapter_title = extracted_chapter_title

                chapter_text = _extract_main_text(chapter_html, rule=site_rule)
                if _is_alphapolis_url(chapter_url) and _looks_like_alphapolis_block_page(chapter_html):
                    chapter_text = ''
                special_title, special_text = _extract_site_specific_chapter_content(chapter_url, chapter_html)
                if special_title:
                    chapter_title = special_title
                if special_text:
                    chapter_text = special_text

                if _is_alicesw_site_rule(site_rule, chapter_url):
                    api_title, api_text = _extract_alicesw_chapter_content(chapter_html, chapter_url)
                    if api_title:
                        chapter_title = api_title
                    if api_text:
                        chapter_text = api_text
                    elif _looks_like_alicesw_placeholder_text(chapter_text):
                        chapter_text = ''

                if not chapter_text:
                    raise CrawlerRetryableError('未提取到章节正文')
                sections.append(f'{chapter_title}\n\n{chapter_text}')
            except Exception:
                failed_chapters += 1
                if failed_chapters > allowed_failed_chapters and not sections:
                    raise
            finally:
                _update_crawler_task(
                    task_id,
                    total_chapters=total,
                    crawled_chapters=index,
                    progress=int(index * 100 / total)
                )

        if not sections:
            raise RuntimeError('未能从目录页抓取到有效章节内容，请更换目录页链接重试')

        return {
            'title': title,
            'author': task.get('author') or '',
            'content': '\n\n'.join(sections),
            'chapter_count': len(sections)
        }

    related_thread_links = _extract_related_thread_links(raw_html, resolved_source_url, rule=site_rule)
    if related_thread_links:
        related_candidates = [{'url': resolved_source_url, 'title': title, 'raw_html': raw_html}] + related_thread_links
        related_candidates.sort(key=lambda item: (_extract_crawler_sequence_start(item.get('title')), item.get('url') or ''))
        total = min(len(related_candidates), CRAWLER_LISTING_BATCH_MAX)
        _update_crawler_task(task_id, total_chapters=total, crawled_chapters=0, progress=0)
        sections = []

        for index, item in enumerate(related_candidates[:total], start=1):
            try:
                current_html = item.get('raw_html')
                if not current_html:
                    current_html = _request_url(item['url'], referer=resolved_source_url).text
                section_title = _extract_page_title(current_html, rule=site_rule, for_chapter=True) or item.get('title') or f'第{index}节'
                section_text = _extract_main_text(current_html, rule=site_rule)
                if not section_text:
                    raise CrawlerRetryableError('未提取到关联正文')
                sections.append(f'{section_title}\n\n{section_text}')
            finally:
                _update_crawler_task(
                    task_id,
                    total_chapters=total,
                    crawled_chapters=index,
                    progress=int(index * 100 / total)
                )

        if sections:
            return {
                'title': title,
                'author': task.get('author') or '',
                'content': '\n\n'.join(sections),
                'chapter_count': len(sections)
            }

    main_text = _extract_main_text(raw_html, rule=site_rule)
    if _is_alphapolis_url(resolved_source_url) and _looks_like_alphapolis_block_page(raw_html):
        main_text = ''
    special_title, special_text = _extract_site_specific_chapter_content(resolved_source_url, raw_html)
    if special_title and '加载中' not in special_title:
        title = special_title
    if special_text:
        main_text = special_text

    if _is_alicesw_site_rule(site_rule, resolved_source_url) and _looks_like_alicesw_placeholder_text(main_text):
        api_title, api_text = _extract_alicesw_chapter_content(raw_html, resolved_source_url)
        if api_title and '加载中' not in api_title:
            title = api_title
        if api_text:
            main_text = api_text
        else:
            main_text = ''

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

        max_attempts = _sanitize_crawler_max_attempts(task.get('max_attempts'))
        started_at = _now_timestamp()
        last_error_message = ''
        last_error_at = None

        for attempt in range(1, max_attempts + 1):
            update_fields = {
                'status': 'running',
                'progress': 0,
                'total_chapters': 0,
                'crawled_chapters': 0,
                'attempt_count': attempt,
                'max_attempts': max_attempts,
                'finished_at': None
            }
            if attempt == 1:
                update_fields.update({
                    'started_at': started_at,
                    'last_error': None,
                    'last_error_at': None
                })
            else:
                update_fields.update({
                    'last_error': f'上次抓取失败，正在进行第 {attempt} 次尝试',
                    'last_error_at': _now_timestamp()
                })

            _update_crawler_task(task_id, **update_fields)
            task = _fetch_crawler_task(task_id)
            if not task:
                return

            try:
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
                    attempt_count=attempt,
                    max_attempts=max_attempts,
                    novel_id=novel_id,
                    file_path=file_path,
                    last_error=None,
                    last_error_at=None,
                    finished_at=_now_timestamp()
                )
                return
            except CrawlerPermanentError as error:
                last_error_message = str(error)
                last_error_at = _now_timestamp()
                break
            except Exception as error:
                last_error_message = str(error)
                last_error_at = _now_timestamp()

                if attempt < max_attempts:
                    _update_crawler_task(
                        task_id,
                        attempt_count=attempt,
                        max_attempts=max_attempts,
                        last_error=f'{last_error_message}；正在准备第 {attempt + 1} 次尝试',
                        last_error_at=last_error_at
                    )
                    time.sleep(min(2 * attempt, 5))
                    continue

                break

        _update_crawler_task(
            task_id,
            status='failed',
            attempt_count=max(1, min(max_attempts, int(task.get('attempt_count') or 0) or max_attempts)),
            max_attempts=max_attempts,
            last_error=last_error_message or '抓取失败，请稍后重试',
            last_error_at=last_error_at or _now_timestamp(),
            finished_at=_now_timestamp()
        )
    except Exception as error:
        _update_crawler_task(
            task_id,
            status='failed',
            attempt_count=1,
            max_attempts=CRAWLER_DEFAULT_MAX_ATTEMPTS,
            last_error=str(error),
            last_error_at=_now_timestamp(),
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


def _insert_crawler_task_record(cursor, *, name, source_url, title='', author='', description='', category_id=None, site_rule_id=None, tag_ids=None, max_attempts=None):
    cursor.execute(
        '''
        INSERT INTO crawler_tasks (name, source_url, title, author, description, category_id, site_rule_id, tag_ids_json, status, progress, attempt_count, max_attempts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, 0, ?)
        ''',
        (
            (name or '').strip() or _guess_title_from_url(source_url),
            source_url,
            (title or '').strip(),
            (author or '').strip(),
            (description or '').strip(),
            category_id,
            site_rule_id,
            json.dumps(sorted(set(tag_ids or []))),
            _sanitize_crawler_max_attempts(max_attempts),
        )
    )
    return cursor.lastrowid


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


def get_crawler_rules():
    return jsonify({'success': True, 'data': _fetch_crawler_site_rules(active_only=False)})


def create_crawler_rule():
    data = request.get_json(silent=True) or {}

    try:
        payload = _build_crawler_site_rule_payload(data)
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''
            INSERT INTO crawler_site_rules (
                name, host_pattern, title_selector, content_selector, listing_link_selector, related_thread_selector,
                chapter_link_selector, chapter_title_selector,
                remove_selectors, notes, sort_order, is_active, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                payload['name'],
                payload['host_pattern'],
                payload['title_selector'],
                payload['content_selector'],
                payload['listing_link_selector'],
                payload['related_thread_selector'],
                payload['chapter_link_selector'],
                payload['chapter_title_selector'],
                payload['remove_selectors'],
                payload['notes'],
                payload['sort_order'],
                payload['is_active'],
                _now_timestamp(),
            )
        )
        rule_id = cursor.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return jsonify({'success': False, 'message': '该站点域名规则已存在'}), 400
    finally:
        conn.close()

    rule = _fetch_crawler_site_rule(rule_id)
    return jsonify({'success': True, 'data': rule})


def update_crawler_rule(rule_id):
    existing = _fetch_crawler_site_rule(rule_id)
    if not existing:
        return jsonify({'success': False, 'message': '站点规则不存在'}), 404

    data = request.get_json(silent=True) or {}
    try:
        payload = _build_crawler_site_rule_payload(data)
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''
            UPDATE crawler_site_rules
            SET name = ?, host_pattern = ?, title_selector = ?, content_selector = ?, listing_link_selector = ?, related_thread_selector = ?,
                chapter_link_selector = ?, chapter_title_selector = ?,
                remove_selectors = ?, notes = ?, sort_order = ?, is_active = ?, updated_at = ?
            WHERE id = ?
            ''',
            (
                payload['name'],
                payload['host_pattern'],
                payload['title_selector'],
                payload['content_selector'],
                payload['listing_link_selector'],
                payload['related_thread_selector'],
                payload['chapter_link_selector'],
                payload['chapter_title_selector'],
                payload['remove_selectors'],
                payload['notes'],
                payload['sort_order'],
                payload['is_active'],
                _now_timestamp(),
                rule_id,
            )
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return jsonify({'success': False, 'message': '该站点域名规则已存在'}), 400
    finally:
        conn.close()

    return jsonify({'success': True, 'data': _fetch_crawler_site_rule(rule_id)})


def delete_crawler_rule(rule_id):
    existing = _fetch_crawler_site_rule(rule_id)
    if not existing:
        return jsonify({'success': False, 'message': '站点规则不存在'}), 404

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE crawler_tasks SET site_rule_id = NULL WHERE site_rule_id = ?', (rule_id,))
    cursor.execute('DELETE FROM crawler_site_rules WHERE id = ?', (rule_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


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

    rules = _fetch_crawler_site_rules(active_only=True)
    return jsonify({'success': True, 'data': [_serialize_crawler_task(row, rules=rules) for row in rows]})


def create_crawler_task():
    data = request.get_json(silent=True) or {}
    source_url = (data.get('source_url') or '').strip()
    if not source_url:
        return jsonify({'success': False, 'message': '请提供抓取链接'}), 400
    if not source_url.startswith(('http://', 'https://')):
        return jsonify({'success': False, 'message': '链接必须以 http:// 或 https:// 开头'}), 400

    try:
        source_url = _validate_crawler_target_url(source_url)
    except CrawlerError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400

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
            return jsonify({'success': False, 'message': '分类无效'}), 400

    site_rule_id = data.get('site_rule_id')
    if site_rule_id in ('', None):
        site_rule_id = None
    else:
        try:
            site_rule_id = int(site_rule_id)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': '站点规则无效'}), 400
        if not _fetch_crawler_site_rule(site_rule_id):
            return jsonify({'success': False, 'message': '站点规则不存在'}), 400

    batch_from_listing = bool(data.get('batch_from_listing'))
    listing_limit = _sanitize_crawler_listing_limit(data.get('listing_limit'))
    start_immediately = bool(data.get('start_immediately', True))
    active_rules = _fetch_crawler_site_rules(active_only=True)
    resolved_rule = _resolve_crawler_site_rule(source_url, preferred_rule_id=site_rule_id, rules=active_rules)

    name = (data.get('name') or data.get('title') or _guess_title_from_url(source_url)).strip()
    max_attempts = _sanitize_crawler_max_attempts(data.get('max_attempts'))

    conn = get_db()
    cursor = conn.cursor()
    try:
        if batch_from_listing:
            if not resolved_rule or not str(resolved_rule.get('listing_link_selector') or '').strip():
                return jsonify({'success': False, 'message': '当前站点规则不支持从列表批量创建任务'}), 400

            response = _request_url(source_url)
            thread_links = _extract_listing_thread_links(response.text, source_url, resolved_rule)
            if not thread_links:
                return jsonify({'success': False, 'message': '未能从列表页提取到可抓取链接'}), 400

            effective_rule_id = resolved_rule.get('id') if resolved_rule else site_rule_id
            title_prefix = (data.get('title') or '').strip()
            name_prefix = (data.get('name') or '').strip()
            default_author = (data.get('author') or '').strip()
            default_description = (data.get('description') or '').strip()
            created_task_ids = []
            skipped_count = 0

            for item in thread_links[:listing_limit]:
                detail_url = _validate_crawler_target_url(item['url'])
                cursor.execute('SELECT id FROM crawler_tasks WHERE source_url = ? ORDER BY id DESC LIMIT 1', (detail_url,))
                if cursor.fetchone():
                    skipped_count += 1
                    continue

                item_title = item.get('title') or _guess_title_from_url(detail_url)
                task_title = f'{title_prefix} - {item_title}' if title_prefix else item_title
                task_name = f'{name_prefix} - {item_title}' if name_prefix else item_title
                task_id = _insert_crawler_task_record(
                    cursor,
                    name=task_name,
                    source_url=detail_url,
                    title=task_title,
                    author=default_author,
                    description=default_description,
                    category_id=category_id,
                    site_rule_id=effective_rule_id,
                    tag_ids=tag_ids,
                    max_attempts=max_attempts,
                )
                created_task_ids.append(task_id)

            conn.commit()

            if start_immediately:
                for task_id in created_task_ids:
                    _start_crawler_thread(task_id)

            return jsonify({
                'success': True,
                'message': f'已创建 {len(created_task_ids)} 个任务，跳过 {skipped_count} 个重复任务',
                'data': {
                    'mode': 'batch_listing',
                    'found_count': len(thread_links),
                    'created_count': len(created_task_ids),
                    'skipped_count': skipped_count,
                    'tasks': [_fetch_crawler_task(task_id) for task_id in created_task_ids],
                }
            })

        task_id = _insert_crawler_task_record(
            cursor,
            name=name,
            source_url=source_url,
            title=(data.get('title') or '').strip(),
            author=(data.get('author') or '').strip(),
            description=(data.get('description') or '').strip(),
            category_id=category_id,
            site_rule_id=site_rule_id,
            tag_ids=tag_ids,
            max_attempts=max_attempts,
        )
        conn.commit()
    finally:
        conn.close()

    if start_immediately:
        _start_crawler_thread(task_id)

    return jsonify({'success': True, 'data': _fetch_crawler_task(task_id)})


def run_crawler_task(task_id):
    task = _fetch_crawler_task(task_id)
    if not task:
        return jsonify({'success': False, 'message': '爬虫任务不存在'}), 404

    if task['status'] == 'running':
        return jsonify({'success': False, 'message': '任务已在运行中'}), 400

    if not _start_crawler_thread(task_id):
        return jsonify({'success': False, 'message': '任务启动失败，请稍后重试'}), 400

    return jsonify({'success': True, 'message': '任务已启动'})


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



def register_crawler_routes(app, *, get_db):
    global _get_db
    _get_db = get_db

    app.add_url_rule('/api/crawler/stats', view_func=get_crawler_stats, methods=['GET'])
    app.add_url_rule('/api/crawler/rules', view_func=get_crawler_rules, methods=['GET'])
    app.add_url_rule('/api/crawler/rules', view_func=create_crawler_rule, methods=['POST'])
    app.add_url_rule('/api/crawler/rules/<int:rule_id>', view_func=update_crawler_rule, methods=['PUT'])
    app.add_url_rule('/api/crawler/rules/<int:rule_id>', view_func=delete_crawler_rule, methods=['DELETE'])
    app.add_url_rule('/api/crawler/tasks', view_func=get_crawler_tasks, methods=['GET'])
    app.add_url_rule('/api/crawler/tasks', view_func=create_crawler_task, methods=['POST'])
    app.add_url_rule('/api/crawler/tasks/<int:task_id>/run', view_func=run_crawler_task, methods=['POST'])
    app.add_url_rule('/api/crawler/tasks/<int:task_id>', view_func=delete_crawler_task, methods=['DELETE'])
