// ?????????????????

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
