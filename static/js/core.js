/**
 * 本地小说管理器 - 前端应用
 */

// 全局状态
const state = {
    novels: [],
    categories: [],
    tags: [],
    currentView: 'novels',
    selectedTags: new Set(),
    expandedNovelTagIds: new Set(),
    filterTagQuery: '',
    filterTagsExpanded: false,
    editingNovel: null,
    detailNovel: null,
    detailCharacterAnalysis: null,
    detailSettingAnalysis: null,
    authStatus: null,
    editingCategory: null,
    editingTag: null,
    importStep: 1,
    scannedNovels: [],
    importFolderPath: '',
    // 批量操作状态
    selectedNovels: new Set(),
    batchActionMode: 'tags'
};

const NOVEL_TAG_VISIBLE_COUNT = 4;
const FILTER_TAG_COLLAPSED_LIMIT = 12;

const batchAIState = {
    queue: [],
    currentIndex: 0,
    isGenerating: false,
    isApplying: false,
    autoSkipOnError: true
};

// API 封装
async function parseApiResponse(res) {
    const payload = await res.json().catch(() => ({
        success: false,
        message: '服务器返回了无法解析的数据'
    }));

    if (res.status === 401 && typeof showLoginScreen === 'function') {
        showLoginScreen(payload.message || '请先登录');
    }

    return payload;
}

const api = {
    async get(url) {
        const res = await fetch(url);
        return parseApiResponse(res);
    },
    async post(url, data) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return parseApiResponse(res);
    },
    async postForm(url, formData) {
        const res = await fetch(url, {
            method: 'POST',
            body: formData
        });
        return parseApiResponse(res);
    },
    async put(url, data) {
        const res = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return parseApiResponse(res);
    },
    async delete(url) {
        const res = await fetch(url, { method: 'DELETE' });
        return parseApiResponse(res);
    }
};

// 初始化

function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getStatusText(status) {
    const statusMap = {
        0: '未读',
        1: '阅读中',
        2: '已读完'
    };
    return statusMap[status] || '未知';
}

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = document.createElement('i');
    icon.className = `fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}`;

    const messageEl = document.createElement('span');
    messageEl.textContent = message;

    toast.append(icon, messageEl);
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// ==================== 批量操作功能 ====================
