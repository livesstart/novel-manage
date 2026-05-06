const adminState = {
    settings: null,
    users: [],
    eventsBound: false,
    authEventsBound: false
};

function showLoginScreen(message = '') {
    document.body.classList.remove('auth-pending');
    document.getElementById('login-screen')?.classList.remove('hidden');
    const appContainer = document.querySelector('.app-container');
    if (appContainer) {
        appContainer.hidden = true;
    }
    document.getElementById('login-error').textContent = message;
    document.getElementById('login-username')?.focus();
}

function hideLoginScreen() {
    document.body.classList.remove('auth-pending');
    document.getElementById('login-screen')?.classList.add('hidden');
    const appContainer = document.querySelector('.app-container');
    if (appContainer) {
        appContainer.hidden = false;
    }
}

function canManageSystem(status = state.authStatus) {
    if (!status) return true;
    if (Object.prototype.hasOwnProperty.call(status, 'can_manage_system')) {
        return Boolean(status.can_manage_system);
    }
    return !status.login_required || Boolean(status.user?.is_admin);
}

function syncAdminAccess(status = state.authStatus) {
    const allowed = canManageSystem(status);
    document.querySelectorAll('[data-view="admin"]').forEach(item => {
        item.hidden = !allowed;
        item.setAttribute('aria-hidden', String(!allowed));
        item.tabIndex = allowed ? 0 : -1;
        if (!allowed) {
            item.classList.remove('active');
        }
    });

    const adminView = document.getElementById('view-admin');
    if (adminView && !allowed) {
        adminView.classList.add('hidden');
    }
}

function bindAuthEvents() {
    if (adminState.authEventsBound) return;
    adminState.authEventsBound = true;

    document.getElementById('login-form')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        await loginWithPassword();
    });
}

async function initAuthGate() {
    bindAuthEvents();
    const res = await api.get('/api/auth/status');
    if (!res.success) {
        document.body.classList.remove('auth-pending');
        return true;
    }

    state.authStatus = res.data;
    syncAdminAccess(res.data);
    if (res.data.login_required && !res.data.authenticated) {
        showLoginScreen('');
        return false;
    }

    hideLoginScreen();
    return true;
}

async function loginWithPassword() {
    const usernameInput = document.getElementById('login-username');
    const passwordInput = document.getElementById('login-password');
    const errorEl = document.getElementById('login-error');
    const button = document.getElementById('btn-login-submit');
    const originalHtml = button.innerHTML;

    errorEl.textContent = '';
    button.disabled = true;
    button.innerHTML = '<span class="loading"></span> 登录中';

    try {
        const res = await api.post('/api/auth/login', {
            username: usernameInput.value.trim(),
            password: passwordInput.value
        });
        if (!res.success) {
            errorEl.textContent = res.message || '登录失败';
            return;
        }
        window.location.reload();
    } catch (err) {
        errorEl.textContent = '登录失败: ' + err.message;
    } finally {
        button.disabled = false;
        button.innerHTML = originalHtml;
    }
}

function bindAdminEvents() {
    if (adminState.eventsBound) return;
    adminState.eventsBound = true;

    document.getElementById('btn-admin-save-settings')?.addEventListener('click', saveAdminSettings);
    document.getElementById('btn-admin-create-user')?.addEventListener('click', createAdminUser);
    document.getElementById('btn-admin-logout')?.addEventListener('click', logoutAdminUser);
    document.getElementById('admin-user-list')?.addEventListener('click', async (event) => {
        const button = event.target.closest('button[data-action]');
        if (!button) return;

        const card = button.closest('.admin-user-card');
        const userId = Number(card?.dataset.userId || 0);
        if (!userId) return;

        if (button.dataset.action === 'save') {
            await saveAdminUser(card, userId);
        }
        if (button.dataset.action === 'delete') {
            await deleteAdminUser(userId);
        }
    });
}

function updateAdminHeader(status = state.authStatus) {
    const userEl = document.getElementById('admin-current-user');
    const logoutBtn = document.getElementById('btn-admin-logout');
    if (!userEl || !logoutBtn) return;

    syncAdminAccess(status);

    const user = status?.user;
    if (status?.login_required && user) {
        userEl.textContent = `当前用户：${user.display_name || user.username}`;
        logoutBtn.hidden = false;
        return;
    }

    userEl.textContent = status?.login_required ? '登录已开启' : '当前未启用登录';
    logoutBtn.hidden = !user;
}

function renderAdminSettings(settings) {
    adminState.settings = settings || { login_required: false };
    const toggle = document.getElementById('admin-login-required');
    const status = document.getElementById('admin-login-required-status');
    toggle.checked = Boolean(adminState.settings.login_required);
    status.textContent = toggle.checked ? '当前开启' : '当前关闭';
}

function renderAdminUsers(users = []) {
    adminState.users = users;
    const container = document.getElementById('admin-user-list');
    if (!users.length) {
        container.innerHTML = '<div class="admin-empty">暂无用户，先创建一个管理员再开启登录。</div>';
        return;
    }

    container.innerHTML = users.map(user => `
        <article class="admin-user-card" data-user-id="${user.id}">
            <div class="admin-user-main">
                <strong>${escapeHtml(user.username)}</strong>
                <span>${escapeHtml(user.display_name || '未设置显示名称')} · ${user.last_login_at ? `上次登录 ${escapeHtml(formatDateTime(user.last_login_at))}` : '尚未登录'}</span>
            </div>
            <div class="admin-user-form">
                <input type="text" data-field="username" value="${escapeHtml(user.username)}" placeholder="用户名">
                <input type="text" data-field="display_name" value="${escapeHtml(user.display_name || '')}" placeholder="显示名称">
                <input type="password" data-field="password" placeholder="留空则不修改密码">
                <div class="admin-user-flags">
                    <label><input type="checkbox" data-field="is_admin" ${user.is_admin ? 'checked' : ''}> 管理员</label>
                    <label><input type="checkbox" data-field="is_active" ${user.is_active ? 'checked' : ''}> 启用</label>
                </div>
            </div>
            <div class="admin-user-actions">
                <button class="btn btn-sm btn-secondary" data-action="save">保存</button>
                <button class="btn btn-sm btn-danger" data-action="delete">删除</button>
            </div>
        </article>
    `).join('');
}

async function loadAdminPanel() {
    if (!canManageSystem()) {
        syncAdminAccess();
        showToast('普通用户无权访问系统管理', 'error');
        if (state.currentView === 'admin' && typeof switchView === 'function') {
            switchView('novels');
        }
        return;
    }

    try {
        const [statusRes, settingsRes, usersRes] = await Promise.all([
            api.get('/api/auth/status'),
            api.get('/api/admin/settings'),
            api.get('/api/admin/users')
        ]);

        if (statusRes.success) {
            state.authStatus = statusRes.data;
            if (!canManageSystem(statusRes.data)) {
                syncAdminAccess(statusRes.data);
                showToast('普通用户无权访问系统管理', 'error');
                if (state.currentView === 'admin' && typeof switchView === 'function') {
                    switchView('novels');
                }
                return;
            }
            updateAdminHeader(statusRes.data);
        }
        if (settingsRes.success) {
            renderAdminSettings(settingsRes.data);
        }
        if (usersRes.success) {
            renderAdminUsers(usersRes.data);
        }
    } catch (err) {
        console.error('加载系统管理数据失败:', err);
        showToast('加载系统管理数据失败', 'error');
    }
}

async function saveAdminSettings() {
    const loginRequired = document.getElementById('admin-login-required').checked;
    const res = await api.put('/api/admin/settings', {
        login_required: loginRequired
    });

    if (!res.success) {
        showToast(res.message || '保存登录设置失败', 'error');
        renderAdminSettings(adminState.settings);
        return;
    }

    renderAdminSettings(res.data);
    showToast(loginRequired ? '登录保护已开启' : '登录保护已关闭');
    if (loginRequired && !state.authStatus?.user) {
        showLoginScreen('登录已开启，请使用用户账号登录');
        return;
    }
    await loadAdminPanel();
}

async function createAdminUser() {
    const data = {
        username: document.getElementById('admin-new-username').value.trim(),
        display_name: document.getElementById('admin-new-display-name').value.trim(),
        password: document.getElementById('admin-new-password').value,
        is_admin: document.getElementById('admin-new-is-admin').checked,
        is_active: document.getElementById('admin-new-is-active').checked
    };

    const res = await api.post('/api/admin/users', data);
    if (!res.success) {
        showToast(res.message || '创建用户失败', 'error');
        return;
    }

    document.getElementById('admin-new-username').value = '';
    document.getElementById('admin-new-display-name').value = '';
    document.getElementById('admin-new-password').value = '';
    document.getElementById('admin-new-is-admin').checked = true;
    document.getElementById('admin-new-is-active').checked = true;
    showToast('用户已创建');
    await loadAdminPanel();
}

function collectAdminUserCard(card) {
    return {
        username: card.querySelector('[data-field="username"]').value.trim(),
        display_name: card.querySelector('[data-field="display_name"]').value.trim(),
        password: card.querySelector('[data-field="password"]').value,
        is_admin: card.querySelector('[data-field="is_admin"]').checked,
        is_active: card.querySelector('[data-field="is_active"]').checked
    };
}

async function saveAdminUser(card, userId) {
    const res = await api.put(`/api/admin/users/${userId}`, collectAdminUserCard(card));
    if (!res.success) {
        showToast(res.message || '保存用户失败', 'error');
        return;
    }
    showToast('用户已保存');
    await loadAdminPanel();
}

async function deleteAdminUser(userId) {
    if (!confirm('确定删除这个用户？删除后无法用该账号登录。')) {
        return;
    }

    const res = await api.delete(`/api/admin/users/${userId}`);
    if (!res.success) {
        showToast(res.message || '删除用户失败', 'error');
        return;
    }
    showToast('用户已删除');
    await loadAdminPanel();
}

async function logoutAdminUser() {
    const res = await api.post('/api/auth/logout', {});
    if (!res.success) {
        showToast(res.message || '退出登录失败', 'error');
        return;
    }
    window.location.reload();
}
