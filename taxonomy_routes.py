"""Category, tag, and library statistics API routes."""
import sqlite3

from flask import jsonify, request


def register_taxonomy_routes(app, *, get_db):
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
            cursor.execute('UPDATE novels SET category_id = NULL WHERE category_id = ?', (category_id,))
            cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            conn.close()

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
