import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as novel_app


class AdminAuthTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.init_db()
        self.client = novel_app.app.test_client()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        self.tmpdir.cleanup()

    def create_admin(self, username='admin', password='secret123'):
        response = self.client.post('/api/admin/users', json={
            'username': username,
            'password': password,
            'display_name': '管理员',
            'is_admin': True,
            'is_active': True,
        })
        self.assertEqual(response.status_code, 200)
        return response.get_json()['data']

    def create_user(self, username='reader', password='secret123', is_admin=False):
        response = self.client.post('/api/admin/users', json={
            'username': username,
            'password': password,
            'display_name': username,
            'is_admin': is_admin,
            'is_active': True,
        })
        self.assertEqual(response.status_code, 200)
        return response.get_json()['data']

    def test_login_is_disabled_by_default_and_admin_api_is_available(self):
        status_response = self.client.get('/api/auth/status')
        status_payload = status_response.get_json()

        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_payload['success'])
        self.assertFalse(status_payload['data']['login_required'])
        self.assertTrue(status_payload['data']['authenticated'])

        users_response = self.client.get('/api/admin/users')
        self.assertEqual(users_response.status_code, 200)
        self.assertTrue(users_response.get_json()['success'])

    def test_cannot_enable_login_without_active_admin(self):
        response = self.client.put('/api/admin/settings', json={'login_required': True})
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload['success'])
        self.assertIn('管理员用户', payload['message'])

    def test_enable_login_blocks_api_until_user_logs_in(self):
        self.create_admin()
        enable_response = self.client.put('/api/admin/settings', json={'login_required': True})
        self.assertEqual(enable_response.status_code, 200)

        blocked_response = self.client.get('/api/novels')
        self.assertEqual(blocked_response.status_code, 401)

        login_response = self.client.post('/api/auth/login', json={
            'username': 'admin',
            'password': 'secret123',
        })
        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(login_response.get_json()['success'])

        allowed_response = self.client.get('/api/novels')
        self.assertEqual(allowed_response.status_code, 200)
        self.assertTrue(allowed_response.get_json()['success'])

    def test_regular_user_cannot_manage_system_when_login_is_enabled(self):
        self.create_admin()
        self.create_user()
        enable_response = self.client.put('/api/admin/settings', json={'login_required': True})
        self.assertEqual(enable_response.status_code, 200)

        login_response = self.client.post('/api/auth/login', json={
            'username': 'reader',
            'password': 'secret123',
        })
        self.assertEqual(login_response.status_code, 200)

        status_response = self.client.get('/api/auth/status')
        status_payload = status_response.get_json()
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_payload['data']['authenticated'])
        self.assertFalse(status_payload['data']['user']['is_admin'])
        self.assertFalse(status_payload['data']['can_manage_system'])

        users_response = self.client.get('/api/admin/users')
        self.assertEqual(users_response.status_code, 403)

    def test_prevent_deleting_last_active_admin(self):
        admin = self.create_admin()
        self.client.put('/api/admin/settings', json={'login_required': True})
        self.client.post('/api/auth/login', json={
            'username': 'admin',
            'password': 'secret123',
        })

        response = self.client.delete(f"/api/admin/users/{admin['id']}")
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload['success'])
        self.assertIn('最后一个启用的管理员', payload['message'])


if __name__ == '__main__':
    unittest.main()
