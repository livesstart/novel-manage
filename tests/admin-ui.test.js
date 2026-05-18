const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const coreJs = fs.readFileSync(path.join(root, 'static/js/core.js'), 'utf8');
const adminJs = fs.readFileSync(path.join(root, 'static/js/admin.js'), 'utf8');
const appJs = fs.readFileSync(path.join(root, 'static/js/app.js'), 'utf8');
const appBindingsJs = fs.readFileSync(path.join(root, 'static/js/app-bindings.js'), 'utf8');
const adminCss = fs.readFileSync(path.join(root, 'static/css/admin.css'), 'utf8');

const requiredTemplateIds = [
    'login-screen',
    'login-form',
    'login-username',
    'login-password',
    'view-admin',
    'admin-login-required',
    'btn-admin-save-settings',
    'btn-admin-create-user',
    'admin-user-list',
    'btn-admin-logout',
];

for (const id of requiredTemplateIds) {
    assert.match(template, new RegExp(`id="${id}"`), `template should include #${id}`);
}

assert.match(template, /data-view="admin"/, 'sidebar should include the system management view');
assert.match(template, /是否开启登录/, 'management page should expose the login toggle');
assert.match(template, /用户管理/, 'management page should expose user management');
assert.match(template, /\/static\/js\/admin\.js/, 'template should load admin.js');

assert.match(coreJs, /authStatus: null/, 'global state should track auth status');
assert.match(coreJs, /parseApiResponse/, 'API wrapper should centralize response parsing');
assert.match(coreJs, /res\.status === 401/, 'API wrapper should handle unauthenticated API responses');

assert.match(adminJs, /async function initAuthGate\(\)/, 'admin.js should gate app initialization by auth status');
assert.match(adminJs, /function showLoginScreen/, 'admin.js should show the login screen');
assert.match(adminJs, /function canManageSystem/, 'admin.js should derive system management access');
assert.match(adminJs, /function syncAdminAccess/, 'admin.js should hide system management from regular users');
assert.match(adminJs, /async function loadAdminPanel\(\)/, 'admin.js should load management data');
assert.match(adminJs, /async function saveAdminSettings\(\)/, 'admin.js should save login settings');
assert.match(adminJs, /async function createAdminUser\(\)/, 'admin.js should create users');
assert.match(adminJs, /async function saveAdminUser/, 'admin.js should update users');
assert.match(adminJs, /async function deleteAdminUser/, 'admin.js should delete users');
assert.match(appJs, /const canEnterApp = await initAuthGate\(\)/, 'app init should respect the auth gate');
assert.match(appJs, /viewName === 'admin'/, 'app view switch should load admin panel');
assert.match(appJs, /!canManageSystem\(\)/, 'app view switch should reject admin view for regular users');
assert.match(appBindingsJs, /bindAdminEvents\(\)/, 'app should bind admin events');

assert.match(adminCss, /\.login-screen/, 'login screen should be styled');
assert.match(adminCss, /\.admin-shell/, 'admin page shell should be styled');
assert.match(template, /admin-create-panel/, 'new user form should use the polished create panel');
assert.match(template, /admin-input-wrap/, 'new user inputs should use icon input wrappers');
assert.match(adminCss, /\.admin-create-form/, 'new user form should use a compact responsive grid');
assert.match(adminCss, /\.admin-check-option/, 'new user permission toggles should be styled as options');
assert.match(adminCss, /\.admin-user-card/, 'admin user cards should be styled');
assert.match(adminCss, /\.switch/, 'login toggle should be styled');

console.log('admin UI checks passed');
