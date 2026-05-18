"""Batch operation API routes for novels."""
from flask import jsonify, request

from storage_utils import (
    _build_file_delete_error_message,
    _collect_novel_file_deletion_targets,
    _delete_novel_files,
    _normalize_novel_ids,
)


def register_batch_routes(app, *, get_db):
    @app.route('/api/novels/batch/tags', methods=['POST'])
    def batch_add_tags():
        """批量为小说添加或移除标签"""
        data = request.json
        novel_ids = data.get('novel_ids', [])
        tag_ids = data.get('tag_ids', [])
        mode = data.get('mode', 'add')

        if not novel_ids:
            return jsonify({'success': False, 'message': '未选择小说'}), 400

        conn = get_db()
        cursor = conn.cursor()

        try:
            if mode == 'set':
                placeholders = ','.join(['?' for _ in novel_ids])
                cursor.execute(f'DELETE FROM novel_tags WHERE novel_id IN ({placeholders})', novel_ids)

            for novel_id in novel_ids:
                for tag_id in tag_ids:
                    if mode == 'remove':
                        cursor.execute('DELETE FROM novel_tags WHERE novel_id = ? AND tag_id = ?',
                                     (novel_id, tag_id))
                    else:
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
