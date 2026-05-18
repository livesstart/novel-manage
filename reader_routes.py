"""Reader API routes for opening chapters and saving progress."""
import os

from flask import jsonify, request

from reader_utils import get_cached_reader_file


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


def register_reader_routes(app, *, get_db, resolve_novel_file_path, is_text_readable_file):
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
                    'chapters': [{
                        'title': '文件未找到',
                        'content': f'请在服务器上确认文件存在:\n{file_path}\n\n已检查路径:\n' + '\n'.join(checked_paths)
                    }]
                }
            }), 404

        if not is_text_readable_file(actual_path):
            return jsonify({
                'success': False,
                'message': '当前仅支持 TXT/EPUB 文件在线阅读，请使用下载功能打开原文件',
                'data': {'novel': novel, 'checked_paths': checked_paths}
            }), 400

        try:
            reader_file = get_cached_reader_file(actual_path)
            chapters = reader_file['chapters']
            reading_progress = _serialize_reading_progress(novel, len(chapters))
            initial_chapter = None
            if chapters:
                initial_index = reading_progress['chapter_index']
                chapter = chapters[initial_index]
                initial_chapter = {
                    'index': initial_index,
                    'title': chapter['title'],
                    'content': chapter['content'],
                    'total_chapters': len(chapters)
                }

            return jsonify({
                'success': True,
                'data': {
                    'novel': novel,
                    'chapters': [{'title': c['title'], 'line_num': c['line_num']} for c in chapters],
                    'initial_chapter': initial_chapter,
                    'reading_progress': reading_progress,
                    'total_chars': reader_file['total_chars'],
                    'encoding': reader_file['encoding']
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
            return jsonify({'success': False, 'message': '当前仅支持 TXT/EPUB 文件在线阅读'}), 400

        try:
            chapters = get_cached_reader_file(actual_path)['chapters']

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
                chapter_count = max(len(get_cached_reader_file(actual_path)['chapters']), 1)
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
