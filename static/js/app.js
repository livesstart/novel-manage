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
    editingNovel: null,
    editingCategory: null,
    editingTag: null,
    importStep: 1,
    scannedNovels: [],
    importFolderPath: '',
    // 批量操作状态
    selectedNovels: new Set(),
    batchActionMode: 'tags'
};

// API 封装
const api = {
    async get(url) {
        const res = await fetch(url);
        return res.json();
    },
    async post(url, data) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    },
    async put(url, data) {
        const res = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    },
    async delete(url) {
        const res = await fetch(url, { method: 'DELETE' });
        return res.json();
    }
};

// 初始化
async function init() {
    await Promise.all([
        loadStats(),
        loadCategories(),
        loadTags(),
        loadNovels()
    ]);
    bindEvents();
}

// 加载统计数据
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

        // 添加标签筛选参数
        if (filters.tag_ids && filters.tag_ids.length > 0) {
            filters.tag_ids.forEach(tagId => params.append('tag_ids', tagId));
        }

        const res = await api.get(`/api/novels?${params}`);
        if (res.success) {
            state.novels = res.data;
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
            <input type="checkbox" class="novel-select-checkbox"
                   ${isSelected ? 'checked' : ''}
                   onchange="toggleNovelSelection(${novel.id}, this.checked)">
            <div class="novel-header">
                <div>
                    <div class="novel-title">${escapeHtml(novel.title)}</div>
                    <div class="novel-author">${novel.author ? escapeHtml(novel.author) : '未知作者'}</div>
                </div>
                <span class="novel-status status-${novel.status}">${getStatusText(novel.status)}</span>
            </div>
            ${novel.category_name ? `<span class="novel-category">${escapeHtml(novel.category_name)}</span>` : ''}
            ${novel.description ? `<div class="novel-description">${escapeHtml(novel.description)}</div>` : ''}
            ${novel.tags && novel.tags.length > 0 ? `
                <div class="novel-tags">
                    ${novel.tags.map(tag => `
                        <span class="novel-tag" style="background-color: ${tag.color}20; color: ${tag.color}">
                            ${escapeHtml(tag.name)}
                        </span>
                    `).join('')}
                </div>
            ` : ''}
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

    const options = state.categories.map(cat =>
        `<option value="${cat.id}">${escapeHtml(cat.name)}</option>`
    ).join('');

    filterSelect.innerHTML = '<option value="">全部分类</option>' + options;
    novelSelect.innerHTML = '<option value="">无分类</option>' + options;
}

// 更新标签选择器
function updateTagSelectors() {
    // 更新筛选标签
    const filterContainer = document.getElementById('filter-tags');
    filterContainer.innerHTML = state.tags.map(tag => `
        <span class="filter-tag ${state.selectedTags.has(tag.id) ? 'active' : ''}"
              data-id="${tag.id}"
              style="background-color: ${tag.color}20; color: ${tag.color}"
              onclick="toggleFilterTag(${tag.id})">
            ${escapeHtml(tag.name)}
        </span>
    `).join('');

    // 更新小说编辑标签选择器
    const selectorContainer = document.getElementById('novel-tag-selector');
    selectorContainer.innerHTML = state.tags.map(tag => `
        <span class="tag-option"
              data-id="${tag.id}"
              style="background-color: ${tag.color}20; color: ${tag.color}"
              onclick="toggleNovelTag(this, ${tag.id})">
            ${escapeHtml(tag.name)}
        </span>
    `).join('');
}

// 切换筛选标签
function toggleFilterTag(tagId) {
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

// 应用筛选
function applyFilters() {
    const keyword = document.getElementById('search-input').value;
    const categoryId = document.getElementById('filter-category').value;
    const status = document.getElementById('filter-status').value;

    loadNovels({
        keyword,
        category_id: categoryId,
        status: status,
        tag_ids: Array.from(state.selectedTags)
    });
}

// 打开小说阅读器
async function openNovelFile(novelId) {
    openReader(novelId);
}

// ==================== 阅读器功能 ====================

const readerState = {
    novelId: null,
    chapters: [],
    currentChapter: 0,
    fontSize: 18,
    darkTheme: false
};

async function openReader(novelId) {
    readerState.novelId = novelId;
    readerState.currentChapter = 0;

    // 显示阅读器弹窗
    openModal('reader-modal');

    // 显示加载状态
    document.getElementById('reader-loading').classList.remove('hidden');
    document.getElementById('reader-text').classList.add('hidden');
    document.getElementById('reader-empty').classList.add('hidden');

    try {
        const res = await api.get(`/api/novels/${novelId}/read`);

        if (res.success) {
            const data = res.data;
            readerState.chapters = data.chapters;

            // 更新小说标题
            document.getElementById('reader-novel-title').textContent = data.novel.title;

            // 更新章节数量
            document.getElementById('reader-toc-count').textContent = `${data.chapters.length}章`;

            // 渲染目录
            renderTOC();

            // 加载第一章
            await loadChapter(0);
        } else {
            // 显示错误信息但仍在阅读器中显示
            document.getElementById('reader-loading').classList.add('hidden');
            document.getElementById('reader-empty').classList.remove('hidden');
            document.querySelector('#reader-empty p').textContent = res.message || '无法加载小说';

            if (res.data && res.data.chapters) {
                readerState.chapters = res.data.chapters;
                renderTOC();
            }
        }
    } catch (err) {
        console.error('加载小说失败:', err);
        document.getElementById('reader-loading').classList.add('hidden');
        document.getElementById('reader-empty').classList.remove('hidden');
        document.querySelector('#reader-empty p').textContent = '加载失败: ' + err.message;
    }
}

function renderTOC() {
    const container = document.getElementById('reader-toc');

    if (readerState.chapters.length === 0) {
        container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-secondary);">未识别到章节</div>';
        return;
    }

    container.innerHTML = readerState.chapters.map((chapter, index) => `
        <div class="toc-item ${index === readerState.currentChapter ? 'active' : ''}"
             data-index="${index}"
             onclick="loadChapter(${index})">
            ${escapeHtml(chapter.title)}
        </div>
    `).join('');
}

async function loadChapter(index) {
    if (index < 0 || index >= readerState.chapters.length) return;

    readerState.currentChapter = index;

    // 更新目录高亮
    document.querySelectorAll('.toc-item').forEach((item, i) => {
        item.classList.toggle('active', i === index);
    });

    // 滚动到当前章节
    const activeItem = document.querySelector('.toc-item.active');
    if (activeItem) {
        activeItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // 显示加载状态
    document.getElementById('reader-loading').classList.remove('hidden');
    document.getElementById('reader-text').classList.add('hidden');

    try {
        const res = await api.get(`/api/novels/${readerState.novelId}/chapters/${index}`);

        if (res.success) {
            const chapter = res.data.chapter;

            // 更新章节标题
            document.getElementById('reader-chapter-title').textContent = chapter.title;

            // 渲染内容
            const contentDiv = document.getElementById('reader-text');
            // 将换行转换为段落
            const paragraphs = chapter.content.split('\n')
                .filter(line => line.trim())
                .map(line => `<p>${escapeHtml(line)}</p>`)
                .join('');

            contentDiv.innerHTML = paragraphs || '<p>本章无内容</p>';

            // 更新进度
            document.getElementById('reader-progress').textContent =
                `${index + 1} / ${chapter.total_chapters}`;

            // 更新导航按钮
            document.getElementById('reader-prev-chapter').disabled = index === 0;
            document.getElementById('reader-next-chapter').disabled =
                index >= chapter.total_chapters - 1;

            // 显示内容
            document.getElementById('reader-loading').classList.add('hidden');
            document.getElementById('reader-text').classList.remove('hidden');

            // 滚动到顶部
            document.getElementById('reader-content').scrollTop = 0;
        } else {
            document.getElementById('reader-loading').classList.add('hidden');
            document.getElementById('reader-empty').classList.remove('hidden');
        }
    } catch (err) {
        console.error('加载章节失败:', err);
        document.getElementById('reader-loading').classList.add('hidden');
        document.getElementById('reader-empty').classList.remove('hidden');
    }
}

function prevChapter() {
    if (readerState.currentChapter > 0) {
        loadChapter(readerState.currentChapter - 1);
    }
}

function nextChapter() {
    if (readerState.currentChapter < readerState.chapters.length - 1) {
        loadChapter(readerState.currentChapter + 1);
    }
}

function increaseFontSize() {
    if (readerState.fontSize < 32) {
        readerState.fontSize += 2;
        document.getElementById('reader-text').style.fontSize = readerState.fontSize + 'px';
    }
}

function decreaseFontSize() {
    if (readerState.fontSize > 12) {
        readerState.fontSize -= 2;
        document.getElementById('reader-text').style.fontSize = readerState.fontSize + 'px';
    }
}

function toggleReaderTheme() {
    readerState.darkTheme = !readerState.darkTheme;
    const modal = document.getElementById('reader-modal');
    modal.classList.toggle('dark-theme', readerState.darkTheme);

    const icon = document.querySelector('#reader-theme-toggle i');
    icon.className = readerState.darkTheme ? 'fas fa-sun' : 'fas fa-moon';
}

// ==================== 下载功能 ====================

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
        tag_ids: Array.from(document.querySelectorAll('#novel-tag-selector .tag-option.selected'))
            .map(el => parseInt(el.dataset.id))
    };

    try {
        let res;
        if (state.editingNovel) {
            res = await api.put(`/api/novels/${state.editingNovel.id}`, data);
        } else {
            res = await api.post('/api/novels', data);
        }

        if (res.success) {
            closeModal('novel-modal');
            await Promise.all([loadNovels(), loadStats()]);
            showToast(state.editingNovel ? '小说已更新' : '小说已添加', 'success');
        } else {
            showToast(res.message || '操作失败', 'error');
        }
    } catch (err) {
        console.error('保存小说失败:', err);
        showToast('保存失败', 'error');
    }
}

// 编辑小说
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

    // 设置已选标签
    document.querySelectorAll('#novel-tag-selector .tag-option').forEach(el => {
        el.classList.remove('selected');
        const tagId = parseInt(el.dataset.id);
        if (novel.tags && novel.tags.some(t => t.id === tagId)) {
            el.classList.add('selected');
        }
    });

    openModal('novel-modal');
}

// 删除小说
async function deleteNovel(novelId) {
    if (!confirm('确定要删除这本小说吗？')) return;

    try {
        const res = await api.delete(`/api/novels/${novelId}`);
        if (res.success) {
            await Promise.all([loadNovels(), loadStats()]);
            showToast('小说已删除', 'success');
        } else {
            showToast(res.message || '删除失败', 'error');
        }
    } catch (err) {
        console.error('删除小说失败:', err);
        showToast('删除失败', 'error');
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
function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

function resetNovelModal() {
    state.editingNovel = null;
    document.getElementById('novel-modal-title').textContent = '添加小说';
    document.getElementById('novel-form').reset();
    document.getElementById('novel-id').value = '';
    document.querySelectorAll('#novel-tag-selector .tag-option').forEach(el => {
        el.classList.remove('selected');
    });
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
function switchView(viewName) {
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

    // 加载爬虫数据
    if (viewName === 'crawler') {
        loadCrawlerStats();
        loadCrawlerTasks();
    }

    // 加载 AI 配置数据
    if (viewName === 'ai-config') {
        loadAIProviders();
        loadAIConfigs();
    }
}

// ==================== 爬虫管理功能 ====================

const crawlerState = {
    tasks: [],
    filter: '',
    statusFilter: ''
};

async function loadCrawlerStats() {
    // 模拟数据，后续可以接入真实API
    document.getElementById('crawler-total-tasks').textContent = '0';
    document.getElementById('crawler-running-tasks').textContent = '0';
    document.getElementById('crawler-completed-tasks').textContent = '0';
    document.getElementById('crawler-downloaded-novels').textContent = '0';
}

async function loadCrawlerTasks() {
    const container = document.getElementById('crawler-tasks-list');

    // 模拟空状态
    container.innerHTML = `
        <div class="empty-state">
            <i class="fas fa-spider"></i>
            <h3>暂无爬虫任务</h3>
            <p>点击"新建爬虫任务"按钮添加爬虫</p>
        </div>
    `;
}

function openAddCrawlerTaskModal() {
    showToast('爬虫功能开发中...', 'success');
}

// ==================== AI 配置功能 ====================

const aiConfigState = {
    configs: [],
    providers: [],
    editingConfig: null,
    activeConfigId: null
};

// 提供商模型提示
const providerModels = {
    openai: {
        hint: '常用模型：gpt-3.5-turbo, gpt-4, gpt-4-turbo, gpt-4o',
        defaultModel: 'gpt-3.5-turbo'
    },
    'openai-compatible': {
        hint: '阿里：qwen-turbo, qwen-plus, qwen-max | 月之暗面：moonshot-v1-8k, moonshot-v1-32k | DeepSeek：deepseek-chat',
        defaultModel: 'qwen-turbo'
    },
    claude: {
        hint: '常用模型：claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307',
        defaultModel: 'claude-3-haiku-20240307'
    },
    gemini: {
        hint: '常用模型：gemini-pro, gemini-1.5-pro, gemini-1.5-flash',
        defaultModel: 'gemini-pro'
    },
    ollama: {
        hint: '本地模型：llama2, llama3, mistral, qwen, phi3 等',
        defaultModel: 'llama3'
    }
};

async function loadAIConfigs() {
    try {
        const res = await api.get('/api/ai/configs');
        if (res.success) {
            aiConfigState.configs = res.data;
            aiConfigState.activeConfigId = res.data.find(c => c.is_active)?.id || null;
            renderAIConfigs();
        }
    } catch (err) {
        console.error('加载 AI 配置失败:', err);
        showToast('加载 AI 配置失败', 'error');
    }
}

async function loadAIProviders() {
    try {
        const res = await api.get('/api/ai/providers');
        if (res.success) {
            aiConfigState.providers = res.data;
        }
    } catch (err) {
        console.error('加载 AI 提供商失败:', err);
    }
}

function renderAIConfigs() {
    const container = document.getElementById('ai-config-list');

    if (aiConfigState.configs.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-robot"></i>
                <h3>暂无 AI 配置</h3>
                <p>点击"添加配置"按钮创建 AI 配置</p>
            </div>
        `;
        return;
    }

    container.innerHTML = aiConfigState.configs.map(config => {
        const isActive = config.id === aiConfigState.activeConfigId;
        const provider = aiConfigState.providers.find(p => p.id === config.provider);
        const providerName = provider ? provider.name : config.provider;

        return `
            <div class="ai-config-card ${isActive ? 'active' : ''}">
                <div class="ai-config-info-main">
                    <div class="ai-config-icon ${config.provider}">
                        <i class="fas fa-${getProviderIcon(config.provider)}"></i>
                    </div>
                    <div class="ai-config-details">
                        <h4>${escapeHtml(config.name)}</h4>
                        <div class="ai-config-meta">
                            <span>${escapeHtml(providerName)}</span>
                            <span class="ai-config-model">${escapeHtml(config.model)}</span>
                            ${isActive ? '<span class="ai-config-status active"><i class="fas fa-check-circle"></i> 当前激活</span>' : ''}
                        </div>
                    </div>
                </div>
                <div class="ai-config-actions">
                    ${!isActive ? `
                        <button class="btn btn-sm btn-secondary" onclick="activateAIConfig(${config.id})">
                            <i class="fas fa-check"></i> 激活
                        </button>
                    ` : ''}
                    <button class="btn btn-sm btn-secondary" onclick="testAIConfig(${config.id})">
                        <i class="fas fa-plug"></i> 测试
                    </button>
                    <button class="btn btn-sm btn-primary" onclick="editAIConfig(${config.id})">
                        <i class="fas fa-edit"></i> 编辑
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteAIConfig(${config.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function getProviderIcon(provider) {
    const icons = {
        openai: 'brain',
        'openai-compatible': 'plug',
        claude: 'feather-alt',
        gemini: 'sparkles',
        ollama: 'server'
    };
    return icons[provider] || 'robot';
}

function resetAIConfigModal() {
    aiConfigState.editingConfig = null;
    document.getElementById('ai-config-id').value = '';
    document.getElementById('ai-config-name').value = '';
    document.getElementById('ai-config-provider').value = 'openai';
    document.getElementById('ai-config-model').value = '';
    document.getElementById('ai-config-api-key').value = '';
    document.getElementById('ai-config-api-base').value = '';
    document.getElementById('ai-config-temperature').value = '0.7';
    document.getElementById('ai-config-max-tokens').value = '2000';
    document.getElementById('ai-config-modal-title').textContent = '添加 AI 配置';

    updateProviderHint('openai');
}

function updateProviderHint(provider) {
    const hint = providerModels[provider]?.hint || '';
    const defaultModel = providerModels[provider]?.defaultModel || '';
    document.getElementById('ai-model-hint').textContent = hint;

    const modelInput = document.getElementById('ai-config-model');
    if (!modelInput.value && defaultModel) {
        modelInput.value = defaultModel;
    }
}

async function saveAIConfig() {
    const id = document.getElementById('ai-config-id').value;
    const configData = {
        name: document.getElementById('ai-config-name').value.trim(),
        provider: document.getElementById('ai-config-provider').value,
        model: document.getElementById('ai-config-model').value.trim(),
        api_key: document.getElementById('ai-config-api-key').value.trim(),
        api_base: document.getElementById('ai-config-api-base').value.trim(),
        temperature: parseFloat(document.getElementById('ai-config-temperature').value),
        max_tokens: parseInt(document.getElementById('ai-config-max-tokens').value)
    };

    if (!configData.name) {
        showToast('请输入配置名称', 'error');
        return;
    }
    if (!configData.model) {
        showToast('请输入模型名称', 'error');
        return;
    }
    if (configData.provider !== 'ollama' && !configData.api_key) {
        showToast('请输入 API Key', 'error');
        return;
    }

    try {
        let res;
        if (id) {
            res = await api.put(`/api/ai/configs/${id}`, configData);
        } else {
            res = await api.post('/api/ai/configs', configData);
        }

        if (res.success) {
            closeModal('ai-config-modal');
            await loadAIConfigs();
            showToast(id ? '配置已更新' : '配置已创建', 'success');
        } else {
            showToast(res.message || '保存失败', 'error');
        }
    } catch (err) {
        console.error('保存 AI 配置失败:', err);
        showToast('保存失败: ' + err.message, 'error');
    }
}

async function editAIConfig(id) {
    const config = aiConfigState.configs.find(c => c.id === id);
    if (!config) return;

    aiConfigState.editingConfig = config;
    document.getElementById('ai-config-id').value = config.id;
    document.getElementById('ai-config-name').value = config.name;
    document.getElementById('ai-config-provider').value = config.provider;
    document.getElementById('ai-config-model').value = config.model;
    document.getElementById('ai-config-api-key').value = config.api_key || '';
    document.getElementById('ai-config-api-base').value = config.api_base || '';
    document.getElementById('ai-config-temperature').value = config.temperature;
    document.getElementById('ai-config-max-tokens').value = config.max_tokens;
    document.getElementById('ai-config-modal-title').textContent = '编辑 AI 配置';

    updateProviderHint(config.provider);
    openModal('ai-config-modal');
}

async function deleteAIConfig(id) {
    if (!confirm('确定要删除这个 AI 配置吗？')) return;

    try {
        const res = await api.delete(`/api/ai/configs/${id}`);
        if (res.success) {
            await loadAIConfigs();
            showToast('配置已删除', 'success');
        } else {
            showToast(res.message || '删除失败', 'error');
        }
    } catch (err) {
        console.error('删除 AI 配置失败:', err);
        showToast('删除失败: ' + err.message, 'error');
    }
}

async function activateAIConfig(id) {
    try {
        const res = await api.post(`/api/ai/configs/${id}/activate`);
        if (res.success) {
            aiConfigState.activeConfigId = id;
            renderAIConfigs();
            showToast('配置已激活', 'success');
        } else {
            showToast(res.message || '激活失败', 'error');
        }
    } catch (err) {
        console.error('激活 AI 配置失败:', err);
        showToast('激活失败: ' + err.message, 'error');
    }
}

async function testAIConfig(id) {
    try {
        showToast('正在测试连接...', 'success');
        const res = await api.post(`/api/ai/configs/${id}/test`);
        if (res.success) {
            showToast('连接成功', 'success');
        } else {
            showToast('连接失败: ' + res.message, 'error');
        }
    } catch (err) {
        console.error('测试 AI 连接失败:', err);
        showToast('测试失败: ' + err.message, 'error');
    }
}

async function testCurrentAIConfig() {
    const id = document.getElementById('ai-config-id').value;
    if (!id) {
        showToast('请先保存配置', 'error');
        return;
    }
    await testAIConfig(id);
}

// AI 聊天测试功能
function addChatMessage(role, content) {
    const container = document.getElementById('ai-chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `ai-chat-message ${role}`;
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-${role === 'user' ? 'user' : 'robot'}"></i>
        </div>
        <div class="message-content">${escapeHtml(content)}</div>
    `;
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

async function sendChatMessage() {
    const input = document.getElementById('ai-chat-input');
    const message = input.value.trim();
    if (!message) return;

    addChatMessage('user', message);
    input.value = '';

    try {
        const res = await api.post('/api/ai/chat', { message });
        if (res.success) {
            addChatMessage('ai', res.data.response);
        } else {
            addChatMessage('ai', '错误: ' + res.message);
        }
    } catch (err) {
        addChatMessage('ai', '请求失败: ' + err.message);
    }
}

// 工具函数
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
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
        <span>${message}</span>
    `;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// ==================== 批量操作功能 ====================

function toggleNovelSelection(novelId, selected) {
    if (selected) {
        state.selectedNovels.add(novelId);
    } else {
        state.selectedNovels.delete(novelId);
    }
    updateBatchActionsBar();
    renderNovels(); // 重新渲染以更新选中状态样式
}

function toggleAllNovels(selected) {
    if (selected) {
        state.novels.forEach(novel => state.selectedNovels.add(novel.id));
    } else {
        state.selectedNovels.clear();
    }
    updateBatchActionsBar();
    renderNovels();
}

function updateBatchActionsBar() {
    const bar = document.getElementById('batch-actions-bar');
    const count = state.selectedNovels.size;

    document.getElementById('batch-selected-count').textContent = count;

    if (count > 0) {
        bar.classList.remove('hidden');
    } else {
        bar.classList.add('hidden');
    }
}

function clearBatchSelection() {
    state.selectedNovels.clear();
    updateBatchActionsBar();
    renderNovels();
}

function openBatchModal(mode) {
    state.batchActionMode = mode;

    const selectedNovelsList = state.novels.filter(n => state.selectedNovels.has(n.id));
    if (selectedNovelsList.length === 0) {
        showToast('请先选择小说', 'error');
        return;
    }

    // 更新弹窗标题
    const titles = {
        'tags': '批量添加标签',
        'category': '批量设置分类',
        'status': '批量设置阅读状态'
    };
    document.getElementById('batch-modal-title').textContent = titles[mode];

    // 更新选中小说预览
    const previewContainer = document.getElementById('batch-novels-preview');
    previewContainer.innerHTML = selectedNovelsList.slice(0, 5).map(novel => `
        <div class="preview-item">
            <i class="fas fa-book"></i>
            <span>${escapeHtml(novel.title)}</span>
        </div>
    `).join('') + (selectedNovelsList.length > 5 ? `
        <div class="preview-item">
            <span>...还有 ${selectedNovelsList.length - 5} 本</span>
        </div>
    ` : '');

    // 更新标签页状态
    document.querySelectorAll('.action-mode-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.mode === mode);
    });

    // 显示对应面板
    document.querySelectorAll('.action-panel').forEach(panel => {
        panel.classList.add('hidden');
    });
    document.getElementById(`action-panel-${mode}`).classList.remove('hidden');

    // 更新标签选择器
    if (mode === 'tags') {
        updateBatchTagSelector();
    }

    // 更新分类选择器
    if (mode === 'category') {
        updateBatchCategorySelect();
    }

    openModal('batch-action-modal');
}

function updateBatchTagSelector() {
    const container = document.getElementById('batch-tag-select');
    container.innerHTML = state.tags.map(tag => `
        <span class="tag-select-item"
              data-id="${tag.id}"
              style="background-color: ${tag.color}20; color: ${tag.color}"
              onclick="this.classList.toggle('selected')">
            ${escapeHtml(tag.name)}
        </span>
    `).join('');
}

function updateBatchCategorySelect() {
    const select = document.getElementById('batch-category-select');
    select.innerHTML = '<option value="">无分类</option>' +
        state.categories.map(cat => `
            <option value="${cat.id}">${escapeHtml(cat.name)}</option>
        `).join('');
}

async function executeBatchAction() {
    const novelIds = Array.from(state.selectedNovels);
    const mode = state.batchActionMode;

    try {
        let res;
        let message;

        if (mode === 'tags') {
            const tagIds = Array.from(document.querySelectorAll('#batch-tag-select .tag-select-item.selected'))
                .map(el => parseInt(el.dataset.id));

            if (tagIds.length === 0) {
                showToast('请选择标签', 'error');
                return;
            }

            res = await api.post('/api/novels/batch/tags', {
                novel_ids: novelIds,
                tag_ids: tagIds,
                mode: 'add'
            });
            message = '标签已添加';

        } else if (mode === 'category') {
            const categoryId = document.getElementById('batch-category-select').value || null;

            res = await api.post('/api/novels/batch/category', {
                novel_ids: novelIds,
                category_id: categoryId
            });
            message = '分类已设置';

        } else if (mode === 'status') {
            const status = parseInt(document.getElementById('batch-status-select').value);

            res = await api.post('/api/novels/batch/status', {
                novel_ids: novelIds,
                status: status
            });
            message = '阅读状态已更新';
        }

        if (res.success) {
            closeModal('batch-action-modal');
            clearBatchSelection();
            await loadNovels();
            showToast(message, 'success');
        } else {
            showToast(res.message || '操作失败', 'error');
        }
    } catch (err) {
        console.error('批量操作失败:', err);
        showToast('操作失败: ' + err.message, 'error');
    }
}

async function batchDeleteNovels() {
    const novelIds = Array.from(state.selectedNovels);

    if (novelIds.length === 0) {
        showToast('请先选择小说', 'error');
        return;
    }

    if (!confirm(`确定要删除选中的 ${novelIds.length} 本小说吗？此操作不可恢复。`)) {
        return;
    }

    try {
        const res = await api.post('/api/novels/batch/delete', {
            novel_ids: novelIds
        });

        if (res.success) {
            clearBatchSelection();
            await Promise.all([loadNovels(), loadStats()]);
            showToast(`已删除 ${res.data.deleted} 本小说`, 'success');
        } else {
            showToast(res.message || '删除失败', 'error');
        }
    } catch (err) {
        console.error('批量删除失败:', err);
        showToast('删除失败: ' + err.message, 'error');
    }
}

// 事件绑定
function bindEvents() {
    // 导航切换
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            switchView(item.dataset.view);
        });
    });

    // 搜索
    let searchTimeout;
    document.getElementById('search-input').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            applyFilters();
        }, 300);
    });

    // 筛选器
    document.getElementById('filter-category').addEventListener('change', applyFilters);
    document.getElementById('filter-status').addEventListener('change', applyFilters);

    // 添加小说按钮
    document.getElementById('btn-add-novel').addEventListener('click', () => {
        resetNovelModal();
        openModal('novel-modal');
    });

    // 保存小说
    document.getElementById('btn-save-novel').addEventListener('click', saveNovel);

    // 添加分类按钮
    document.getElementById('btn-add-category').addEventListener('click', () => {
        resetCategoryModal();
        openModal('category-modal');
    });

    // 保存分类
    document.getElementById('btn-save-category').addEventListener('click', saveCategory);

    // 添加标签按钮
    document.getElementById('btn-add-tag').addEventListener('click', () => {
        resetTagModal();
        openModal('tag-modal');
    });

    // 保存标签
    document.getElementById('btn-save-tag').addEventListener('click', saveTag);

    // 关闭弹窗
    document.querySelectorAll('.btn-close, .btn-cancel').forEach(btn => {
        btn.addEventListener('click', () => {
            const modal = btn.closest('.modal');
            if (modal) {
                closeModal(modal.id);
            }
        });
    });

    // 点击弹窗外部关闭
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal(modal.id);
            }
        });
    });

    // 颜色选择器实时更新
    document.getElementById('tag-color').addEventListener('input', (e) => {
        document.querySelector('.color-value').textContent = e.target.value;
    });

    // 文件浏览按钮
    document.getElementById('btn-browse-file').addEventListener('click', () => {
        document.getElementById('file-input').click();
    });

    // 文件选择
    document.getElementById('file-input').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            document.getElementById('novel-file-path').value = file.name;
        }
    });

    // ==================== 批量操作事件绑定 ====================

    // 全选/取消全选
    document.getElementById('select-all-novels-main').addEventListener('change', (e) => {
        toggleAllNovels(e.target.checked);
    });

    // 批量操作按钮
    document.getElementById('btn-batch-tags').addEventListener('click', () => {
        openBatchModal('tags');
    });

    document.getElementById('btn-batch-category').addEventListener('click', () => {
        openBatchModal('category');
    });

    document.getElementById('btn-batch-status').addEventListener('click', () => {
        openBatchModal('status');
    });

    document.getElementById('btn-batch-delete').addEventListener('click', batchDeleteNovels);

    document.getElementById('btn-batch-clear').addEventListener('click', clearBatchSelection);

    // 批量操作模式切换
    document.querySelectorAll('.action-mode-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            openBatchModal(tab.dataset.mode);
        });
    });

    // 执行批量操作
    document.getElementById('btn-execute-batch').addEventListener('click', executeBatchAction);

    // ==================== 批量导入事件绑定 ====================

    // 打开批量导入弹窗
    document.getElementById('btn-batch-import').addEventListener('click', () => {
        resetBatchImportModal();
        openModal('batch-import-modal');
        updateImportTagSelector();
    });

    // 选择文件夹按钮
    document.getElementById('btn-select-folder').addEventListener('click', () => {
        document.getElementById('folder-input').click();
    });

    // 文件夹选择变化
    document.getElementById('folder-input').addEventListener('change', (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            // 获取文件夹路径（从第一个文件的路径推断）
            const filePath = files[0].webkitRelativePath || files[0].name;
            const folderName = filePath.split('/')[0];
            document.getElementById('import-folder-path').value = folderName;

            // 收集所有文件
            state.scannedNovels = [];
            for (const file of files) {
                const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
                const validExts = ['.txt', '.epub', '.pdf', '.mobi', '.azw3', '.doc', '.docx', '.rtf'];
                if (validExts.includes(ext)) {
                    const relativePath = file.webkitRelativePath || file.name;
                    const pathParts = relativePath.split('/');
                    const categoryName = pathParts.length > 1 ? pathParts[0] : null;

                    // 清理文件名
                    let title = file.name.replace(ext, '');
                    title = title.replace(/^\d+[\s\-_\.]+/, '').trim();

                    state.scannedNovels.push({
                        file_path: relativePath,
                        title: title,
                        category_name: categoryName,
                        selected: true,
                        file_size: file.size
                    });
                }
            }

            // 显示扫描结果
            if (state.scannedNovels.length > 0) {
                showImportStep(2);
                renderScannedNovels();
            } else {
                showToast('未找到小说文件', 'error');
            }
        }
    });

    // 重新扫描按钮
    document.getElementById('btn-rescan').addEventListener('click', () => {
        showImportStep(1);
        state.scannedNovels = [];
        document.getElementById('import-folder-path').value = '';
        document.getElementById('folder-input').value = '';
    });

    // 全选/取消全选
    document.getElementById('select-all-novels').addEventListener('change', (e) => {
        const checked = e.target.checked;
        state.scannedNovels.forEach(novel => novel.selected = checked);
        renderScannedNovels();
        updateScanStats();
    });

    // 取消导入
    document.getElementById('btn-import-cancel').addEventListener('click', () => {
        closeModal('batch-import-modal');
    });

    // 开始导入
    document.getElementById('btn-start-import').addEventListener('click', executeBatchImport);

    // 完成导入
    document.getElementById('btn-import-finish').addEventListener('click', async () => {
        closeModal('batch-import-modal');
        await Promise.all([loadNovels(), loadCategories(), loadStats()]);
    });

    // ==================== 阅读器事件绑定 ====================

    // 关闭阅读器
    document.getElementById('reader-close').addEventListener('click', () => {
        closeModal('reader-modal');
    });

    // 上一章/下一章
    document.getElementById('reader-prev-chapter').addEventListener('click', prevChapter);
    document.getElementById('reader-next-chapter').addEventListener('click', nextChapter);

    // 字体大小调整
    document.getElementById('reader-font-increase').addEventListener('click', increaseFontSize);
    document.getElementById('reader-font-decrease').addEventListener('click', decreaseFontSize);

    // 主题切换
    document.getElementById('reader-theme-toggle').addEventListener('click', toggleReaderTheme);

    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
        // 只在阅读器打开时生效
        if (!document.getElementById('reader-modal').classList.contains('active')) return;

        switch(e.key) {
            case 'ArrowLeft':
                prevChapter();
                break;
            case 'ArrowRight':
            case ' ':
                nextChapter();
                break;
            case 'Escape':
                closeModal('reader-modal');
                break;
        }
    });

    // ==================== 爬虫管理事件绑定 ====================

    // 新建爬虫任务
    document.getElementById('btn-add-crawler-task').addEventListener('click', openAddCrawlerTaskModal);

    // 爬虫任务筛选
    document.getElementById('crawler-status-filter').addEventListener('change', (e) => {
        crawlerState.statusFilter = e.target.value;
        loadCrawlerTasks();
    });

    document.getElementById('crawler-search').addEventListener('input', (e) => {
        crawlerState.filter = e.target.value;
        // 可以添加防抖逻辑
        loadCrawlerTasks();
    });

    // ==================== AI 配置事件绑定 ====================

    // 添加 AI 配置
    document.getElementById('btn-add-ai-config').addEventListener('click', () => {
        resetAIConfigModal();
        openModal('ai-config-modal');
    });

    // 保存 AI 配置
    document.getElementById('btn-save-ai-config').addEventListener('click', saveAIConfig);

    // 测试 AI 配置
    document.getElementById('btn-test-ai-config').addEventListener('click', testCurrentAIConfig);

    // 提供商选择变化时更新提示
    document.getElementById('ai-config-provider').addEventListener('change', (e) => {
        updateProviderHint(e.target.value);
    });

    // AI 聊天测试
    document.getElementById('btn-ai-send').addEventListener('click', sendChatMessage);
    document.getElementById('ai-chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });
}

// ==================== 批量导入功能 ====================

function resetBatchImportModal() {
    state.importStep = 1;
    state.scannedNovels = [];
    state.importFolderPath = '';

    // 重置表单
    document.getElementById('import-folder-path').value = '';
    document.getElementById('import-create-categories').checked = true;
    document.getElementById('import-default-status').value = '0';
    document.getElementById('folder-input').value = '';
    document.getElementById('select-all-novels').checked = true;

    // 显示第一步
    showImportStep(1);
}

function showImportStep(step) {
    state.importStep = step;

    // 隐藏所有步骤
    document.querySelectorAll('.import-step').forEach(el => el.classList.add('hidden'));
    document.getElementById(`import-step-${step}`).classList.remove('hidden');

    // 更新按钮显示
    document.getElementById('btn-start-scan').classList.add('hidden');
    document.getElementById('btn-start-import').classList.add('hidden');
    document.getElementById('btn-import-finish').classList.add('hidden');

    if (step === 1) {
        document.getElementById('btn-import-cancel').textContent = '取消';
    } else if (step === 2) {
        document.getElementById('btn-start-import').classList.remove('hidden');
        document.getElementById('btn-import-cancel').textContent = '上一步';
    } else if (step === 3) {
        document.getElementById('btn-import-finish').classList.remove('hidden');
        document.getElementById('btn-import-cancel').classList.add('hidden');
    }
}

function updateImportTagSelector() {
    const container = document.getElementById('import-tag-selector');
    container.innerHTML = state.tags.map(tag => `
        <span class="tag-option"
              data-id="${tag.id}"
              style="background-color: ${tag.color}20; color: ${tag.color}"
              onclick="this.classList.toggle('selected')">
            ${escapeHtml(tag.name)}
        </span>
    `).join('');
}

function renderScannedNovels() {
    const container = document.getElementById('import-novels-list');
    const total = state.scannedNovels.length;
    const selected = state.scannedNovels.filter(n => n.selected).length;

    document.getElementById('scan-total').textContent = total;
    document.getElementById('scan-selected').textContent = selected;

    if (state.scannedNovels.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>未找到小说文件</p></div>';
        return;
    }

    container.innerHTML = state.scannedNovels.map((novel, index) => `
        <div class="import-novel-item">
            <input type="checkbox" ${novel.selected ? 'checked' : ''}
                   onchange="toggleNovelSelection(${index}, this.checked)">
            <div class="import-novel-info">
                <div class="import-novel-title">${escapeHtml(novel.title)}</div>
                <div class="import-novel-meta">${formatFileSize(novel.file_size)} · ${escapeHtml(novel.file_path)}</div>
            </div>
            ${novel.category_name ? `<span class="import-novel-category">${escapeHtml(novel.category_name)}</span>` : ''}
        </div>
    `).join('');
}

function toggleNovelSelection(index, selected) {
    state.scannedNovels[index].selected = selected;
    updateScanStats();
}

function updateScanStats() {
    const selected = state.scannedNovels.filter(n => n.selected).length;
    document.getElementById('scan-selected').textContent = selected;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function executeBatchImport() {
    const selectedNovels = state.scannedNovels.filter(n => n.selected);
    if (selectedNovels.length === 0) {
        showToast('请选择要导入的小说', 'error');
        return;
    }

    // 获取选中的标签
    const tagIds = Array.from(document.querySelectorAll('#import-tag-selector .tag-option.selected'))
        .map(el => parseInt(el.dataset.id));

    const defaultStatus = parseInt(document.getElementById('import-default-status').value);
    const createCategories = document.getElementById('import-create-categories').checked;

    // 显示加载状态
    const importBtn = document.getElementById('btn-start-import');
    const originalText = importBtn.innerHTML;
    importBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 导入中...';
    importBtn.disabled = true;

    try {
        const res = await api.post('/api/import/batch', {
            novels: selectedNovels.map(n => ({
                ...n,
                category_name: createCategories ? n.category_name : null
            })),
            tag_ids: tagIds,
            default_status: defaultStatus
        });

        if (res.success) {
            // 显示导入结果
            document.getElementById('result-imported').textContent = res.data.imported;
            document.getElementById('result-skipped').textContent = res.data.skipped;
            document.getElementById('result-failed').textContent = res.data.failed;

            // 显示错误信息
            const errorsContainer = document.getElementById('import-errors');
            const errorsList = document.getElementById('import-errors-list');

            if (res.data.errors && res.data.errors.length > 0) {
                errorsContainer.classList.remove('hidden');
                errorsList.innerHTML = res.data.errors.map(err => `<li>${escapeHtml(err)}</li>`).join('');
            } else {
                errorsContainer.classList.add('hidden');
            }

            showImportStep(3);
        } else {
            showToast(res.message || '导入失败', 'error');
        }
    } catch (err) {
        console.error('批量导入失败:', err);
        showToast('导入失败: ' + err.message, 'error');
    } finally {
        importBtn.innerHTML = originalText;
        importBtn.disabled = false;
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', init);
