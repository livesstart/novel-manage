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
