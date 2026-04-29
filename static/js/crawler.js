const crawlerState = {
    tasks: [],
    rules: [],
    filter: '',
    statusFilter: '',
    refreshTimer: null,
    editingRule: null
};

async function loadCrawlerStats() {
    try {
        const res = await api.get('/api/crawler/stats');
        if (!res.success) {
            throw new Error(res.message || '加载失败');
        }

        document.getElementById('crawler-total-tasks').textContent = res.data.total_tasks ?? 0;
        document.getElementById('crawler-running-tasks').textContent = res.data.running_tasks ?? 0;
        document.getElementById('crawler-completed-tasks').textContent = res.data.completed_tasks ?? 0;
        document.getElementById('crawler-downloaded-novels').textContent = res.data.downloaded_novels ?? 0;
    } catch (err) {
        console.error('加载爬虫统计失败:', err);
        document.getElementById('crawler-total-tasks').textContent = '0';
        document.getElementById('crawler-running-tasks').textContent = '0';
        document.getElementById('crawler-completed-tasks').textContent = '0';
        document.getElementById('crawler-downloaded-novels').textContent = '0';
    }
}

async function loadCrawlerRules() {
    const container = document.getElementById('crawler-rules-list');

    try {
        const res = await api.get('/api/crawler/rules');
        if (!res.success) {
            throw new Error(res.message || '加载失败');
        }

        crawlerState.rules = Array.isArray(res.data) ? res.data : [];
        renderCrawlerRules();
        renderCrawlerRuleSelect();
    } catch (err) {
        console.error('加载站点规则失败:', err);
        if (container) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-globe"></i>
                    <h3>加载站点规则失败</h3>
                    <p>${escapeHtml(err.message || '请稍后重试')}</p>
                </div>
            `;
        }
    }
}

async function loadCrawlerTasks() {
    const container = document.getElementById('crawler-tasks-list');

    try {
        const params = new URLSearchParams();
        if (crawlerState.filter) params.append('keyword', crawlerState.filter);
        if (crawlerState.statusFilter) params.append('status', crawlerState.statusFilter);

        const res = await api.get(`/api/crawler/tasks?${params.toString()}`);
        if (!res.success) {
            throw new Error(res.message || '加载失败');
        }

        crawlerState.tasks = res.data || [];
        renderCrawlerTasks();
    } catch (err) {
        console.error('加载爬虫任务失败:', err);
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-bug"></i>
                <h3>加载失败</h3>
                <p>${escapeHtml(err.message || '请稍后重试')}</p>
            </div>
        `;
    }
}

function openAddCrawlerTaskModal() {
    resetCrawlerTaskModal();
    openModal('crawler-task-modal');
}

function resetCrawlerTaskModal() {
    document.getElementById('crawler-task-modal-title').textContent = '新建爬虫任务';
    document.getElementById('crawler-task-form').reset();
    document.getElementById('crawler-task-start-immediately').checked = true;
    document.getElementById('crawler-task-batch-from-listing').checked = false;
    document.getElementById('crawler-task-listing-limit').value = '10';
    renderCrawlerTagSelector();
    renderCrawlerRuleSelect();
    updateCategorySelects();
}

function openAddCrawlerRuleModal() {
    resetCrawlerRuleModal();
    openModal('crawler-rule-modal');
}

function resetCrawlerRuleModal() {
    crawlerState.editingRule = null;
    document.getElementById('crawler-rule-modal-title').textContent = '新增站点规则';
    document.getElementById('crawler-rule-form').reset();
    document.getElementById('crawler-rule-id').value = '';
    document.getElementById('crawler-rule-sort-order').value = '100';
    document.getElementById('crawler-rule-is-active').checked = true;
}

function renderCrawlerRules() {
    const container = document.getElementById('crawler-rules-list');
    if (!container) return;

    if (!crawlerState.rules.length) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-globe"></i>
                <h3>暂无站点规则</h3>
                <p>可以先添加 example.com 或 *.example.com 对应的抓取规则</p>
            </div>
        `;
        return;
    }

    container.innerHTML = crawlerState.rules.map(rule => {
        const selectorCount = [
            rule.title_selector,
            rule.content_selector,
            rule.listing_link_selector,
            rule.related_thread_selector,
            rule.chapter_link_selector,
            rule.chapter_title_selector
        ].filter(Boolean).length;

        return `
            <div class="crawler-rule-card ${rule.is_active ? 'active' : 'inactive'}">
                <div class="crawler-rule-card-top">
                    <div class="crawler-rule-card-main">
                        <h4>${escapeHtml(rule.name)}</h4>
                        <div class="crawler-rule-host">${escapeHtml(rule.host_pattern)}</div>
                    </div>
                    <span class="crawler-task-badge ${rule.is_active ? '' : 'is-muted'}">${rule.is_active ? '已启用' : '已停用'}</span>
                </div>
                <div class="crawler-rule-meta">
                    <span>优先级：${Number(rule.sort_order || 0)}</span>
                    <span>选择器：${selectorCount} 项</span>
                    <span>${rule.listing_link_selector ? '支持列表页批量' : '不支持列表页批量'}</span>
                    <span>${rule.related_thread_selector ? '支持正文页关联合并' : '不合并关联帖子'}</span>
                    <span>${rule.chapter_link_selector ? '支持目录页' : '偏正文页'}</span>
                </div>
                ${rule.notes ? `<div class="crawler-rule-notes">${escapeHtml(rule.notes)}</div>` : ''}
                <div class="crawler-rule-actions">
                    <button class="btn btn-sm btn-primary" onclick="editCrawlerRule(${rule.id})">
                        <i class="fas fa-edit"></i>
                        编辑
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteCrawlerRule(${rule.id})">
                        <i class="fas fa-trash"></i>
                        删除
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function renderCrawlerRuleSelect(selectedRuleId = '') {
    const select = document.getElementById('crawler-task-site-rule');
    if (!select) return;

    const activeRules = crawlerState.rules.filter(rule => rule.is_active);
    const options = activeRules.map(rule => `
        <option value="${rule.id}">${escapeHtml(rule.name)} (${escapeHtml(rule.host_pattern)})</option>
    `).join('');

    select.innerHTML = `
        <option value="">自动匹配站点规则（无则使用通用规则）</option>
        ${options}
    `;

    if (selectedRuleId) {
        select.value = String(selectedRuleId);
    }
}

function collectCrawlerRuleFormData() {
    return {
        name: document.getElementById('crawler-rule-name').value.trim(),
        host_pattern: document.getElementById('crawler-rule-host-pattern').value.trim(),
        title_selector: document.getElementById('crawler-rule-title-selector').value.trim(),
        content_selector: document.getElementById('crawler-rule-content-selector').value.trim(),
        listing_link_selector: document.getElementById('crawler-rule-listing-link-selector').value.trim(),
        related_thread_selector: document.getElementById('crawler-rule-related-thread-selector').value.trim(),
        chapter_link_selector: document.getElementById('crawler-rule-chapter-link-selector').value.trim(),
        chapter_title_selector: document.getElementById('crawler-rule-chapter-title-selector').value.trim(),
        remove_selectors: document.getElementById('crawler-rule-remove-selectors').value.trim(),
        sort_order: parseInt(document.getElementById('crawler-rule-sort-order').value || '100', 10),
        is_active: document.getElementById('crawler-rule-is-active').checked,
        notes: document.getElementById('crawler-rule-notes').value.trim()
    };
}

async function saveCrawlerRule() {
    const ruleId = document.getElementById('crawler-rule-id').value.trim();
    const payload = collectCrawlerRuleFormData();

    if (!payload.name) {
        showToast('请输入规则名称', 'error');
        return;
    }
    if (!payload.host_pattern) {
        showToast('请输入站点域名', 'error');
        return;
    }
    if (!payload.content_selector) {
        showToast('请至少填写正文选择器', 'error');
        return;
    }

    const saveButton = document.getElementById('btn-save-crawler-rule');
    const originalHtml = saveButton.innerHTML;
    saveButton.disabled = true;
    saveButton.innerHTML = '<span class="loading"></span> 保存中';

    try {
        const res = ruleId
            ? await api.put(`/api/crawler/rules/${ruleId}`, payload)
            : await api.post('/api/crawler/rules', payload);

        if (!res.success) {
            throw new Error(res.message || '保存失败');
        }

        closeModal('crawler-rule-modal');
        await loadCrawlerRules();
        showToast(ruleId ? '站点规则已更新' : '站点规则已创建', 'success');
    } catch (err) {
        console.error('保存站点规则失败:', err);
        showToast(err.message || '保存失败', 'error');
    } finally {
        saveButton.disabled = false;
        saveButton.innerHTML = originalHtml;
    }
}

function editCrawlerRule(ruleId) {
    const rule = crawlerState.rules.find(item => item.id === ruleId);
    if (!rule) return;

    crawlerState.editingRule = rule;
    document.getElementById('crawler-rule-id').value = String(rule.id);
    document.getElementById('crawler-rule-modal-title').textContent = '编辑站点规则';
    document.getElementById('crawler-rule-name').value = rule.name || '';
    document.getElementById('crawler-rule-host-pattern').value = rule.host_pattern || '';
    document.getElementById('crawler-rule-title-selector').value = rule.title_selector || '';
    document.getElementById('crawler-rule-content-selector').value = rule.content_selector || '';
    document.getElementById('crawler-rule-listing-link-selector').value = rule.listing_link_selector || '';
    document.getElementById('crawler-rule-related-thread-selector').value = rule.related_thread_selector || '';
    document.getElementById('crawler-rule-chapter-link-selector').value = rule.chapter_link_selector || '';
    document.getElementById('crawler-rule-chapter-title-selector').value = rule.chapter_title_selector || '';
    document.getElementById('crawler-rule-remove-selectors').value = rule.remove_selectors || '';
    document.getElementById('crawler-rule-sort-order').value = String(rule.sort_order ?? 100);
    document.getElementById('crawler-rule-is-active').checked = Boolean(rule.is_active);
    document.getElementById('crawler-rule-notes').value = rule.notes || '';
    openModal('crawler-rule-modal');
}

async function deleteCrawlerRule(ruleId) {
    if (!confirm('确定要删除这条站点规则吗？删除后相关任务会自动回退到通用规则或重新自动匹配。')) {
        return;
    }

    try {
        const res = await api.delete(`/api/crawler/rules/${ruleId}`);
        if (!res.success) {
            throw new Error(res.message || '删除失败');
        }

        await Promise.all([loadCrawlerRules(), loadCrawlerTasks()]);
        showToast('站点规则已删除', 'success');
    } catch (err) {
        console.error('删除站点规则失败:', err);
        showToast(err.message || '删除失败', 'error');
    }
}

function renderCrawlerTagSelector(selectedTagIds = []) {
    const container = document.getElementById('crawler-task-tag-selector');
    if (!container) return;

    const selectedSet = new Set((selectedTagIds || []).map(id => Number(id)));
    if (state.tags.length === 0) {
        container.innerHTML = '<span class="form-hint">暂无标签，可先在标签管理中创建</span>';
        return;
    }

    container.innerHTML = state.tags.map(tag => `
        <span class="crawler-tag-option ${selectedSet.has(Number(tag.id)) ? 'selected' : ''}"
              data-id="${tag.id}"
              style="border-color: ${selectedSet.has(Number(tag.id)) ? tag.color : ''}; color: ${selectedSet.has(Number(tag.id)) ? tag.color : ''};"
              onclick="toggleCrawlerTaskTag(this)">
            <i class="fas fa-tag"></i>
            ${escapeHtml(tag.name)}
        </span>
    `).join('');
}

function toggleCrawlerTaskTag(element) {
    element.classList.toggle('selected');
}

function getSelectedCrawlerTagIds() {
    return Array.from(document.querySelectorAll('#crawler-task-tag-selector .crawler-tag-option.selected'))
        .map(item => Number(item.dataset.id))
        .filter(Boolean);
}

function renderCrawlerTasks() {
    const container = document.getElementById('crawler-tasks-list');
    if (!crawlerState.tasks.length) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-spider"></i>
                <h3>暂无爬虫任务</h3>
                <p>点击“新建爬虫任务”后即可抓取目录页、正文页或 txt 链接</p>
            </div>
        `;
        return;
    }

    container.innerHTML = crawlerState.tasks.map(task => {
        const progress = Number(task.progress || 0);
        const totalChapters = Number(task.total_chapters || 0);
        const crawledChapters = Number(task.crawled_chapters || 0);
        const attemptCount = Number(task.attempt_count || 0);
        const maxAttempts = Number(task.max_attempts || 1);
        const progressText = totalChapters > 1
            ? `${progress}% · ${crawledChapters}/${totalChapters} 章`
            : `${progress}%`;
        const noticeLabel = task.status === 'failed' ? '失败原因' : '提示';

        return `
            <div class="crawler-task-item">
                <span class="crawler-task-status status-${escapeHtml(task.status)}"></span>
                <div class="crawler-task-info">
                    <div class="crawler-task-name-row">
                        <div class="crawler-task-name">${escapeHtml(task.name || task.title || '未命名任务')}</div>
                        <span class="crawler-task-badge">${escapeHtml(getCrawlerStatusText(task.status))}</span>
                        ${task.novel_id ? '<span class="crawler-task-badge">已入库</span>' : ''}
                        <span class="crawler-task-badge rule ${escapeHtml(task.effective_site_rule_mode || 'default')}">${escapeHtml(task.effective_site_rule_name || '通用规则')}</span>
                    </div>
                    <div class="crawler-task-meta">
                        <span>书名：${escapeHtml(task.title || '自动提取')}</span>
                        <span>作者：${escapeHtml(task.author || '未填写')}</span>
                        <span>分类：${escapeHtml(task.category_name || '未分类')}</span>
                        <span>规则：${escapeHtml(task.effective_site_rule_host_pattern || '通用规则')}</span>
                        <span>尝试：${attemptCount}/${maxAttempts}</span>
                        <span>更新时间：${escapeHtml(formatCrawlerDateTime(task.updated_at))}</span>
                    </div>
                    <div class="crawler-task-link">${escapeHtml(task.source_url || '')}</div>
                    ${task.last_error ? `<div class="crawler-task-error">${noticeLabel}：${escapeHtml(task.last_error)}</div>` : ''}
                </div>
                <div class="crawler-task-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${Math.max(0, Math.min(progress, 100))}%"></div>
                    </div>
                    <div class="progress-text">${escapeHtml(progressText)}</div>
                </div>
                <div class="crawler-task-actions">
                    <button class="btn btn-secondary" onclick="startCrawlerTask(${task.id})" ${task.status === 'running' ? 'disabled' : ''}>
                        <i class="fas fa-${task.status === 'failed' ? 'rotate-right' : 'play'}"></i>
                        ${task.status === 'failed' ? '重试' : task.status === 'completed' ? '重新抓取' : '开始'}
                    </button>
                    <button class="btn btn-danger" onclick="deleteCrawlerTask(${task.id})" ${task.status === 'running' ? 'disabled' : ''}>
                        <i class="fas fa-trash"></i>
                        删除
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function getCrawlerStatusText(status) {
    return {
        pending: '等待中',
        running: '抓取中',
        completed: '已完成',
        failed: '失败'
    }[status] || '未知';
}

function formatCrawlerDateTime(value) {
    if (!value) return '--';
    const parsed = new Date(String(value).replace(' ', 'T'));
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }
    return parsed.toLocaleString('zh-CN', { hour12: false });
}

async function saveCrawlerTask() {
    const sourceUrl = document.getElementById('crawler-task-source-url').value.trim();
    const name = document.getElementById('crawler-task-name').value.trim();
    const batchFromListing = document.getElementById('crawler-task-batch-from-listing').checked;
    const listingLimit = parseInt(document.getElementById('crawler-task-listing-limit').value || '10', 10);

    if (!batchFromListing && !name) {
        showToast('请输入任务名称', 'error');
        return;
    }
    if (!sourceUrl) {
        showToast('请输入抓取链接', 'error');
        return;
    }
    if (batchFromListing && (!Number.isFinite(listingLimit) || listingLimit < 1)) {
        showToast('请输入有效的最近抓取数量', 'error');
        return;
    }

    const saveButton = document.getElementById('btn-save-crawler-task');
    const originalHtml = saveButton.innerHTML;
    saveButton.disabled = true;
    saveButton.innerHTML = '<span class="loading"></span> 保存中';

    try {
        const res = await api.post('/api/crawler/tasks', {
            name,
            source_url: sourceUrl,
            title: document.getElementById('crawler-task-title').value.trim(),
            author: document.getElementById('crawler-task-author').value.trim(),
            description: document.getElementById('crawler-task-description').value.trim(),
            category_id: document.getElementById('crawler-task-category').value,
            site_rule_id: document.getElementById('crawler-task-site-rule').value,
            batch_from_listing: batchFromListing,
            listing_limit: listingLimit,
            tag_ids: getSelectedCrawlerTagIds(),
            start_immediately: document.getElementById('crawler-task-start-immediately').checked
        });

        if (!res.success) {
            throw new Error(res.message || '保存失败');
        }

        closeModal('crawler-task-modal');
        await Promise.all([loadCrawlerStats(), loadCrawlerTasks(), loadNovels(), loadStats()]);
        const successMessage = res.message || (
            document.getElementById('crawler-task-start-immediately').checked ? '任务已创建并开始抓取' : '任务已创建'
        );
        showToast(successMessage, 'success');
    } catch (err) {
        console.error('保存爬虫任务失败:', err);
        showToast(err.message || '保存失败', 'error');
    } finally {
        saveButton.disabled = false;
        saveButton.innerHTML = originalHtml;
    }
}

async function startCrawlerTask(taskId) {
    try {
        const res = await api.post(`/api/crawler/tasks/${taskId}/run`, {});
        if (!res.success) {
            throw new Error(res.message || '启动失败');
        }

        await Promise.all([loadCrawlerStats(), loadCrawlerTasks()]);
        showToast('爬虫任务已启动', 'success');
    } catch (err) {
        console.error('启动爬虫任务失败:', err);
        showToast(err.message || '启动失败', 'error');
    }
}

async function deleteCrawlerTask(taskId) {
    if (!confirm('确定要删除这个爬虫任务吗？')) return;

    try {
        const res = await api.delete(`/api/crawler/tasks/${taskId}`);
        if (!res.success) {
            throw new Error(res.message || '删除失败');
        }

        await Promise.all([loadCrawlerStats(), loadCrawlerTasks()]);
        showToast('爬虫任务已删除', 'success');
    } catch (err) {
        console.error('删除爬虫任务失败:', err);
        showToast(err.message || '删除失败', 'error');
    }
}

function startCrawlerAutoRefresh() {
    stopCrawlerAutoRefresh();
    crawlerState.refreshTimer = setInterval(() => {
        if (state.currentView === 'crawler') {
            loadCrawlerStats();
            loadCrawlerTasks();
        }
    }, 4000);
}

function stopCrawlerAutoRefresh() {
    if (crawlerState.refreshTimer) {
        clearInterval(crawlerState.refreshTimer);
        crawlerState.refreshTimer = null;
    }
}

// ==================== AI 配置功能 ====================
