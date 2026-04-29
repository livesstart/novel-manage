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

    if (!confirm(`确定要删除选中的 ${novelIds.length} 本小说及其对应文件吗？此操作不可恢复。`)) {
        return;
    }

    try {
        const res = await api.post('/api/novels/batch/delete', {
            novel_ids: novelIds
        });

        if (res.success) {
            clearBatchSelection();
            await Promise.all([loadNovels(), loadStats()]);
            const deletedFiles = res.data?.deleted_files || 0;
            showToast(
                deletedFiles > 0
                    ? `已删除 ${res.data.deleted} 本小说，并删除 ${deletedFiles} 个文件`
                    : `已删除 ${res.data.deleted} 本小说，对应文件不存在或已被其他记录共用`,
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

function getSelectedNovelsForBatchAI() {
    return state.novels.filter(novel => state.selectedNovels.has(novel.id));
}

function getCurrentBatchAIItem() {
    return batchAIState.queue[batchAIState.currentIndex] || null;
}

function getBatchAIStatusMeta(status) {
    const metaMap = {
        pending: { text: '待处理', className: 'pending' },
        generating: { text: '生成中', className: 'generating' },
        generated: { text: '待确认', className: 'generated' },
        applied: { text: '已应用', className: 'applied' },
        skipped: { text: '已跳过', className: 'skipped' },
        auto_skipped: { text: '失败已跳过', className: 'skipped' },
        error: { text: '生成失败', className: 'error' }
    };
    return metaMap[status] || metaMap.pending;
}

function buildBatchAIQueueItem(novel) {
    const originalTagIds = (novel.tags || []).map(tag => tag.id);
    return {
        id: novel.id,
        novel: {
            id: novel.id,
            title: novel.title,
            author: novel.author || '',
            description: novel.description || '',
            file_path: novel.file_path || '',
            category_id: novel.category_id || null,
            category_name: novel.category_name || '',
            status: novel.status,
            tags: (novel.tags || []).map(tag => ({ ...tag }))
        },
        status: 'pending',
        error: '',
        generatedSummary: '',
        generatedTagIds: [],
        originalTagIds,
        selectedTagIds: [...originalTagIds],
        applySummary: true,
        applyTags: true
    };
}

function resetBatchAIQueueState() {
    batchAIState.queue = [];
    batchAIState.currentIndex = 0;
    batchAIState.isGenerating = false;
    batchAIState.isApplying = false;
}

function isBatchAISkippedStatus(status) {
    return status === 'skipped' || status === 'auto_skipped';
}

function syncBatchAIModeSettings() {
    const autoSkipCheckbox = document.getElementById('batch-ai-auto-skip-error');
    if (!autoSkipCheckbox) {
        return;
    }
    batchAIState.autoSkipOnError = autoSkipCheckbox.checked;
}

function openBatchAIModal() {
    const selectedNovels = getSelectedNovelsForBatchAI();
    if (selectedNovels.length === 0) {
        showToast('请先选择小说', 'error');
        return;
    }

    resetBatchAIQueueState();
    batchAIState.queue = selectedNovels.map(buildBatchAIQueueItem);

    const autoSkipCheckbox = document.getElementById('batch-ai-auto-skip-error');
    if (autoSkipCheckbox) {
        autoSkipCheckbox.checked = batchAIState.autoSkipOnError;
    }
    syncBatchAIModeSettings();

    renderBatchAIQueue();
    openModal('batch-ai-modal');
    processCurrentBatchAIItem();
}

function renderBatchAIQueue() {
    const queueList = document.getElementById('batch-ai-queue-list');
    const progressText = document.getElementById('batch-ai-progress-text');
    const progressFill = document.getElementById('batch-ai-progress-fill');
    const queueSummary = document.getElementById('batch-ai-queue-summary');
    const queueHint = document.getElementById('batch-ai-queue-hint');

    const total = batchAIState.queue.length;
    const applied = batchAIState.queue.filter(item => item.status === 'applied').length;
    const skipped = batchAIState.queue.filter(item => isBatchAISkippedStatus(item.status)).length;
    const autoSkipped = batchAIState.queue.filter(item => item.status === 'auto_skipped').length;
    const errors = batchAIState.queue.filter(item => item.status === 'error').length;
    const doneCount = applied + skipped;
    const progressPercent = total ? Math.round((doneCount / total) * 100) : 0;
    const currentIndexDisplay = total ? Math.min(batchAIState.currentIndex + 1, total) : 0;

    progressText.textContent = `${currentIndexDisplay} / ${total}`;
    progressFill.style.width = `${progressPercent}%`;
    queueSummary.textContent = `已应用 ${applied} 本，跳过 ${skipped} 本，待处理 ${Math.max(total - doneCount, 0)} 本`;

    if (errors > 0) {
        queueHint.textContent = `有 ${errors} 本生成失败，可重新生成或跳过后继续`;
    } else if (autoSkipped > 0) {
        queueHint.textContent = `已有 ${autoSkipped} 本生成失败并自动跳过，队列会继续向后处理`;
    } else if (batchAIState.autoSkipOnError) {
        queueHint.textContent = '已开启失败自动跳过：生成失败时会直接处理下一本';
    } else {
        queueHint.textContent = '会逐本调用 AI，确认后再写回数据库';
    }

    queueList.innerHTML = batchAIState.queue.map((item, index) => {
        const statusMeta = getBatchAIStatusMeta(item.status);
        return `
            <div class="batch-ai-queue-item ${index === batchAIState.currentIndex ? 'active' : ''} ${statusMeta.className}">
                <div class="batch-ai-queue-item-top">
                    <strong>${index + 1}. ${escapeHtml(item.novel.title)}</strong>
                    <span class="batch-ai-queue-status ${statusMeta.className}">${statusMeta.text}</span>
                </div>
                <div class="batch-ai-queue-item-meta">${escapeHtml(item.novel.author || '未知作者')}</div>
            </div>
        `;
    }).join('');

    renderBatchAICurrentItem();
}

function renderBatchAICurrentItem() {
    const item = getCurrentBatchAIItem();
    const titleEl = document.getElementById('batch-ai-current-title');
    const metaEl = document.getElementById('batch-ai-current-meta');
    const statusEl = document.getElementById('batch-ai-current-status');
    const existingSummaryEl = document.getElementById('batch-ai-existing-summary');
    const generatedSummaryEl = document.getElementById('batch-ai-generated-summary');
    const applySummaryEl = document.getElementById('batch-ai-apply-summary');
    const applyTagsEl = document.getElementById('batch-ai-apply-tags');
    const resultHintEl = document.getElementById('batch-ai-result-hint');
    const regenerateBtn = document.getElementById('btn-batch-ai-regenerate');
    const skipBtn = document.getElementById('btn-batch-ai-skip');
    const applyBtn = document.getElementById('btn-batch-ai-apply-next');

    if (!item) {
        titleEl.textContent = '队列已完成';
        metaEl.textContent = '本轮批量 AI 处理已经结束';
        statusEl.textContent = '完成';
        statusEl.className = 'batch-ai-current-status applied';
        existingSummaryEl.textContent = '本轮没有待处理小说';
        generatedSummaryEl.value = '';
        generatedSummaryEl.disabled = true;
        applySummaryEl.checked = false;
        applySummaryEl.disabled = true;
        applyTagsEl.checked = false;
        applyTagsEl.disabled = true;
        resultHintEl.textContent = '你可以关闭弹窗，或重新选择小说开启下一轮队列';
        document.getElementById('batch-ai-tag-select').innerHTML = '';
        regenerateBtn.disabled = true;
        skipBtn.disabled = true;
        applyBtn.disabled = true;
        return;
    }

    const statusMeta = getBatchAIStatusMeta(item.status);
    const isBusy = batchAIState.isGenerating || batchAIState.isApplying;
    const canApply = item.status === 'generated';
    const isLast = batchAIState.currentIndex === batchAIState.queue.length - 1;

    titleEl.textContent = item.novel.title;
    metaEl.textContent = [
        item.novel.author || '未知作者',
        item.novel.category_name || '未分类',
        `已有 ${item.originalTagIds.length} 个标签`
    ].join(' · ');
    statusEl.textContent = statusMeta.text;
    statusEl.className = `batch-ai-current-status ${statusMeta.className}`;
    existingSummaryEl.textContent = item.novel.description || '暂无简介';

    generatedSummaryEl.disabled = !canApply || isBusy;
    generatedSummaryEl.value = item.generatedSummary || '';
    applySummaryEl.checked = item.applySummary;
    applySummaryEl.disabled = !canApply || isBusy;
    applyTagsEl.checked = item.applyTags;
    applyTagsEl.disabled = !canApply || isBusy;

    if (item.status === 'generating') {
        resultHintEl.textContent = '正在调用 AI 生成简介和标签，请稍候...';
    } else if (item.status === 'error') {
        resultHintEl.textContent = item.error || 'AI 生成失败，请重试';
    } else if (item.status === 'auto_skipped') {
        resultHintEl.textContent = item.error
            ? `本项生成失败，已按模式自动跳过：${item.error}`
            : '本项生成失败，已按模式自动跳过';
    } else if (item.error) {
        resultHintEl.textContent = `上次保存失败：${item.error}`;
    } else {
        resultHintEl.textContent = item.generatedTagIds.length > 0
            ? `AI 推荐了 ${item.generatedTagIds.length} 个标签，已自动勾选，可手动调整`
            : '会保留已有标签，并自动勾选 AI 推荐标签';
    }

    regenerateBtn.disabled = isBusy;
    skipBtn.disabled = isBusy;
    applyBtn.disabled = !canApply || isBusy;
    applyBtn.innerHTML = isLast
        ? '<i class="fas fa-check"></i> 应用并完成'
        : '<i class="fas fa-check"></i> 应用并下一个';
    skipBtn.innerHTML = isLast
        ? '<i class="fas fa-forward"></i> 跳过并完成'
        : '<i class="fas fa-forward"></i> 跳过当前';

    renderBatchAITagSelector();
}

function renderBatchAITagSelector() {
    const container = document.getElementById('batch-ai-tag-select');
    const item = getCurrentBatchAIItem();

    if (!item) {
        container.innerHTML = '';
        return;
    }

    if (state.tags.length === 0) {
        container.innerHTML = '<div class="form-hint">当前还没有标签，可先让 AI 生成后自动创建</div>';
        return;
    }

    const selectedSet = new Set(item.selectedTagIds);
    const generatedSet = new Set(item.generatedTagIds);
    const disabledAttr = item.status !== 'generated' || batchAIState.isGenerating || batchAIState.isApplying;

    container.innerHTML = state.tags.map(tag => `
        <span class="tag-select-item ${selectedSet.has(tag.id) ? 'selected' : ''} ${generatedSet.has(tag.id) ? 'generated-suggestion' : ''} ${disabledAttr ? 'disabled' : ''}"
              data-id="${tag.id}"
              style="background-color: ${tag.color}20; color: ${tag.color}"
              onclick="toggleBatchAITag(${tag.id})">
            ${escapeHtml(tag.name)}
        </span>
    `).join('');
}

function toggleBatchAITag(tagId) {
    const item = getCurrentBatchAIItem();
    if (!item || item.status !== 'generated' || batchAIState.isGenerating || batchAIState.isApplying) {
        return;
    }

    const selectedSet = new Set(item.selectedTagIds);
    if (selectedSet.has(tagId)) {
        selectedSet.delete(tagId);
    } else {
        selectedSet.add(tagId);
    }
    item.selectedTagIds = Array.from(selectedSet);
    renderBatchAITagSelector();
}

function syncBatchAIInputsToCurrentItem() {
    const item = getCurrentBatchAIItem();
    if (!item) {
        return;
    }

    item.generatedSummary = document.getElementById('batch-ai-generated-summary').value.trim();
    item.applySummary = document.getElementById('batch-ai-apply-summary').checked;
    item.applyTags = document.getElementById('batch-ai-apply-tags').checked;
}

async function processCurrentBatchAIItem(force = false) {
    const item = getCurrentBatchAIItem();
    if (!item || batchAIState.isGenerating) {
        return;
    }

    if (item.status === 'generated' && !force) {
        renderBatchAIQueue();
        return;
    }

    let shouldAdvanceAfterError = false;

    batchAIState.isGenerating = true;
    item.status = 'generating';
    item.error = '';
    renderBatchAIQueue();

    try {
        const res = await api.post('/api/ai/novels/metadata', { novel_id: item.id });
        if (!res.success) {
            throw new Error(buildAIErrorMessage(res));
        }

        await loadTags();

        item.generatedSummary = res.data.summary || '';
        item.generatedTagIds = (res.data.tags || []).map(tag => tag.id);
        item.selectedTagIds = Array.from(new Set([
            ...item.originalTagIds,
            ...item.generatedTagIds
        ]));
        item.applySummary = Boolean(item.generatedSummary);
        item.applyTags = item.selectedTagIds.length > 0;
        item.status = 'generated';
        renderBatchAIQueue();
    } catch (err) {
        item.error = err.message;
        item.generatedSummary = '';
        item.generatedTagIds = [];
        item.selectedTagIds = [...item.originalTagIds];
        item.applySummary = false;
        item.applyTags = item.originalTagIds.length > 0;

        if (batchAIState.autoSkipOnError) {
            item.status = 'auto_skipped';
            shouldAdvanceAfterError = true;
        } else {
            item.status = 'error';
            renderBatchAIQueue();
            showToast(`《${item.novel.title}》生成失败：${err.message}`, 'error');
        }
    } finally {
        batchAIState.isGenerating = false;
        renderBatchAIQueue();
    }

    if (shouldAdvanceAfterError) {
        await advanceBatchAIQueue();
    }
}

async function advanceBatchAIQueue() {
    batchAIState.currentIndex += 1;

    if (batchAIState.currentIndex >= batchAIState.queue.length) {
        const applied = batchAIState.queue.filter(item => item.status === 'applied').length;
        const skipped = batchAIState.queue.filter(item => item.status === 'skipped').length;
        const autoSkipped = batchAIState.queue.filter(item => item.status === 'auto_skipped').length;
        const failed = batchAIState.queue.filter(item => item.status === 'error').length;

        closeModal('batch-ai-modal');
        clearBatchSelection();
        await Promise.all([loadNovels(), loadStats(), loadTags()]);
        resetBatchAIQueueState();
        showToast(
            `批量 AI 完成：已应用 ${applied} 本，手动跳过 ${skipped} 本${autoSkipped ? `，失败自动跳过 ${autoSkipped} 本` : ''}${failed ? `，失败 ${failed} 本` : ''}`,
            autoSkipped || failed ? 'error' : 'success'
        );
        return;
    }

    renderBatchAIQueue();
    await processCurrentBatchAIItem();
}

async function skipCurrentBatchAIItem() {
    const item = getCurrentBatchAIItem();
    if (!item || batchAIState.isGenerating || batchAIState.isApplying) {
        return;
    }

    syncBatchAIInputsToCurrentItem();
    item.status = 'skipped';
    await advanceBatchAIQueue();
}

async function applyCurrentBatchAIItem() {
    const item = getCurrentBatchAIItem();
    if (!item || item.status !== 'generated' || batchAIState.isGenerating || batchAIState.isApplying) {
        return;
    }

    syncBatchAIInputsToCurrentItem();
    batchAIState.isApplying = true;
    renderBatchAIQueue();

    const description = item.applySummary ? item.generatedSummary : (item.novel.description || '');
    const tagIds = item.applyTags ? item.selectedTagIds : item.originalTagIds;

    try {
        const res = await api.put(`/api/novels/${item.id}`, {
            title: item.novel.title,
            author: item.novel.author,
            description,
            file_path: item.novel.file_path,
            category_id: item.novel.category_id,
            status: item.novel.status,
            tag_ids: tagIds
        });

        if (!res.success) {
            throw new Error(res.message || '保存失败');
        }

        item.novel.description = description;
        item.originalTagIds = [...tagIds];
        item.novel.tags = state.tags
            .filter(tag => tagIds.includes(tag.id))
            .map(tag => ({ id: tag.id, name: tag.name, color: tag.color }));
        item.status = 'applied';

        const stateNovel = state.novels.find(novel => novel.id === item.id);
        if (stateNovel) {
            stateNovel.description = description;
            stateNovel.tags = item.novel.tags.map(tag => ({ ...tag }));
        }

        batchAIState.isApplying = false;
        await advanceBatchAIQueue();
    } catch (err) {
        batchAIState.isApplying = false;
        item.status = 'generated';
        item.error = err.message;
        renderBatchAIQueue();
        showToast(`《${item.novel.title}》保存失败：${err.message}`, 'error');
        return;
    }
}

// 事件绑定
