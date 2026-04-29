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
            hideFullTextSearchResults();
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
                <button class="btn btn-sm btn-secondary" onclick="openNovelDetail(${novel.id})">
                    <i class="fas fa-circle-info"></i> 详情
                </button>
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

function hideFullTextSearchResults() {
    const resultsContainer = document.getElementById('full-text-search-results');
    const novelsGrid = document.getElementById('novels-grid');
    if (resultsContainer) {
        resultsContainer.classList.add('is-hidden');
        resultsContainer.innerHTML = '';
    }
    if (novelsGrid) {
        novelsGrid.classList.remove('is-full-text-mode');
    }
}

function renderFullTextSearchResults(query, results) {
    const resultsContainer = document.getElementById('full-text-search-results');
    const novelsGrid = document.getElementById('novels-grid');
    if (!resultsContainer || !novelsGrid) return;

    novelsGrid.classList.add('is-full-text-mode');
    resultsContainer.classList.remove('is-hidden');
    document.getElementById('novels-count').textContent = `全文命中 ${results.length} 条`;

    if (results.length === 0) {
        resultsContainer.innerHTML = `
            <div class="full-text-search-empty">
                <i class="fas fa-magnifying-glass"></i>
                <h3>没有找到正文命中</h3>
                <p>换个关键词试试，当前只索引可在线阅读的 TXT 文件。</p>
            </div>
        `;
        return;
    }

    resultsContainer.innerHTML = `
        <div class="full-text-search-summary">
            <span>关键词</span>
            <strong>${escapeHtml(query)}</strong>
        </div>
        <div class="full-text-search-list">
            ${results.map(result => `
                <article class="full-text-search-result">
                    <div class="full-text-hit-main">
                        <div class="full-text-hit-title">${escapeHtml(result.title)}</div>
                        <div class="full-text-hit-meta">
                            <span>${escapeHtml(result.author || '未知作者')}</span>
                            <span>第 ${Number(result.chapter_index) + 1} 章</span>
                            <span>${escapeHtml(result.chapter_title || '未命名章节')}</span>
                        </div>
                        <p class="full-text-hit-snippet">${escapeHtml(result.snippet)}</p>
                    </div>
                    <div class="full-text-hit-actions">
                        <button class="btn btn-sm btn-secondary" onclick="openNovelDetail(${result.novel_id})">
                            <i class="fas fa-circle-info"></i> 详情
                        </button>
                        <button class="btn btn-sm btn-primary" onclick="openFullTextSearchResult(${result.novel_id}, ${result.chapter_index})">
                            <i class="fas fa-book-open"></i> 打开章节
                        </button>
                    </div>
                </article>
            `).join('')}
        </div>
    `;
}

async function searchFullTextNovels(query) {
    const keyword = (query || '').trim();
    if (!keyword) {
        hideFullTextSearchResults();
        return;
    }

    const resultsContainer = document.getElementById('full-text-search-results');
    const novelsGrid = document.getElementById('novels-grid');
    if (resultsContainer && novelsGrid) {
        novelsGrid.classList.add('is-full-text-mode');
        resultsContainer.classList.remove('is-hidden');
        resultsContainer.innerHTML = `
            <div class="full-text-search-loading">
                <i class="fas fa-spinner fa-spin"></i>
                <span>正在搜索正文...</span>
            </div>
        `;
    }

    try {
        const params = new URLSearchParams({ q: keyword });
        const res = await api.get(`/api/search/fulltext?${params}`);
        const currentKeyword = document.getElementById('search-input').value.trim();
        const fullTextSearchEnabled = document.getElementById('full-text-search-toggle')?.checked;
        if (!fullTextSearchEnabled || currentKeyword !== keyword) {
            return;
        }

        if (!res.success) {
            showToast(res.message || '全文搜索失败', 'error');
            renderFullTextSearchResults(keyword, []);
            return;
        }

        state.fullTextResults = res.data.results || [];
        renderFullTextSearchResults(keyword, state.fullTextResults);
    } catch (err) {
        const currentKeyword = document.getElementById('search-input').value.trim();
        const fullTextSearchEnabled = document.getElementById('full-text-search-toggle')?.checked;
        if (!fullTextSearchEnabled || currentKeyword !== keyword) {
            return;
        }

        console.error('全文搜索失败:', err);
        showToast('全文搜索失败', 'error');
        renderFullTextSearchResults(keyword, []);
    }
}

async function openFullTextSearchResult(novelId, chapterIndex) {
    try {
        await openReader(novelId);
        await loadChapter(Number(chapterIndex));
    } catch (err) {
        console.error('打开全文搜索命中章节失败:', err);
        showToast('打开章节失败', 'error');
    }
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
    const keyword = document.getElementById('search-input').value.trim();
    const fullTextSearchEnabled = document.getElementById('full-text-search-toggle')?.checked;
    if (fullTextSearchEnabled && keyword) {
        searchFullTextNovels(keyword);
        return;
    }

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

function formatFileSize(bytes) {
    if (!Number.isFinite(Number(bytes))) return '--';

    const size = Number(bytes);
    const units = ['B', 'KB', 'MB', 'GB'];
    let value = size;
    let unitIndex = 0;

    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024;
        unitIndex += 1;
    }

    const digits = unitIndex === 0 ? 0 : 1;
    return `${value.toFixed(digits)} ${units[unitIndex]}`;
}

function formatDateTime(value) {
    if (!value) return '未记录';

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);

    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '--';
    return number.toLocaleString('zh-CN');
}

function formatConfidence(value) {
    const number = Number(value);
    if (!Number.isFinite(number) || number <= 0) return '--';
    return `${Math.round(Math.max(0, Math.min(number, 1)) * 100)}%`;
}

function renderNovelDetailTags(tags = []) {
    const container = document.getElementById('novel-detail-tags');
    if (!Array.isArray(tags) || tags.length === 0) {
        container.innerHTML = '<span class="novel-detail-empty-tag">无标签</span>';
        return;
    }

    container.innerHTML = tags.map(tag => `
        <span class="novel-tag" style="background-color: ${tag.color}20; color: ${tag.color}">
            ${escapeHtml(tag.name)}
        </span>
    `).join('');
}

function resetNovelCharacterAnalysis() {
    state.detailCharacterAnalysis = null;
    document.getElementById('novel-character-status').textContent = '尚未分析';
    document.getElementById('novel-character-status').className = '';
    document.getElementById('novel-character-list').innerHTML = '<div class="novel-character-empty">暂无角色数据</div>';
    document.getElementById('novel-character-graph').innerHTML = '<div class="novel-character-empty">分析后会生成关系图</div>';
    document.getElementById('novel-character-relations').innerHTML = '';
}

function renderCharacterBadges(items = []) {
    if (!Array.isArray(items) || items.length === 0) return '';
    return `
        <div class="novel-character-badges">
            ${items.map(item => `<span>${escapeHtml(item)}</span>`).join('')}
        </div>
    `;
}

function renderCharacterRelationshipGraph(characters = [], relations = []) {
    const graph = document.getElementById('novel-character-graph');
    if (!Array.isArray(characters) || characters.length === 0) {
        graph.innerHTML = '<div class="novel-character-empty">暂无角色数据</div>';
        return;
    }

    const width = 520;
    const height = 320;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = characters.length === 1 ? 0 : 112;
    const nodePositions = new Map();

    characters.forEach((character, index) => {
        const angle = characters.length === 1 ? 0 : (Math.PI * 2 * index) / characters.length - Math.PI / 2;
        nodePositions.set(character.id, {
            x: centerX + Math.cos(angle) * radius,
            y: centerY + Math.sin(angle) * radius
        });
    });

    const relationLines = (relations || [])
        .map(relation => {
            const source = nodePositions.get(relation.source_character_id);
            const target = nodePositions.get(relation.target_character_id);
            if (!source || !target) return '';
            const midX = (source.x + target.x) / 2;
            const midY = (source.y + target.y) / 2;
            return `
                <line x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" class="novel-relation-line"></line>
                <text x="${midX}" y="${midY - 6}" class="novel-relation-label">${escapeHtml(relation.relation_type || '相关')}</text>
            `;
        })
        .join('');

    const nodes = characters.map(character => {
        const position = nodePositions.get(character.id);
        const initials = String(character.name || '?').slice(0, 2);
        return `
            <g class="novel-character-node" transform="translate(${position.x}, ${position.y})">
                <circle r="34"></circle>
                <text class="novel-character-node-name" text-anchor="middle" y="5">${escapeHtml(initials)}</text>
                <text class="novel-character-node-role" text-anchor="middle" y="52">${escapeHtml(character.role_type || '角色')}</text>
            </g>
        `;
    }).join('');

    graph.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="角色关系谱">
            ${relationLines}
            ${nodes}
        </svg>
    `;
}

function renderNovelCharacterAnalysis(analysis) {
    state.detailCharacterAnalysis = analysis;
    const characters = Array.isArray(analysis?.characters) ? analysis.characters : [];
    const relations = Array.isArray(analysis?.relations) ? analysis.relations : [];
    const status = analysis?.analysis_status || 'empty';
    const statusEl = document.getElementById('novel-character-status');

    if (status === 'failed') {
        statusEl.textContent = analysis.error_message || '上次分析失败';
        statusEl.className = 'failed';
    } else if (characters.length > 0 || relations.length > 0) {
        statusEl.textContent = `已识别 ${characters.length} 个角色、${relations.length} 条关系`;
        statusEl.className = 'completed';
    } else {
        statusEl.textContent = '尚未分析';
        statusEl.className = '';
    }

    const list = document.getElementById('novel-character-list');
    if (characters.length === 0) {
        list.innerHTML = '<div class="novel-character-empty">暂无角色数据</div>';
    } else {
        list.innerHTML = characters.map(character => `
            <article class="novel-character-card">
                <div class="novel-character-card-head">
                    <strong>${escapeHtml(character.name)}</strong>
                    <span>${escapeHtml(character.role_type || '角色')}</span>
                </div>
                ${character.aliases?.length ? `<div class="novel-character-alias">别名：${escapeHtml(character.aliases.join('、'))}</div>` : ''}
                <p>${escapeHtml(character.description || '暂无说明')}</p>
                ${renderCharacterBadges(character.traits)}
                <div class="novel-character-evidence">${escapeHtml(character.evidence || '暂无证据片段')}</div>
                <div class="novel-character-confidence">可信度 ${formatConfidence(character.confidence)}</div>
            </article>
        `).join('');
    }

    renderCharacterRelationshipGraph(characters, relations);

    const relationList = document.getElementById('novel-character-relations');
    if (relations.length === 0) {
        relationList.innerHTML = '<div class="novel-character-empty compact">暂无关系数据</div>';
    } else {
        relationList.innerHTML = relations.map(relation => `
            <article class="novel-relation-card">
                <div class="novel-relation-card-title">
                    <strong>${escapeHtml(relation.source_name)}</strong>
                    <span>${escapeHtml(relation.relation_type || '相关')}</span>
                    <strong>${escapeHtml(relation.target_name)}</strong>
                </div>
                <p>${escapeHtml(relation.description || '暂无说明')}</p>
                <div class="novel-character-evidence">${escapeHtml(relation.evidence || '暂无证据片段')}</div>
                <div class="novel-character-confidence">可信度 ${formatConfidence(relation.confidence)}</div>
            </article>
        `).join('');
    }
}

async function loadNovelCharacterAnalysis(novelId) {
    try {
        const res = await api.get(`/api/novels/${novelId}/characters`);
        if (!res.success) {
            document.getElementById('novel-character-status').textContent = res.message || '角色数据加载失败';
            return;
        }
        renderNovelCharacterAnalysis(res.data);
    } catch (err) {
        console.warn('加载角色关系分析失败:', err);
        document.getElementById('novel-character-status').textContent = '角色数据加载失败';
    }
}

async function analyzeNovelCharactersWithAI(novelId) {
    const button = document.getElementById('btn-detail-analyze-characters');
    const originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="loading"></span> 分析中';
    document.getElementById('novel-character-status').textContent = 'AI 正在分析角色关系...';

    try {
        const res = await api.post(`/api/ai/novels/${novelId}/characters/analyze`, {});
        if (!res.success) {
            showToast(res.message || '角色分析失败', 'error');
            await loadNovelCharacterAnalysis(novelId);
            return;
        }

        renderNovelCharacterAnalysis(res.data);
        showToast(`已识别 ${res.data.character_count} 个角色、${res.data.relation_count} 条关系`, 'success');
    } catch (err) {
        console.error('AI 分析角色关系失败:', err);
        showToast('AI 分析角色关系失败: ' + err.message, 'error');
    } finally {
        button.disabled = false;
        button.innerHTML = originalHtml;
    }
}

function calculateNovelReadingPercent(readingProgress, chapterCount) {
    if (!readingProgress || !chapterCount) return 0;

    const chapterIndex = Number(readingProgress.chapter_index) || 0;
    const scrollPercent = Math.max(0, Math.min(Number(readingProgress.scroll_percent) || 0, 100));
    const percent = ((chapterIndex + scrollPercent / 100) / Math.max(chapterCount, 1)) * 100;
    return Math.max(0, Math.min(percent, 100));
}

function renderNovelDetail(novel) {
    state.detailNovel = novel;

    document.getElementById('novel-detail-title').textContent = novel.title || '未命名小说';
    document.getElementById('novel-detail-author').textContent = novel.author || '未知作者';
    document.getElementById('novel-detail-status').textContent = getStatusText(novel.status);
    document.getElementById('novel-detail-status').className = `novel-status status-${novel.status || 0}`;
    document.getElementById('novel-detail-category').textContent = novel.category_name || '未分类';
    document.getElementById('novel-detail-description').textContent = novel.description || '暂无简介';
    document.getElementById('novel-detail-file-path').textContent = novel.file_path || '未设置文件路径';
    document.getElementById('novel-detail-progress').textContent = '0%';
    document.getElementById('novel-detail-last-read').textContent = '未记录';
    document.getElementById('novel-detail-chapter-count').textContent = '--';
    document.getElementById('novel-detail-char-count').textContent = '--';
    document.getElementById('novel-detail-file-size').textContent = '--';
    document.getElementById('novel-detail-file-updated').textContent = '--';

    const fileStatus = document.getElementById('novel-detail-file-status');
    fileStatus.className = 'novel-detail-status-pill checking';
    fileStatus.textContent = '检查中';

    resetNovelCharacterAnalysis();
    renderNovelDetailTags(novel.tags);

    document.getElementById('btn-detail-read').onclick = () => openNovelFile(novel.id);
    document.getElementById('btn-detail-download').onclick = () => downloadNovel(novel.id);
    document.getElementById('btn-detail-edit').onclick = () => {
        closeModal('novel-detail-modal');
        editNovel(novel.id);
    };
    document.getElementById('btn-detail-check-file').onclick = () => loadNovelDetailFileInfo(novel.id);
    document.getElementById('btn-detail-analyze-characters').onclick = () => analyzeNovelCharactersWithAI(novel.id);
}

async function loadNovelDetailFileInfo(novelId) {
    const fileStatus = document.getElementById('novel-detail-file-status');
    fileStatus.className = 'novel-detail-status-pill checking';
    fileStatus.textContent = '检查中';

    try {
        const fileRes = await api.get(`/api/novels/${novelId}/check-file`);
        if (fileRes.success) {
            const fileInfo = fileRes.data;
            fileStatus.className = `novel-detail-status-pill ${fileInfo.file_found ? 'ok' : 'missing'}`;
            fileStatus.textContent = fileInfo.file_found
                ? (fileInfo.is_text_readable ? '文件正常' : '仅可下载')
                : '文件缺失';
            document.getElementById('novel-detail-file-path').textContent = fileInfo.actual_path || fileInfo.file_path_in_db || '未设置文件路径';
            document.getElementById('novel-detail-file-size').textContent = formatFileSize(fileInfo.file_size);
            document.getElementById('novel-detail-file-updated').textContent = formatDateTime(fileInfo.file_modified_at);
        } else {
            fileStatus.className = 'novel-detail-status-pill missing';
            fileStatus.textContent = fileRes.message || '检查失败';
        }
    } catch (err) {
        fileStatus.className = 'novel-detail-status-pill missing';
        fileStatus.textContent = '检查失败';
        console.error('检查小说文件失败:', err);
    }

    try {
        const readRes = await api.get(`/api/novels/${novelId}/read`);
        if (readRes.success) {
            const data = readRes.data;
            const chapterCount = data.chapters.length;
            const progressPercent = calculateNovelReadingPercent(data.reading_progress, chapterCount);

            document.getElementById('novel-detail-chapter-count').textContent = `${chapterCount} 章`;
            document.getElementById('novel-detail-char-count').textContent = formatNumber(data.total_chars);
            document.getElementById('novel-detail-progress').textContent = `${Math.round(progressPercent)}%`;
            document.getElementById('novel-detail-last-read').textContent = formatDateTime(data.reading_progress?.last_read_at);
        }
    } catch (err) {
        console.warn('读取小说章节统计失败:', err);
    }
}

async function openNovelDetail(novelId) {
    const cachedNovel = state.novels.find(novel => novel.id === novelId);
    if (cachedNovel) {
        renderNovelDetail(cachedNovel);
        openModal('novel-detail-modal');
        loadNovelDetailFileInfo(novelId);
        loadNovelCharacterAnalysis(novelId);
        return;
    }

    try {
        const res = await api.get(`/api/novels/${novelId}`);
        if (!res.success) {
            showToast(res.message || '加载小说详情失败', 'error');
            return;
        }

        renderNovelDetail(res.data);
        openModal('novel-detail-modal');
        loadNovelDetailFileInfo(novelId);
        loadNovelCharacterAnalysis(novelId);
    } catch (err) {
        console.error('加载小说详情失败:', err);
        showToast('加载小说详情失败: ' + err.message, 'error');
    }
}

// ==================== 阅读器功能 ====================

function stripContentDispositionQuotes(value) {
    const trimmed = (value || '').trim();
    if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
        return trimmed.slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, '\\');
    }
    return trimmed;
}

function decodeRfc5987FilenameValue(value) {
    const unquotedValue = stripContentDispositionQuotes(value);
    const encodedMatch = /^([^']*)'[^']*'(.*)$/.exec(unquotedValue);
    const encodedFilename = encodedMatch ? encodedMatch[2] : unquotedValue;

    try {
        return decodeURIComponent(encodedFilename);
    } catch (err) {
        console.warn('解析下载文件名失败:', err);
        return '';
    }
}

function parseDownloadFilename(contentDisposition, fallbackFilename) {
    const fallback = fallbackFilename || 'novel.txt';
    if (!contentDisposition) return fallback;

    const encodedFilenameMatch = /(?:^|;)\s*filename\*\s*=\s*([^;]+)/i.exec(contentDisposition);
    if (encodedFilenameMatch) {
        const decodedFilename = decodeRfc5987FilenameValue(encodedFilenameMatch[1]);
        if (decodedFilename) return decodedFilename;
    }

    const filenameMatch = /(?:^|;)\s*filename\s*=\s*("[^"]*"|[^;]+)/i.exec(contentDisposition);
    if (filenameMatch) {
        const filename = stripContentDispositionQuotes(filenameMatch[1]);
        if (filename) return filename;
    }

    return fallback;
}

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
        const filename = parseDownloadFilename(contentDisposition, novel.title + '.txt');

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
