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
                   onchange="toggleImportNovelSelection(${index}, this.checked)">
            <div class="import-novel-info">
                <div class="import-novel-title">${escapeHtml(novel.title)}</div>
                <div class="import-novel-meta">${formatFileSize(novel.file_size)} · ${escapeHtml(novel.file_path)}</div>
            </div>
            ${novel.category_name ? `<span class="import-novel-category">${escapeHtml(novel.category_name)}</span>` : ''}
        </div>
    `).join('');
}

function toggleImportNovelSelection(index, selected) {
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
        const formData = new FormData();
        const novels = selectedNovels.map(n => ({
            title: n.title,
            author: n.author || '',
            file_path: n.file_path,
            category_name: createCategories ? n.category_name : null,
            selected: true,
            file_size: n.file_size
        }));

        selectedNovels.forEach(novel => {
            formData.append('files', novel.file, novel.file.name);
            formData.append('relative_paths', novel.relative_path || novel.file_path);
        });

        formData.append('novels', JSON.stringify(novels));
        formData.append('tag_ids', JSON.stringify(tagIds));
        formData.append('default_status', String(defaultStatus));

        const res = await api.postForm('/api/import/batch', formData);

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
