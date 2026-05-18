// 前端入口：初始化应用、切换视图并绑定事件。
async function init() {
    const canEnterApp = await initAuthGate();
    if (!canEnterApp) {
        return;
    }

    await Promise.all([
        loadStats(),
        loadCategories(),
        loadTags(),
        loadNovels()
    ]);
    bindEvents();
}

function switchView(viewName) {
    if (viewName === 'admin' && typeof canManageSystem === 'function' && !canManageSystem()) {
        if (typeof syncAdminAccess === 'function') {
            syncAdminAccess();
        }
        showToast('普通用户无权访问系统管理', 'error');
        viewName = 'novels';
    }

    state.currentView = viewName;

    // 更新导航
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.view === viewName);
    });

    // 更新视图显示
    document.querySelectorAll('.view').forEach(view => {
        view.classList.toggle('hidden', !view.id.includes(viewName));
    });

    // 更新筛选栏显示
    const filterBar = document.querySelector('.filter-bar');
    filterBar.style.display = viewName === 'novels' ? 'flex' : 'none';

    // 更新添加按钮显示
    const addBtn = document.getElementById('btn-add-novel');
    addBtn.style.display = viewName === 'novels' ? 'flex' : 'none';

    // 更新批量导入按钮显示
    const batchImportBtn = document.getElementById('btn-batch-import');
    batchImportBtn.style.display = viewName === 'novels' ? 'flex' : 'none';

    if (viewName === 'novels') {
        loadStats();
        applyFilters();
    }

    if (viewName === 'characters') {
        renderCharacterFilters();
        loadCharacterLibrary();
    }

    // 加载爬虫数据
    if (viewName === 'crawler') {
        loadCrawlerStats();
        loadCrawlerRules();
        loadCrawlerTasks();
        startCrawlerAutoRefresh();
    } else {
        stopCrawlerAutoRefresh();
    }

    // 加载 AI 配置数据
    if (viewName === 'ai-config') {
        loadAIProviders();
        loadAIConfigs();
    }

    if (viewName === 'admin') {
        loadAdminPanel();
    }
}


document.addEventListener('DOMContentLoaded', init);
