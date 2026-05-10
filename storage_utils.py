"""本地小说文件存储和批量导入工具。"""
import hashlib
import json
import os
import re
from pathlib import Path

from flask import request

APP_ROOT = Path(__file__).resolve().parent
UPLOAD_ROOT = APP_ROOT / 'library'
NOVEL_EXTENSIONS = {'.txt', '.epub', '.pdf', '.mobi', '.azw3', '.doc', '.docx', '.rtf'}
TEXT_READABLE_EXTENSIONS = {'.txt', '.epub'}
FILE_HASH_CHUNK_SIZE = 1024 * 1024


def sanitize_storage_name(name):
    """清理可安全写入本地文件系统的名称"""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', (name or '').strip())
    cleaned = cleaned.strip(' .')
    return cleaned or 'untitled'


def sanitize_relative_storage_path(relative_path, fallback_name='untitled.txt'):
    """清理相对存储路径并过滤危险路径片段"""
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


def calculate_file_sha256(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as input_file:
        for chunk in iter(lambda: input_file.read(FILE_HASH_CHUNK_SIZE), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def calculate_uploaded_file_metadata(file_storage):
    hasher = hashlib.sha256()
    total_size = 0
    stream = file_storage.stream

    try:
        stream.seek(0)
    except (AttributeError, OSError):
        pass

    for chunk in iter(lambda: stream.read(FILE_HASH_CHUNK_SIZE), b''):
        total_size += len(chunk)
        hasher.update(chunk)

    try:
        stream.seek(0)
    except (AttributeError, OSError):
        pass

    return {
        'file_size': total_size,
        'content_hash': hasher.hexdigest()
    }


def store_uploaded_file(file_storage, relative_path=None, namespace='manual', reuse_existing=False):
    """保存上传文件并返回库目录中的相对路径"""
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
    """解析数据库中的小说文件路径"""
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


def get_novel_file_metadata(file_path):
    actual_path, _ = resolve_novel_file_path(file_path)
    if not actual_path:
        return {
            'file_size': None,
            'content_hash': ''
        }

    return {
        'file_size': os.path.getsize(actual_path),
        'content_hash': calculate_file_sha256(actual_path)
    }


def normalize_content_hash(content_hash):
    return (content_hash or '').strip().lower()


def coerce_file_size(file_size):
    if file_size in (None, ''):
        return None
    try:
        value = int(file_size)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def prepare_import_novel_metadata(novel_data):
    file_path = (novel_data.get('file_path') or '').strip()
    file_size = coerce_file_size(novel_data.get('file_size'))
    content_hash = normalize_content_hash(novel_data.get('content_hash'))

    if file_path and (file_size is None or not content_hash):
        file_metadata = get_novel_file_metadata(file_path)
        if file_size is None:
            file_size = coerce_file_size(file_metadata.get('file_size'))
        if not content_hash:
            content_hash = normalize_content_hash(file_metadata.get('content_hash'))

    original_filename = (novel_data.get('original_filename') or '').strip()
    if not original_filename and file_path:
        original_filename = Path(file_path).name

    novel_data['file_size'] = file_size
    novel_data['content_hash'] = content_hash
    novel_data['original_filename'] = original_filename
    return novel_data


def backfill_potential_duplicate_hashes(cursor, file_size):
    query = '''
        SELECT id, file_path
        FROM novels
        WHERE file_path IS NOT NULL
          AND file_path != ''
          AND (content_hash IS NULL OR content_hash = '')
    '''
    params = []
    if file_size is not None:
        query += ' AND (file_size = ? OR file_size IS NULL)'
        params.append(file_size)

    cursor.execute(query, params)
    for row in cursor.fetchall():
        file_metadata = get_novel_file_metadata(row['file_path'])
        content_hash = normalize_content_hash(file_metadata.get('content_hash'))
        if not content_hash:
            continue
        cursor.execute('''
            UPDATE novels
            SET file_size = ?, content_hash = ?
            WHERE id = ?
        ''', (
            coerce_file_size(file_metadata.get('file_size')),
            content_hash,
            row['id']
        ))


def find_import_duplicate(cursor, novel_data):
    file_path = (novel_data.get('file_path') or '').strip()
    if file_path:
        cursor.execute('SELECT id FROM novels WHERE file_path = ? LIMIT 1', (file_path,))
        existing = cursor.fetchone()
        if existing:
            return existing

    content_hash = normalize_content_hash(novel_data.get('content_hash'))
    if not content_hash:
        return None

    backfill_potential_duplicate_hashes(cursor, coerce_file_size(novel_data.get('file_size')))
    cursor.execute('SELECT id FROM novels WHERE content_hash = ? LIMIT 1', (content_hash,))
    return cursor.fetchone()


def _normalize_novel_ids(novel_ids):
    normalized = []
    seen = set()

    for novel_id in novel_ids or []:
        try:
            current_id = int(novel_id)
        except (TypeError, ValueError):
            continue

        if current_id <= 0 or current_id in seen:
            continue

        seen.add(current_id)
        normalized.append(current_id)

    return normalized


def _cleanup_empty_parent_dirs(file_path):
    try:
        upload_root = UPLOAD_ROOT.resolve()
        current = Path(file_path).resolve().parent
    except Exception:
        return

    while current != upload_root and upload_root in current.parents:
        try:
            next(current.iterdir())
            break
        except StopIteration:
            current.rmdir()
            current = current.parent
        except OSError:
            break


def _collect_novel_file_deletion_targets(cursor, novel_ids):
    normalized_ids = _normalize_novel_ids(novel_ids)
    if not normalized_ids:
        return [], [], set()

    placeholders = ','.join(['?' for _ in normalized_ids])
    cursor.execute(
        f'SELECT id, title, file_path FROM novels WHERE id IN ({placeholders})',
        normalized_ids
    )
    rows = cursor.fetchall()

    file_paths = sorted({row['file_path'] for row in rows if row['file_path']})
    if not file_paths:
        return rows, [], set()

    file_placeholders = ','.join(['?' for _ in file_paths])
    cursor.execute(
        f'''SELECT file_path, COUNT(*) AS ref_count
            FROM novels
            WHERE file_path IN ({file_placeholders})
              AND id NOT IN ({placeholders})
            GROUP BY file_path''',
        file_paths + normalized_ids
    )
    shared_paths = {row['file_path'] for row in cursor.fetchall() if row['ref_count'] > 0}
    deletion_targets = [file_path for file_path in file_paths if file_path not in shared_paths]
    return rows, deletion_targets, shared_paths


def _delete_novel_files(file_paths):
    result = {
        'deleted': [],
        'missing': [],
        'failed': []
    }

    for file_path in file_paths:
        actual_path, _ = resolve_novel_file_path(file_path)
        if not actual_path:
            result['missing'].append(file_path)
            continue

        try:
            os.remove(actual_path)
            result['deleted'].append({'file_path': file_path, 'actual_path': actual_path})
            _cleanup_empty_parent_dirs(actual_path)
        except Exception as exc:
            result['failed'].append({
                'file_path': file_path,
                'actual_path': actual_path,
                'error': str(exc)
            })

    return result


def _build_file_delete_error_message(failed_items):
    preview = []
    for item in failed_items[:3]:
        preview.append(f"{item['file_path']}: {item['error']}")
    return '文件删除失败：' + '；'.join(preview)


def parse_import_request():
    """解析导入请求，支持 JSON 与 multipart/form-data"""
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

            file_metadata = calculate_uploaded_file_metadata(file_storage)
            stored_path = store_uploaded_file(
                file_storage,
                relative_path=relative_path,
                namespace='imports',
                reuse_existing=True
            )

            novel_data = dict(novels[index])
            novel_data['file_path'] = stored_path
            novel_data['file_size'] = file_metadata['file_size']
            novel_data['content_hash'] = file_metadata['content_hash']
            novel_data['original_filename'] = Path(relative_path).name or file_storage.filename
            novel_data['_uploaded_file'] = True
            prepared_novels.append(novel_data)

        return prepared_novels, tag_ids, default_status

    data = request.get_json(silent=True) or {}
    novels = data.get('novels', [])
    tag_ids = data.get('tag_ids', [])
    default_status = data.get('default_status', 0)
    return novels, tag_ids, default_status
