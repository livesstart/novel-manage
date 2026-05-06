"""Management settings, optional login, and user administration routes."""
import re
from functools import wraps

from flask import jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash


LOGIN_REQUIRED_KEY = 'login_required'


def ensure_management_schema(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            is_admin INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            last_login_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_app_users_active_admin ON app_users(is_active, is_admin)')
    cursor.execute('''
        INSERT OR IGNORE INTO app_settings (key, value)
        VALUES (?, '0')
    ''', (LOGIN_REQUIRED_KEY,))


def register_admin_routes(app, *, get_db):
    USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9_\-.]{3,32}$')

    def parse_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return False

    def get_setting(key, default=''):
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT value FROM app_settings WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row['value'] if row else default
        except Exception:
            return default
        finally:
            conn.close()

    def set_setting(key, value):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        ''', (key, str(value)))
        conn.commit()
        conn.close()

    def is_login_required():
        return parse_bool(get_setting(LOGIN_REQUIRED_KEY, '0'))

    def serialize_user(row):
        item = dict(row)
        item.pop('password_hash', None)
        item['is_admin'] = int(item.get('is_admin') or 0)
        item['is_active'] = int(item.get('is_active') or 0)
        return item

    def fetch_session_user():
        user_id = session.get('user_id')
        if not user_id:
            return None

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM app_users WHERE id = ? AND is_active = 1', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            session.clear()
            return None
        return serialize_user(row)

    def count_active_admins(cursor, *, exclude_user_id=None):
        query = 'SELECT COUNT(*) AS total FROM app_users WHERE is_active = 1 AND is_admin = 1'
        params = []
        if exclude_user_id:
            query += ' AND id != ?'
            params.append(exclude_user_id)
        cursor.execute(query, params)
        row = cursor.fetchone()
        return int(row['total'] if row else 0)

    def can_manage_system(user, *, login_required=None):
        if login_required is None:
            login_required = is_login_required()
        if not login_required:
            return True
        return bool(user and user.get('is_admin'))

    def validate_username(username):
        username = (username or '').strip()
        if not USERNAME_PATTERN.match(username):
            raise ValueError('用户名需为 3-32 位字母、数字、下划线、中横线或点')
        return username

    def validate_password(password, *, required):
        password = str(password or '')
        if not password:
            if required:
                raise ValueError('请填写密码')
            return ''
        if len(password) < 6:
            raise ValueError('密码至少 6 位')
        return password

    def require_management_access(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_login_required():
                return fn(*args, **kwargs)

            user = fetch_session_user()
            if not user:
                return jsonify({'success': False, 'message': '请先登录'}), 401
            if not user.get('is_admin'):
                return jsonify({'success': False, 'message': '只有管理员可以访问管理功能'}), 403
            return fn(*args, **kwargs)

        return wrapper

    @app.before_request
    def require_login_for_api():
        if request.endpoint == 'static':
            return None

        if request.path in {'/api/auth/status', '/api/auth/login'}:
            return None

        if not request.path.startswith('/api/'):
            return None

        if not is_login_required():
            return None

        if fetch_session_user():
            return None

        return jsonify({'success': False, 'message': '请先登录'}), 401

    @app.route('/api/auth/status', methods=['GET'])
    def get_auth_status():
        login_required = is_login_required()
        user = fetch_session_user()
        return jsonify({
            'success': True,
            'data': {
                'login_required': login_required,
                'authenticated': bool(user) if login_required else True,
                'user': user,
                'can_manage_system': can_manage_system(user, login_required=login_required),
            }
        })

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        password = str(data.get('password') or '')
        if not username or not password:
            return jsonify({'success': False, 'message': '请输入用户名和密码'}), 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM app_users WHERE username = ?', (username,))
        row = cursor.fetchone()
        if not row or not int(row['is_active'] or 0) or not check_password_hash(row['password_hash'], password):
            conn.close()
            return jsonify({'success': False, 'message': '用户名或密码错误'}), 401

        cursor.execute('UPDATE app_users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?', (row['id'],))
        conn.commit()
        conn.close()
        session['user_id'] = row['id']
        session.permanent = True

        return jsonify({'success': True, 'data': {'user': serialize_user(row)}})

    @app.route('/api/auth/logout', methods=['POST'])
    def logout():
        session.clear()
        return jsonify({'success': True})

    @app.route('/api/admin/settings', methods=['GET'])
    @require_management_access
    def get_admin_settings():
        return jsonify({
            'success': True,
            'data': {
                'login_required': is_login_required(),
            }
        })

    @app.route('/api/admin/settings', methods=['PUT'])
    @require_management_access
    def update_admin_settings():
        data = request.get_json(silent=True) or {}
        login_required = parse_bool(data.get('login_required'))

        if login_required:
            conn = get_db()
            cursor = conn.cursor()
            active_admin_count = count_active_admins(cursor)
            conn.close()
            if active_admin_count <= 0:
                return jsonify({'success': False, 'message': '请先创建至少一个启用的管理员用户'}), 400

        set_setting(LOGIN_REQUIRED_KEY, '1' if login_required else '0')
        return jsonify({
            'success': True,
            'data': {
                'login_required': login_required,
            }
        })

    @app.route('/api/admin/users', methods=['GET'])
    @require_management_access
    def list_admin_users():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM app_users ORDER BY is_active DESC, username ASC')
        users = [serialize_user(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'data': users})

    @app.route('/api/admin/users', methods=['POST'])
    @require_management_access
    def create_admin_user():
        data = request.get_json(silent=True) or {}
        try:
            username = validate_username(data.get('username'))
            password = validate_password(data.get('password'), required=True)
            display_name = (data.get('display_name') or '').strip()[:80]
            is_admin = 1 if parse_bool(data.get('is_admin', True)) else 0
            is_active = 1 if parse_bool(data.get('is_active', True)) else 0
        except ValueError as exc:
            return jsonify({'success': False, 'message': str(exc)}), 400

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO app_users (
                    username, password_hash, display_name, is_admin, is_active
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                username,
                generate_password_hash(password),
                display_name,
                is_admin,
                is_active,
            ))
            conn.commit()
            cursor.execute('SELECT * FROM app_users WHERE id = ?', (cursor.lastrowid,))
            user = serialize_user(cursor.fetchone())
            return jsonify({'success': True, 'data': user})
        except Exception as exc:
            conn.rollback()
            if 'UNIQUE' in str(exc).upper():
                return jsonify({'success': False, 'message': '用户名已存在'}), 400
            return jsonify({'success': False, 'message': str(exc)}), 500
        finally:
            conn.close()

    @app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
    @require_management_access
    def update_admin_user(user_id):
        data = request.get_json(silent=True) or {}
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM app_users WHERE id = ?', (user_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            return jsonify({'success': False, 'message': '用户不存在'}), 404

        try:
            username = validate_username(data.get('username', existing['username']))
            password = validate_password(data.get('password'), required=False)
            display_name = (data.get('display_name', existing['display_name']) or '').strip()[:80]
            is_admin = 1 if parse_bool(data.get('is_admin', existing['is_admin'])) else 0
            is_active = 1 if parse_bool(data.get('is_active', existing['is_active'])) else 0
        except ValueError as exc:
            conn.close()
            return jsonify({'success': False, 'message': str(exc)}), 400

        if int(existing['is_active'] or 0) and int(existing['is_admin'] or 0) and (not is_active or not is_admin):
            if count_active_admins(cursor, exclude_user_id=user_id) <= 0:
                conn.close()
                return jsonify({'success': False, 'message': '不能停用或降级最后一个启用的管理员'}), 400

        try:
            if password:
                cursor.execute('''
                    UPDATE app_users
                    SET username = ?, password_hash = ?, display_name = ?,
                        is_admin = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    username,
                    generate_password_hash(password),
                    display_name,
                    is_admin,
                    is_active,
                    user_id,
                ))
            else:
                cursor.execute('''
                    UPDATE app_users
                    SET username = ?, display_name = ?, is_admin = ?,
                        is_active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    username,
                    display_name,
                    is_admin,
                    is_active,
                    user_id,
                ))
            conn.commit()
            cursor.execute('SELECT * FROM app_users WHERE id = ?', (user_id,))
            user = serialize_user(cursor.fetchone())
            return jsonify({'success': True, 'data': user})
        except Exception as exc:
            conn.rollback()
            if 'UNIQUE' in str(exc).upper():
                return jsonify({'success': False, 'message': '用户名已存在'}), 400
            return jsonify({'success': False, 'message': str(exc)}), 500
        finally:
            conn.close()

    @app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
    @require_management_access
    def delete_admin_user(user_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM app_users WHERE id = ?', (user_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            return jsonify({'success': False, 'message': '用户不存在'}), 404

        if int(existing['is_active'] or 0) and int(existing['is_admin'] or 0):
            if count_active_admins(cursor, exclude_user_id=user_id) <= 0:
                conn.close()
                return jsonify({'success': False, 'message': '不能删除最后一个启用的管理员'}), 400

        cursor.execute('DELETE FROM app_users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        if session.get('user_id') == user_id:
            session.clear()
        return jsonify({'success': True})
