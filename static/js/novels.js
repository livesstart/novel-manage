async function loadStats() {
    try {
        const res = await api.get('/api/stats');
        if (res.success) {
            document.getElementById('stat-total').textContent = res.data.total_novels;
            document.getElementById('stat-finished').textContent = res.data.finished_novels;
            document.getElementById('stat-categories').textContent = res.data.total_categories;
            document.getElementById('stat-tags').textContent = res.data.total_tags;
        }
    } catch (err) {
        console.error('加载统计数据失败:', err);
    }
}

// 加载小说列表
async function loadNovels(filters = {}) {
    try {
        const params = new URLSearchParams();
        if (filters.keyword) params.append('keyword', filters.keyword);
        if (filters.category_id) params.append('category_id', filters.category_id);
        if (filters.status !== undefined && filters.status !== '') params.append('status', filters.status);
        if (filters.untagged_only) params.append('untagged_only', '1');

        // ????????
        if (!filters.untagged_only && filters.tag_ids && filters.tag_ids.length > 0) {
            filters.tag_ids.forEach(tagId => params.append('tag_ids', tagId));
        }

        const res = await api.get(`/api/novels?${params}`);
        if (res.success) {
            state.novels = res.data;
            const currentNovelIds = new Set(res.data.map(novel => novel.id));
            state.expandedNovelTagIds = new Set([...state.expandedNovelTagIds].filter(id => currentNovelIds.has(id)));
            renderNovels();
        }
    } catch (err) {
        console.error('加载小说失败:', err);
        showToast('加载小说失败', 'error');
    }
}

// 加载分类列表
async function loadCategories() {
    try {
        const res = await api.get('/api/categories');
        if (res.success) {
            state.categories = res.data;
            renderCategories();
            updateCategorySelects();
        }
    } catch (err) {
        console.error('加载分类失败:', err);
    }
}

// 加载标签列表
async function loadTags() {
    try {
        const res = await api.get('/api/tags');
        if (res.success) {
            state.tags = res.data;
            renderTags();
            updateTagSelectors();
        }
    } catch (err) {
        console.error('加载标签失败:', err);
    }
}

// 渲染小说列表
function renderNovelTags(novel) {
    const tags = Array.isArray(novel.tags) ? novel.tags : [];
    if (!tags.length) {
        return '';
    }

    const isExpanded = state.expandedNovelTagIds.has(novel.id);
    const visibleTags = isExpanded ? tags : tags.slice(0, NOVEL_TAG_VISIBLE_COUNT);
    const hiddenCount = Math.max(tags.length - visibleTags.length, 0);
    const hasOverflow = tags.length > NOVEL_TAG_VISIBLE_COUNT;
    const allTagNames = tags.map(tag => tag.name).filter(Boolean).join(', ');

    return `
        <div class="novel-tags ${isExpanded ? 'expanded' : 'collapsed'}" title="${escapeHtml(allTagNames)}">
            ${visibleTags.map(tag => `
                <span class="novel-tag" style="background-color: ${tag.color}20; color: ${tag.color}" title="${escapeHtml(tag.name)}">
                    ${escapeHtml(tag.name)}
                </span>
            `).join('')}
            ${!isExpanded && hiddenCount > 0 ? `
                <button type="button" class="novel-tag-toggle" onclick="toggleNovelTagList(${novel.id})">+${hiddenCount}</button>
            ` : ''}
            ${isExpanded && hasOverflow ? `
                <button type="button" class="novel-tag-toggle is-collapse" onclick="toggleNovelTagList(${novel.id})">&#x6536;&#x8d77;</button>
            ` : ''}
        </div>
    `;
}

function toggleNovelTagList(novelId) {
    if (state.expandedNovelTagIds.has(novelId)) {
        state.expandedNovelTagIds.delete(novelId);
    } else {
        state.expandedNovelTagIds.add(novelId);
    }

    renderNovels();
}

function renderNovels() {
    const container = document.getElementById('novels-grid');

    if (state.novels.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <i class="fas fa-book-open"></i>
                <h3>还没有小说</h3>
                <p>点击"添加小说"按钮开始管理你的小说库</p>
            </div>
        `;
        return;
    }

    // 更新小说数量显示
    document.getElementById('novels-count').textContent = `${state.novels.length} 本小说`;

    // 更新全选复选框状态
    const allSelected = state.novels.length > 0 && state.novels.every(n => state.selectedNovels.has(n.id));
    document.getElementById('select-all-novels-main').checked = allSelected;

    container.innerHTML = state.novels.map(novel => {
        const isSelected = state.selectedNovels.has(novel.id);
        return `
        <div class="novel-card ${isSelected ? 'selected' : ''}" data-id="${novel.id}">
            <label class="novel-select-control" aria-label="批量选择小说" title="批量选择">
                <input type="checkbox" class="novel-select-checkbox"
                       ${isSelected ? 'checked' : ''}
                       onchange="toggleNovelSelection(${novel.id}, this.checked)">
                <span class="novel-select-indicator" aria-hidden="true"></span>
            </label>
            <div class="novel-header">
                <div>
                    <div class="novel-title">${escapeHtml(novel.title)}</div>
                    <div class="novel-author">${novel.author ? escapeHtml(novel.author) : '未知作者'}</div>
                </div>
                <span class="novel-status status-${novel.status}">${getStatusText(novel.status)}</span>
            </div>
            ${novel.category_name ? `<span class="novel-category">${escapeHtml(novel.category_name)}</span>` : ''}
            ${novel.description ? `<div class="novel-description">${escapeHtml(novel.description)}</div>` : ''}
            ${renderNovelTags(novel)}
            <div class="novel-actions">
                <button class="btn btn-sm btn-secondary" onclick="openNovelFile(${novel.id})">
                    <i class="fas fa-book-open"></i> 阅读
                </button>
                <button class="btn btn-sm btn-secondary" onclick="downloadNovel(${novel.id})">
                    <i class="fas fa-download"></i> 下载
                </button>
                <button class="btn btn-sm btn-primary" onclick="editNovel(${novel.id})">
                    <i class="fas fa-edit"></i> 编辑
                </button>
                <button class="btn btn-sm btn-danger" onclick="deleteNovel(${novel.id})">
                    <i class="fas fa-trash"></i> 删除
                </button>
            </div>
        </div>
    `}).join('');
}

// 渲染分类列表
function renderCategories() {
    const container = document.getElementById('categories-list');

    if (state.categories.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <i class="fas fa-folder"></i>
                <h3>还没有分类</h3>
                <p>点击"新建分类"按钮创建分类</p>
            </div>
        `;
        return;
    }

    container.innerHTML = state.categories.map(cat => `
        <div class="category-card">
            <div class="category-header">
                <span class="category-name">${escapeHtml(cat.name)}</span>
            </div>
            <div class="category-count">${cat.novel_count} 本小说</div>
            ${cat.description ? `<div class="category-description">${escapeHtml(cat.description)}</div>` : ''}
            <div class="category-actions">
                <button class="btn btn-sm btn-primary" onclick="editCategory(${cat.id})">
                    <i class="fas fa-edit"></i> 编辑
                </button>
                <button class="btn btn-sm btn-danger" onclick="deleteCategory(${cat.id})">
                    <i class="fas fa-trash"></i> 删除
                </button>
            </div>
        </div>
    `).join('');
}

// 渲染标签列表
function renderTags() {
    const container = document.getElementById('tags-list');

    if (state.tags.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="width: 100%;">
                <i class="fas fa-tags"></i>
                <h3>还没有标签</h3>
                <p>点击"新建标签"按钮创建标签</p>
            </div>
        `;
        return;
    }

    container.innerHTML = state.tags.map(tag => `
        <div class="tag-card">
            <div class="tag-color-dot" style="background-color: ${tag.color}"></div>
            <div class="tag-info">
                <div class="tag-name">${escapeHtml(tag.name)}</div>
                <div class="tag-count">${tag.novel_count} 本小说</div>
            </div>
            <div class="tag-actions">
                <button class="btn btn-sm btn-primary" onclick="editTag(${tag.id})">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-sm btn-danger" onclick="deleteTag(${tag.id})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

// 更新分类选择器
function updateCategorySelects() {
    const filterSelect = document.getElementById('filter-category');
    const novelSelect = document.getElementById('novel-category');
    const crawlerSelect = document.getElementById('crawler-task-category');

    const options = state.categories.map(cat =>
        `<option value="${cat.id}">${escapeHtml(cat.name)}</option>`
    ).join('');

    filterSelect.innerHTML = '<option value="">全部分类</option>' + options;
    novelSelect.innerHTML = '<option value="">无分类</option>' + options;
    if (crawlerSelect) {
        crawlerSelect.innerHTML = '<option value="">未分类</option>' + options;
    }
}

// 更新标签选择器
function updateTagSelectors() {
    const filterContainer = document.getElementById('filter-tags');
    const searchInput = document.getElementById('filter-tag-search');
    const summaryEl = document.getElementById('filter-tags-summary');
    const toggleBtn = document.getElementById('filter-tags-toggle');
    const clearBtn = document.getElementById('filter-tags-clear');
    const untaggedOnly = document.getElementById('filter-untagged-only')?.checked;
    const query = (state.filterTagQuery || '').trim().toLowerCase();
    const selectedCount = state.selectedTags.size;

    if (searchInput) {
        searchInput.value = state.filterTagQuery;
        searchInput.disabled = Boolean(untaggedOnly);
    }

    filterContainer.classList.toggle('disabled', Boolean(untaggedOnly));
    filterContainer.classList.remove('is-collapsed', 'is-searching');

    if (untaggedOnly) {
        filterContainer.innerHTML = '<span class="filter-tags-empty">\u5df2\u542f\u7528\u201c\u4ec5\u770b\u65e0\u6807\u7b7e\u201d\uff0c\u6807\u7b7e\u7b5b\u9009\u6682\u65f6\u505c\u7528</span>';
        if (summaryEl) {
            summaryEl.textContent = `\u5df2\u9009 ${selectedCount} \u4e2a\u6807\u7b7e`;
        }
        if (toggleBtn) {
            toggleBtn.hidden = true;
            clearBtn.hidden = true;
        }
    } else {
        const matchedTags = state.tags.filter(tag => !query || String(tag.name || '').toLowerCase().includes(query));
        const orderedTags = [
            ...matchedTags.filter(tag => state.selectedTags.has(tag.id)),
            ...matchedTags.filter(tag => !state.selectedTags.has(tag.id))
        ];
        const shouldCollapse = !query && !state.filterTagsExpanded && orderedTags.length > FILTER_TAG_COLLAPSED_LIMIT;
        const visibleTags = shouldCollapse ? orderedTags.slice(0, FILTER_TAG_COLLAPSED_LIMIT) : orderedTags;
        const hiddenCount = Math.max(orderedTags.length - visibleTags.length, 0);

        filterContainer.classList.toggle('is-collapsed', shouldCollapse);
        filterContainer.classList.toggle('is-searching', Boolean(query));

        if (visibleTags.length === 0) {
            filterContainer.innerHTML = `<span class="filter-tags-empty">${query ? '\u6ca1\u6709\u5339\u914d\u7684\u6807\u7b7e' : '\u6682\u65e0\u6807\u7b7e'}</span>`;
        } else {
            filterContainer.innerHTML = visibleTags.map(tag => `
                <span class="filter-tag ${state.selectedTags.has(tag.id) ? 'active' : ''}"
                      data-id="${tag.id}"
                      style="background-color: ${tag.color}20; color: ${tag.color}"
                      onclick="toggleFilterTag(${tag.id})"
                      title="${escapeHtml(tag.name)}">
                    ${escapeHtml(tag.name)}
                </span>
            `).join('');
        }

        if (summaryEl) {
            summaryEl.textContent = query
                ? `\u5339\u914d ${matchedTags.length} \u4e2a\u6807\u7b7e\uff0c\u5df2\u9009 ${selectedCount} \u4e2a`
                : `\u5171 ${state.tags.length} \u4e2a\u6807\u7b7e\uff0c\u5df2\u9009 ${selectedCount} \u4e2a`;
        }

        if (clearBtn) {
            clearBtn.hidden = selectedCount === 0;
        }

        if (toggleBtn) {
            if (query) {
                toggleBtn.hidden = false;
                toggleBtn.textContent = '\u6e05\u7a7a\u641c\u7d22';
            } else if (orderedTags.length > FILTER_TAG_COLLAPSED_LIMIT || state.filterTagsExpanded) {
                toggleBtn.hidden = false;
                toggleBtn.textContent = shouldCollapse ? `\u5c55\u5f00\u66f4\u591a\uff08+${hiddenCount}\uff09` : '\u6536\u8d77\u6807\u7b7e';
            } else {
                toggleBtn.hidden = true;
            }
        }
    }

    // ???????????
    const selectorContainer = document.getElementById('novel-tag-selector');
    selectorContainer.innerHTML = state.tags.map(tag => `
        <span class="tag-option"
              data-id="${tag.id}"
              style="background-color: ${tag.color}20; color: ${tag.color}"
              onclick="toggleNovelTag(this, ${tag.id})">
            ${escapeHtml(tag.name)}
        </span>
    `).join('');

    const crawlerTagSelector = document.getElementById('crawler-task-tag-selector');
    if (crawlerTagSelector) {
        renderCrawlerTagSelector();
    }
}

function toggleFilterTagsPanel() {
    if (document.getElementById('filter-untagged-only')?.checked) {
        return;
    }

    if (state.filterTagQuery) {
        state.filterTagQuery = '';
    } else {
        state.filterTagsExpanded = !state.filterTagsExpanded;
    }

    updateTagSelectors();
}

function clearSelectedFilterTags() {
    if (state.selectedTags.size === 0) {
        return;
    }

    state.selectedTags.clear();
    updateTagSelectors();
    applyFilters();
}

function toggleFilterTag(tagId) {
    if (document.getElementById('filter-untagged-only')?.checked) {
        return;
    }

    if (state.selectedTags.has(tagId)) {
        state.selectedTags.delete(tagId);
    } else {
        state.selectedTags.add(tagId);
    }
    updateTagSelectors();
    applyFilters();
}

// 切换小说标签选择
function toggleNovelTag(element, tagId) {
    element.classList.toggle('selected');
}

function getSelectedNovelTagIds() {
    return Array.from(document.querySelectorAll('#novel-tag-selector .tag-option.selected'))
        .map(el => parseInt(el.dataset.id, 10))
        .filter(Number.isInteger);
}

function setNovelTagSelection(tagIds = []) {
    const selectedTagIds = new Set((tagIds || []).map(tagId => parseInt(tagId, 10)).filter(Number.isInteger));
    document.querySelectorAll('#novel-tag-selector .tag-option').forEach(el => {
        const tagId = parseInt(el.dataset.id, 10);
        el.classList.toggle('selected', selectedTagIds.has(tagId));
    });
}

async function readLocalNovelExcerpt() {
    const file = document.getElementById('file-input').files[0];
    if (!file) {
        return '';
    }

    const lowerName = file.name.toLowerCase();
    const canReadAsText = lowerName.endsWith('.txt') || file.type.startsWith('text/');
    if (!canReadAsText) {
        return '';
    }

    try {
        const blob = file.slice(0, 16000);
        const text = await blob.text();
        return text.slice(0, 4000).trim();
    } catch (err) {
        console.warn('读取本地小说片段失败:', err);
        return '';
    }
}

function formatAISafetyFeedback(details) {
    const feedback = details?.safety_feedback;
    if (!feedback) {
        return '';
    }

    if (feedback.summary) {
        return feedback.summary;
    }

    const parts = [];
    if (feedback.block_reason) {
        parts.push(`提示词拦截：${feedback.block_reason}`);
    }
    if (feedback.finish_reason && feedback.finish_reason !== 'STOP') {
        parts.push(`结束原因：${feedback.finish_reason}`);
    }
    return parts.join('；');
}

function buildAIErrorMessage(res, fallback = 'AI 生成失败') {
    const baseMessage = res?.details?.display_message || res?.message || fallback;
    const safetyMessage = formatAISafetyFeedback(res?.details);

    if (!safetyMessage || baseMessage.includes(safetyMessage)) {
        return baseMessage;
    }

    return `${baseMessage}；${safetyMessage}`;
}

async function generateNovelMetadataWithAI() {
    const title = document.getElementById('novel-title').value.trim();
    const description = document.getElementById('novel-description').value.trim();
    const rawFilePath = document.getElementById('novel-file-path').value.trim();
    const filePath = rawFilePath.startsWith('待上传：') ? '' : rawFilePath;

    if (!title && !description && !filePath && !document.getElementById('file-input').files[0]) {
        showToast('请先填写书名，或选择一个可分析的小说文件', 'error');
        return;
    }

    const actionButton = document.getElementById('btn-ai-generate-novel-meta');
    const originalHtml = actionButton.innerHTML;
    actionButton.disabled = true;
    actionButton.innerHTML = '<span class="loading"></span> AI 生成中';

    try {
        const selectedTagIds = getSelectedNovelTagIds();
        const localExcerpt = await readLocalNovelExcerpt();
        const res = await api.post('/api/ai/novels/metadata', {
            novel_id: state.editingNovel ? state.editingNovel.id : null,
            title,
            author: document.getElementById('novel-author').value.trim(),
            description,
            file_path: filePath,
            category_id: document.getElementById('novel-category').value || null,
            tag_ids: selectedTagIds,
            content_excerpt: localExcerpt
        });

        if (!res.success) {
            showToast(buildAIErrorMessage(res), 'error');
            return;
        }

        const generatedSummary = res.data.summary || '';
        const generatedTagIds = (res.data.tags || []).map(tag => tag.id);
        const mergedTagIds = Array.from(new Set([...selectedTagIds, ...generatedTagIds]));

        if (generatedSummary) {
            document.getElementById('novel-description').value = generatedSummary;
        }

        await loadTags();
        setNovelTagSelection(mergedTagIds);

        const tagCount = generatedTagIds.length;
        showToast(`AI 已补全简介，并匹配 ${tagCount} 个标签`, 'success');
    } catch (err) {
        console.error('AI 生成小说元数据失败:', err);
        showToast('AI 生成失败: ' + err.message, 'error');
    } finally {
        actionButton.disabled = false;
        actionButton.innerHTML = originalHtml;
    }
}

// 应用筛选
function applyFilters() {
    const keyword = document.getElementById('search-input').value;
    const categoryId = document.getElementById('filter-category').value;
    const status = document.getElementById('filter-status').value;
    const untaggedOnly = document.getElementById('filter-untagged-only').checked;

    loadNovels({
        keyword,
        category_id: categoryId,
        status: status,
        tag_ids: untaggedOnly ? [] : Array.from(state.selectedTags),
        untagged_only: untaggedOnly
    });
}

// 打开小说阅读器
async function openNovelFile(novelId) {
    openReader(novelId);
}

// ==================== 阅读器功能 ====================

async function downloadNovel(novelId) {
    const novel = state.novels.find(n => n.id === novelId);
    if (!novel) {
        showToast('小说不存在', 'error');
        return;
    }

    if (!novel.file_path) {
        showToast('该小说未设置文件路径', 'error');
        return;
    }

    try {
        // 显示下载中提示
        showToast('正在准备下载...', 'success');

        // 调用后端下载API
        const response = await fetch(`/api/novels/${novelId}/download`);

        if (!response.ok) {
            const res = await response.json();
            showToast(res.message || '下载失败', 'error');
            return;
        }

        // 获取文件名
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = novel.title + '.txt';
        if (contentDisposition) {
            const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(contentDisposition);
            if (matches && matches[1]) {
                filename = matches[1].replace(/['"]/g, '');
            }
        }

        // 创建下载链接
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('下载已开始', 'success');
    } catch (err) {
        console.error('下载失败:', err);
        showToast('下载失败: ' + err.message, 'error');
    }
}

// 添加小说
async function uploadSelectedNovelFile() {
    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];
    if (!file) {
        return null;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('relative_path', file.name);

    const res = await api.postForm('/api/files/upload', formData);
    if (!res.success) {
        throw new Error(res.message || '文件上传失败');
    }

    return res.data.file_path;
}

async function saveNovel() {
    const title = document.getElementById('novel-title').value.trim();
    if (!title) {
        showToast('请输入小说名称', 'error');
        return;
    }

    const data = {
        title,
        author: document.getElementById('novel-author').value.trim(),
        description: document.getElementById('novel-description').value.trim(),
        file_path: document.getElementById('novel-file-path').value.trim(),
        category_id: document.getElementById('novel-category').value || null,
        status: parseInt(document.getElementById('novel-status').value),
        tag_ids: getSelectedNovelTagIds()
    };

    try {
        const uploadedPath = await uploadSelectedNovelFile();
        if (uploadedPath) {
            data.file_path = uploadedPath;
        }

        let res;
        if (state.editingNovel) {
            res = await api.put(`/api/novels/${state.editingNovel.id}`, data);
        } else {
            res = await api.post('/api/novels', data);
        }

        if (res.success) {
            document.getElementById('file-input').value = '';
            closeModal('novel-modal');
            await Promise.all([loadNovels(), loadStats()]);
            showToast(state.editingNovel ? '小说已更新' : '小说已添加', 'success');
        } else {
            showToast(res.message || '操作失败', 'error');
        }
    } catch (err) {
        console.error('保存小说失败:', err);
        showToast('保存失败: ' + err.message, 'error');
    }
}

function editNovel(novelId) {
    const novel = state.novels.find(n => n.id === novelId);
    if (!novel) return;

    state.editingNovel = novel;

    document.getElementById('novel-modal-title').textContent = '编辑小说';
    document.getElementById('novel-id').value = novel.id;
    document.getElementById('novel-title').value = novel.title;
    document.getElementById('novel-author').value = novel.author || '';
    document.getElementById('novel-description').value = novel.description || '';
    document.getElementById('novel-file-path').value = novel.file_path || '';
    document.getElementById('novel-category').value = novel.category_id || '';
    document.getElementById('novel-status').value = novel.status;
    document.getElementById('file-input').value = '';

    setNovelTagSelection((novel.tags || []).map(tag => tag.id));

    openModal('novel-modal');
}

async function deleteNovel(novelId) {
    if (!confirm('确定要删除这本小说及其对应文件吗？此操作不可恢复。')) return;

    try {
        const res = await api.delete(`/api/novels/${novelId}`);
        if (res.success) {
            await Promise.all([loadNovels(), loadStats()]);
            const deletedFiles = res.data?.deleted_files || 0;
            showToast(
                deletedFiles > 0
                    ? `小说已删除，并删除 ${deletedFiles} 个文件`
                    : '小说记录已删除，对应文件不存在或已被其他记录共用',
                'success'
            );
        } else {
            showToast(res.message || '未知作者', 'error');
        }
    } catch (err) {
        console.error('删除小说失败:', err);
        showToast('删除失败: ' + err.message, 'error');
    }
}

// 保存分类
async function saveCategory() {
    const name = document.getElementById('category-name').value.trim();
    if (!name) {
        showToast('请输入分类名称', 'error');
        return;
    }

    const data = {
        name,
        description: document.getElementById('category-description').value.trim()
    };

    try {
        let res;
        if (state.editingCategory) {
            res = await api.put(`/api/categories/${state.editingCategory.id}`, data);
        } else {
            res = await api.post('/api/categories', data);
        }

        if (res.success) {
            closeModal('category-modal');
            await Promise.all([loadCategories(), loadStats()]);
            showToast(state.editingCategory ? '分类已更新' : '分类已创建', 'success');
        } else {
            showToast(res.message || '操作失败', 'error');
        }
    } catch (err) {
        console.error('保存分类失败:', err);
        showToast('保存失败', 'error');
    }
}

// 编辑分类
function editCategory(categoryId) {
    const category = state.categories.find(c => c.id === categoryId);
    if (!category) return;

    state.editingCategory = category;

    document.getElementById('category-modal-title').textContent = '编辑分类';
    document.getElementById('category-id').value = category.id;
    document.getElementById('category-name').value = category.name;
    document.getElementById('category-description').value = category.description || '';

    openModal('category-modal');
}

// 删除分类
async function deleteCategory(categoryId) {
    if (!confirm('确定要删除这个分类吗？该分类下的小说将变为无分类。')) return;

    try {
        const res = await api.delete(`/api/categories/${categoryId}`);
        if (res.success) {
            await Promise.all([loadCategories(), loadNovels(), loadStats()]);
            showToast('分类已删除', 'success');
        } else {
            showToast(res.message || '删除失败', 'error');
        }
    } catch (err) {
        console.error('删除分类失败:', err);
        showToast('删除失败', 'error');
    }
}

// 保存标签
async function saveTag() {
    const name = document.getElementById('tag-name').value.trim();
    if (!name) {
        showToast('请输入标签名称', 'error');
        return;
    }

    const data = {
        name,
        color: document.getElementById('tag-color').value
    };

    try {
        let res;
        if (state.editingTag) {
            res = await api.put(`/api/tags/${state.editingTag.id}`, data);
        } else {
            res = await api.post('/api/tags', data);
        }

        if (res.success) {
            closeModal('tag-modal');
            await Promise.all([loadTags(), loadStats()]);
            showToast(state.editingTag ? '标签已更新' : '标签已创建', 'success');
        } else {
            showToast(res.message || '操作失败', 'error');
        }
    } catch (err) {
        console.error('保存标签失败:', err);
        showToast('保存失败', 'error');
    }
}

// 编辑标签
function editTag(tagId) {
    const tag = state.tags.find(t => t.id === tagId);
    if (!tag) return;

    state.editingTag = tag;

    document.getElementById('tag-modal-title').textContent = '编辑标签';
    document.getElementById('tag-id').value = tag.id;
    document.getElementById('tag-name').value = tag.name;
    document.getElementById('tag-color').value = tag.color;
    document.querySelector('.color-value').textContent = tag.color;

    openModal('tag-modal');
}

// 删除标签
async function deleteTag(tagId) {
    if (!confirm('确定要删除这个标签吗？')) return;

    try {
        const res = await api.delete(`/api/tags/${tagId}`);
        if (res.success) {
            await Promise.all([loadTags(), loadNovels(), loadStats()]);
            showToast('标签已删除', 'success');
        } else {
            showToast(res.message || '删除失败', 'error');
        }
    } catch (err) {
        console.error('删除标签失败:', err);
        showToast('删除失败', 'error');
    }
}

// 弹窗控制

function resetNovelModal() {
    state.editingNovel = null;
    document.getElementById('novel-modal-title').textContent = '添加小说';
    document.getElementById('novel-form').reset();
    document.getElementById('novel-id').value = '';
    document.getElementById('file-input').value = '';
    setNovelTagSelection([]);
}

function resetCategoryModal() {
    state.editingCategory = null;
    document.getElementById('category-modal-title').textContent = '新建分类';
    document.getElementById('category-form').reset();
    document.getElementById('category-id').value = '';
}

function resetTagModal() {
    state.editingTag = null;
    document.getElementById('tag-modal-title').textContent = '新建标签';
    document.getElementById('tag-form').reset();
    document.getElementById('tag-id').value = '';
    document.getElementById('tag-color').value = '#3498db';
    document.querySelector('.color-value').textContent = '#3498db';
}

// 视图切换
