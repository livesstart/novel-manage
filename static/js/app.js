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
    let characterSearchTimeout;
    document.getElementById('search-input').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            applyFilters();
        }, 300);
    });

    document.getElementById('character-library-search').addEventListener('input', (e) => {
        clearTimeout(characterSearchTimeout);
        characterSearchTimeout = setTimeout(() => {
            loadCharacterLibrary({ keyword: e.target.value.trim() });
        }, 300);
    });
    document.getElementById('character-library-novel-filter').addEventListener('change', (e) => {
        loadCharacterLibrary({ novelId: e.target.value });
    });
    document.getElementById('character-library-role-filter').addEventListener('change', (e) => {
        loadCharacterLibrary({ roleType: e.target.value });
    });
    document.getElementById('character-library-tag-filter').addEventListener('input', (e) => {
        loadCharacterLibrary({ tag: e.target.value.trim() });
    });
    document.getElementById('character-library-sort').addEventListener('change', (e) => {
        loadCharacterLibrary({ sort: e.target.value });
    });
    document.getElementById('btn-character-create').addEventListener('click', () => openCharacterDrawer(null));
    document.getElementById('btn-character-ai-generate').addEventListener('click', generateCharacterCardsForCurrentNovel);
    document.getElementById('btn-character-save').addEventListener('click', saveCharacter);
    document.getElementById('btn-character-delete').addEventListener('click', deleteCharacter);
    document.getElementById('btn-character-ai-complete').addEventListener('click', completeCharacterWithAI);
    document.getElementById('btn-character-relation-save').addEventListener('click', saveCharacterRelation);
    document.getElementById('btn-character-drawer-close').addEventListener('click', closeCharacterDrawer);
    document.getElementById('character-novel-id').addEventListener('change', (e) => {
        refreshCharacterRelationTargets(e.target.value, Number(document.getElementById('character-id').value || 0));
    });
    // 筛选器
    document.getElementById('filter-category').addEventListener('change', applyFilters);
    document.getElementById('filter-status').addEventListener('change', applyFilters);
    document.getElementById('filter-tag-search').addEventListener('input', (e) => {
        state.filterTagQuery = e.target.value;
        updateTagSelectors();
    });
    document.getElementById('filter-tag-search').addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            state.filterTagQuery = '';
            e.target.value = '';
            updateTagSelectors();
        }
    });
    document.getElementById('filter-tags-toggle').addEventListener('click', toggleFilterTagsPanel);
    document.getElementById('filter-tags-clear').addEventListener('click', clearSelectedFilterTags);
    document.getElementById('filter-untagged-only').addEventListener('change', () => {
        if (document.getElementById('filter-untagged-only').checked) {
            state.filterTagQuery = '';
            state.filterTagsExpanded = false;
        }
        updateTagSelectors();
        applyFilters();
    });

    // 添加小说按钮
    document.getElementById('btn-add-novel').addEventListener('click', () => {
        resetNovelModal();
        openModal('novel-modal');
    });

    // 保存小说
    document.getElementById('btn-save-novel').addEventListener('click', saveNovel);

    // AI 生成小说简介与标签
    document.getElementById('btn-ai-generate-novel-meta').addEventListener('click', generateNovelMetadataWithAI);

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
            document.getElementById('novel-file-path').value = `待上传：${file.name}`;
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

    document.getElementById('btn-batch-ai-empty-description').addEventListener('click', openBatchAIForEmptyDescriptions);

    document.getElementById('btn-batch-ai-meta').addEventListener('click', openBatchAIModal);

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

    // 批量 AI 队列操作
    document.getElementById('btn-batch-ai-regenerate').addEventListener('click', () => {
        processCurrentBatchAIItem(true);
    });
    document.getElementById('btn-batch-ai-auto-apply').addEventListener('click', toggleBatchAIAutoApply);
    document.getElementById('btn-batch-ai-skip').addEventListener('click', skipCurrentBatchAIItem);
    document.getElementById('btn-batch-ai-apply-next').addEventListener('click', applyCurrentBatchAIItem);
    document.getElementById('batch-ai-auto-skip-error').addEventListener('change', syncBatchAIModeSettings);
    document.getElementById('batch-ai-generated-summary').addEventListener('input', syncBatchAIInputsToCurrentItem);
    document.getElementById('batch-ai-apply-summary').addEventListener('change', syncBatchAIInputsToCurrentItem);
    document.getElementById('batch-ai-apply-tags').addEventListener('change', syncBatchAIInputsToCurrentItem);

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
                        relative_path: relativePath,
                        title: title,
                        category_name: categoryName,
                        selected: true,
                        file_size: file.size,
                        file: file
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
        saveReadingProgressNow();
        closeModal('reader-modal');
    });

    // 上一章/下一章
    document.getElementById('reader-prev-chapter').addEventListener('click', prevChapter);
    document.getElementById('reader-next-chapter').addEventListener('click', nextChapter);
    document.getElementById('reader-content').addEventListener('scroll', scheduleSaveReadingProgress);
    window.addEventListener('resize', syncReaderResponsiveState);

    // 字体大小调整
    document.getElementById('reader-font-increase').addEventListener('click', increaseFontSize);
    document.getElementById('reader-font-decrease').addEventListener('click', decreaseFontSize);

    // 主题切换
    document.getElementById('reader-theme-toggle').addEventListener('click', toggleReaderTheme);
    document.getElementById('reader-theme-select').addEventListener('change', updateReaderSettingsFromControls);
    document.getElementById('reader-font-size').addEventListener('input', updateReaderSettingsFromControls);
    document.getElementById('reader-line-height').addEventListener('input', updateReaderSettingsFromControls);
    document.getElementById('reader-width').addEventListener('input', updateReaderSettingsFromControls);
    document.getElementById('reader-spacing').addEventListener('input', updateReaderSettingsFromControls);
    document.getElementById('reader-settings-toggle').addEventListener('click', toggleReaderSettingsPanel);
    document.getElementById('reader-immersive-toggle').addEventListener('click', toggleReaderImmersiveMode);
    document.getElementById('reader-immersive-exit').addEventListener('click', () => setReaderImmersiveMode(false));
    document.getElementById('reader-toc-toggle').addEventListener('click', toggleReaderToc);

    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
        // 只在阅读器打开时生效
        if (!document.getElementById('reader-modal').classList.contains('active')) return;

        if (e.key === 'Escape') {
            if (readerState.isImmersive) {
                setReaderImmersiveMode(false);
                return;
            }

            if (!['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(e.target.tagName)) {
                saveReadingProgressNow();
                closeModal('reader-modal');
            }
            return;
        }

        if (['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(e.target.tagName)) return;

        switch(e.key) {
            case 'ArrowLeft':
                e.preventDefault();
                prevChapter();
                break;
            case 'ArrowRight':
                e.preventDefault();
                nextChapter();
                break;
            case ' ':
            case 'PageDown':
                e.preventDefault();
                scrollReaderByPage(1);
                break;
            case 'PageUp':
                e.preventDefault();
                scrollReaderByPage(-1);
                break;
        }
    });

    // ==================== 爬虫管理事件绑定 ====================

    // 新建爬虫任务
    document.getElementById('btn-add-crawler-task').addEventListener('click', openAddCrawlerTaskModal);
    document.getElementById('btn-add-crawler-rule').addEventListener('click', openAddCrawlerRuleModal);
    document.getElementById('btn-add-crawler-rule-inline').addEventListener('click', openAddCrawlerRuleModal);

    // 保存爬虫任务
    document.getElementById('btn-save-crawler-task').addEventListener('click', saveCrawlerTask);
    document.getElementById('btn-save-crawler-rule').addEventListener('click', saveCrawlerRule);

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

    // 选择已发现模型时，同步回模型输入框
    document.getElementById('ai-discovered-models').addEventListener('change', (e) => {
        if (e.target.value) {
            document.getElementById('ai-config-model').value = e.target.value;
        }
    });

    // 提供商选择变化时更新提示
    document.getElementById('ai-config-provider').addEventListener('change', (e) => {
        updateProviderHint(e.target.value);
    });

    document.getElementById('ai-config-use-proxy').addEventListener('change', updateAIProxyFields);

    // AI 聊天测试
    document.getElementById('btn-ai-send').addEventListener('click', sendChatMessage);
    document.getElementById('ai-chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    bindAdminEvents();
}

// ==================== 批量导入功能 ====================

document.addEventListener('DOMContentLoaded', init);
