"""Folder scanning and batch import API routes."""
import os
import re
from pathlib import Path

from flask import jsonify, request

from storage_utils import (
    NOVEL_EXTENSIONS,
    find_import_duplicate,
    parse_import_request,
    prepare_import_novel_metadata,
)


def scan_folder(folder_path, create_category_from_folder=True):
    """扫描文件夹中的小说文件"""
    novels = []
    folder_path = Path(folder_path)

    if not folder_path.exists():
        return novels

    for root, dirs, files in os.walk(folder_path):
        root_path = Path(root)

        category_name = None
        if create_category_from_folder:
            try:
                rel_path = root_path.relative_to(folder_path)
                if rel_path.parts:
                    category_name = rel_path.parts[0]
            except ValueError:
                pass

        for filename in files:
            file_ext = Path(filename).suffix.lower()
            if file_ext in NOVEL_EXTENSIONS:
                file_path = root_path / filename
                title = Path(filename).stem
                title = re.sub(r'^\d+[\s\-_\.]+', '', title)
                title = title.strip()

                novels.append({
                    'file_path': str(file_path),
                    'title': title,
                    'category_name': category_name,
                    'file_size': file_path.stat().st_size
                })

    return novels


def register_import_routes(app, *, get_db):
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
                    novel_data = prepare_import_novel_metadata(novel_data)
                    if find_import_duplicate(cursor, novel_data):
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
                        INSERT INTO novels (
                            title, author, file_path, category_id, status,
                            file_size, content_hash, original_filename
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        novel_data.get('title', '未命名'),
                        novel_data.get('author', ''),
                        novel_data.get('file_path'),
                        category_id,
                        default_status,
                        novel_data.get('file_size'),
                        novel_data.get('content_hash'),
                        novel_data.get('original_filename')
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
