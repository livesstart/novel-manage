"""Full-text search schema and routes."""
import os
import re
import sqlite3

from flask import jsonify, request


def ensure_full_text_search_schema(cursor):
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS novel_search_index
        USING fts5(
            novel_id UNINDEXED,
            chapter_index UNINDEXED,
            title,
            author,
            chapter_title,
            content,
            file_path UNINDEXED,
            file_mtime UNINDEXED,
            tokenize='trigram'
        )
    ''')


def register_search_routes(
    app,
    *,
    get_db,
    resolve_novel_file_path,
    is_text_readable_file,
    detect_encoding,
    parse_chapters,
    normalize_novel_ids,
):
    def get_file_mtime(file_path):
        try:
            return str(os.path.getmtime(file_path))
        except OSError:
            return ''

    def read_text_file(file_path):
        encoding = detect_encoding(file_path)
        with open(file_path, 'r', encoding=encoding, errors='ignore') as handle:
            return handle.read()

    def clear_full_text_index(cursor, novel_ids):
        normalized_ids = normalize_novel_ids(novel_ids)
        if not normalized_ids:
            return

        placeholders = ','.join(['?' for _ in normalized_ids])
        cursor.execute(
            f'DELETE FROM novel_search_index WHERE novel_id IN ({placeholders})',
            normalized_ids
        )

    def index_novel_chapters(cursor, novel, actual_path, file_mtime):
        content = read_text_file(actual_path)
        chapters = parse_chapters(content)
        title = novel.get('title') or ''
        author = novel.get('author') or ''
        file_path = novel.get('file_path') or actual_path

        rows = []
        for index, chapter in enumerate(chapters):
            rows.append((
                novel['id'],
                index,
                title,
                author,
                chapter.get('title') or f'Chapter {index + 1}',
                chapter.get('content') or '',
                file_path,
                file_mtime
            ))

        if rows:
            cursor.executemany('''
                INSERT INTO novel_search_index (
                    novel_id, chapter_index, title, author, chapter_title,
                    content, file_path, file_mtime
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', rows)

    def is_full_text_index_current(cursor, novel, file_mtime):
        cursor.execute('''
            SELECT COUNT(*) AS indexed_count,
                   MAX(file_mtime) AS file_mtime,
                   MAX(title) AS title,
                   MAX(author) AS author
            FROM novel_search_index
            WHERE novel_id = ?
        ''', (novel['id'],))
        index_state = cursor.fetchone()

        if not index_state or index_state['indexed_count'] == 0:
            return False

        return (
            str(index_state['file_mtime'] or '') == str(file_mtime) and
            (index_state['title'] or '') == (novel.get('title') or '') and
            (index_state['author'] or '') == (novel.get('author') or '')
        )

    def refresh_full_text_search_index(cursor):
        cursor.execute('SELECT id, title, author, file_path FROM novels')
        novels = [dict(row) for row in cursor.fetchall()]
        searchable_ids = []

        for novel in novels:
            file_path = novel.get('file_path')
            actual_path, _ = resolve_novel_file_path(file_path)
            if not actual_path or not is_text_readable_file(actual_path):
                clear_full_text_index(cursor, [novel['id']])
                continue

            searchable_ids.append(novel['id'])
            file_mtime = get_file_mtime(actual_path)
            if is_full_text_index_current(cursor, novel, file_mtime):
                continue

            clear_full_text_index(cursor, [novel['id']])
            try:
                index_novel_chapters(cursor, novel, actual_path, file_mtime)
            except Exception as exc:
                app.logger.warning('Skip full-text indexing novel %s: %s', novel['id'], exc)

        if searchable_ids:
            placeholders = ','.join(['?' for _ in searchable_ids])
            cursor.execute(
                f'DELETE FROM novel_search_index WHERE novel_id NOT IN ({placeholders})',
                searchable_ids
            )
        else:
            cursor.execute('DELETE FROM novel_search_index')

    def format_fts_query(query):
        normalized = re.sub(r'\s+', ' ', (query or '').strip())
        return '"' + normalized.replace('"', '""') + '"'

    def escape_like_query(query):
        return (query or '').replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

    def build_full_text_snippet(chapter_title, content, query, radius=60):
        search_text = re.sub(r'\s+', ' ', f'{chapter_title or ""} {content or ""}').strip()
        if not search_text:
            return ''

        normalized_query = (query or '').strip()
        match_index = search_text.lower().find(normalized_query.lower())
        if match_index < 0:
            return search_text[:radius * 2] + ('...' if len(search_text) > radius * 2 else '')

        start = max(match_index - radius, 0)
        end = min(match_index + len(normalized_query) + radius, len(search_text))
        prefix = '...' if start > 0 else ''
        suffix = '...' if end < len(search_text) else ''
        return f'{prefix}{search_text[start:end]}{suffix}'

    def query_full_text_index(cursor, query, limit):
        try:
            cursor.execute('''
                SELECT novel_id, chapter_index, title, author, chapter_title, content, file_path
                FROM novel_search_index
                WHERE novel_search_index MATCH ?
                ORDER BY bm25(novel_search_index)
                LIMIT ?
            ''', (format_fts_query(query), limit))
            return cursor.fetchall()
        except sqlite3.OperationalError:
            like_query = f'%{escape_like_query(query)}%'
            cursor.execute('''
                SELECT novel_id, chapter_index, title, author, chapter_title, content, file_path
                FROM novel_search_index
                WHERE title LIKE ? ESCAPE '\\'
                   OR author LIKE ? ESCAPE '\\'
                   OR chapter_title LIKE ? ESCAPE '\\'
                   OR content LIKE ? ESCAPE '\\'
                LIMIT ?
            ''', (like_query, like_query, like_query, like_query, limit))
            return cursor.fetchall()

    @app.route('/api/search/fulltext', methods=['GET'])
    def search_full_text():
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'success': False, 'message': '请输入全文搜索关键词'}), 400

        try:
            limit = int(request.args.get('limit', 50))
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 100))

        conn = get_db()
        cursor = conn.cursor()

        try:
            refresh_full_text_search_index(cursor)
            conn.commit()
            rows = query_full_text_index(cursor, query, limit)
            results = []
            for row in rows:
                result = dict(row)
                result['snippet'] = build_full_text_snippet(
                    result.get('chapter_title'),
                    result.pop('content', ''),
                    query
                )
                results.append(result)
        except sqlite3.DatabaseError as exc:
            conn.rollback()
            conn.close()
            return jsonify({'success': False, 'message': f'全文搜索失败: {exc}'}), 500

        conn.close()
        return jsonify({
            'success': True,
            'data': {
                'query': query,
                'total': len(results),
                'results': results
            }
        })
