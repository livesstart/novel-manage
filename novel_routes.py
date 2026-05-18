"""Novel metadata and file API routes."""
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from flask import jsonify, request, send_file
from werkzeug.http import dump_options_header

from storage_utils import (
    _build_file_delete_error_message,
    _collect_novel_file_deletion_targets,
    _delete_novel_files,
    is_supported_novel_file,
    is_text_readable_file,
    resolve_novel_file_path,
    store_uploaded_file,
)


def register_novel_routes(app, *, get_db):
    @app.route('/api/novels', methods=['GET'])
    def get_novels():
        """获取小说列表，支持搜索和筛选"""
        conn = get_db()
        cursor = conn.cursor()

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

        if tag_ids:
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

        cursor.execute('''
            SELECT t.id, t.name, t.color
            FROM tags t
            JOIN novel_tags nt ON t.id = nt.tag_id
            WHERE nt.novel_id = ?
        ''', (novel_id,))
        novel['tags'] = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return jsonify({'success': True, 'data': novel})

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

        actual_path, _ = resolve_novel_file_path(file_path)
        if not actual_path:
            return jsonify({
                'success': False,
                'message': f'文件不存在: {file_path}'
            }), 404

        try:
            filename = os.path.basename(actual_path)
            encoded_filename = quote(filename, safe='')
            latin1_filename = filename.encode('latin-1', 'replace').decode('latin-1').replace('?', '_')
            if not latin1_filename:
                latin1_filename = 'novel.txt'

            disposition = dump_options_header(
                'attachment',
                {'filename': latin1_filename, 'filename*': f"UTF-8''{encoded_filename}"}
            )

            response = send_file(
                actual_path,
                as_attachment=False,
                mimetype='application/octet-stream'
            )
            response.headers.set('Content-Disposition', disposition)

            return response
        except Exception as e:
            return jsonify({'success': False, 'message': f'下载失败: {str(e)}'}), 500

    @app.route('/api/fix-paths', methods=['POST'])
    def fix_all_paths():
        """批量修复小说文件路径"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id, file_path FROM novels")
        rows = cursor.fetchall()

        fixed_count = 0
        errors = []

        for row in rows:
            novel_id = row['id']
            old_path = row['file_path']

            if old_path and len(old_path) > 3:
                first_chars = old_path[:3]

                if '小说' in first_chars or first_chars.startswith('С'):
                    new_path = old_path
                    if '/' in new_path:
                        new_path = 'D:/' + new_path.replace('小说/', '小说/')
                    elif '\\' in new_path:
                        new_path = 'D:/' + new_path.replace('小说\\', '小说/')

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

        if not file_path:
            return jsonify({
                'success': True,
                'data': {
                    'file_path_in_db': file_path,
                    'current_working_dir': os.getcwd(),
                    'script_dir': os.path.dirname(os.path.abspath(__file__)),
                    'checked_paths': [],
                    'file_found': False,
                    'actual_path': None,
                    'file_size': None,
                    'file_modified_at': None,
                    'file_extension': '',
                    'is_text_readable': False
                }
            })

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

        file_size = None
        file_modified_at = None
        file_extension = ''
        is_text_readable = False

        if actual_path:
            file_size = os.path.getsize(actual_path)
            file_modified_at = datetime.fromtimestamp(os.path.getmtime(actual_path)).isoformat(timespec='seconds')
            file_extension = Path(actual_path).suffix.lower()
            is_text_readable = is_text_readable_file(actual_path)

        return jsonify({
            'success': True,
            'data': {
                'file_path_in_db': file_path,
                'current_working_dir': os.getcwd(),
                'script_dir': os.path.dirname(os.path.abspath(__file__)),
                'checked_paths': results,
                'file_found': actual_path is not None,
                'actual_path': actual_path,
                'file_size': file_size,
                'file_modified_at': file_modified_at,
                'file_extension': file_extension,
                'is_text_readable': is_text_readable
            }
        })
