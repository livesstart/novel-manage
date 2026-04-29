const readerState = {
    novelId: null,
    chapters: [],
    currentChapter: 0,
    fontSize: 18,
    darkTheme: false,
    progressSaveTimer: null,
    isRestoringProgress: false
};

async function openReader(novelId) {
    readerState.novelId = novelId;
    readerState.currentChapter = 0;
    if (readerState.progressSaveTimer) {
        clearTimeout(readerState.progressSaveTimer);
        readerState.progressSaveTimer = null;
    }

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
            const readingProgress = data.reading_progress || {};
            const startChapterIndex = normalizeReaderChapterIndex(
                readingProgress.chapter_index,
                data.chapters.length
            );
            readerState.currentChapter = startChapterIndex;

            // 更新小说标题
            document.getElementById('reader-novel-title').textContent = data.novel.title;

            // 更新章节数量
            document.getElementById('reader-toc-count').textContent = `${data.chapters.length}章`;

            // 渲染目录
            renderTOC();

            // 加载上次阅读位置
            await loadChapter(startChapterIndex, {
                scrollPercent: readingProgress.scroll_percent,
                skipSave: true
            });
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

function normalizeReaderChapterIndex(value, chapterCount) {
    const parsed = parseInt(value, 10);
    if (!Number.isFinite(parsed)) return 0;
    return Math.max(0, Math.min(parsed, Math.max(chapterCount - 1, 0)));
}

function calculateReaderScrollPercent() {
    const content = document.getElementById('reader-content');
    const maxScroll = content.scrollHeight - content.clientHeight;
    if (maxScroll <= 0) return 0;
    return Math.max(0, Math.min((content.scrollTop / maxScroll) * 100, 100));
}

function restoreReaderScrollPercent(scrollPercent) {
    const content = document.getElementById('reader-content');
    const percent = Math.max(0, Math.min(Number(scrollPercent) || 0, 100));
    const maxScroll = content.scrollHeight - content.clientHeight;

    readerState.isRestoringProgress = true;
    content.scrollTop = maxScroll > 0 ? (maxScroll * percent) / 100 : 0;

    setTimeout(() => {
        readerState.isRestoringProgress = false;
    }, 0);
}

function scheduleSaveReadingProgress(delayMs = 800) {
    if (!readerState.novelId || readerState.isRestoringProgress) return;

    if (readerState.progressSaveTimer) {
        clearTimeout(readerState.progressSaveTimer);
    }

    readerState.progressSaveTimer = setTimeout(() => {
        saveReadingProgressNow();
    }, delayMs);
}

async function saveReadingProgressNow() {
    if (!readerState.novelId) return;

    if (readerState.progressSaveTimer) {
        clearTimeout(readerState.progressSaveTimer);
        readerState.progressSaveTimer = null;
    }

    try {
        await api.put(`/api/novels/${readerState.novelId}/reading-progress`, {
            chapter_index: readerState.currentChapter,
            scroll_percent: Number(calculateReaderScrollPercent().toFixed(2))
        });
    } catch (err) {
        console.warn('保存阅读进度失败:', err);
    }
}

async function loadChapter(index, options = {}) {
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

            if (Number.isFinite(Number(options.scrollPercent)) && Number(options.scrollPercent) > 0) {
                restoreReaderScrollPercent(options.scrollPercent);
            } else {
                document.getElementById('reader-content').scrollTop = 0;
            }

            if (!options.skipSave) {
                scheduleSaveReadingProgress(0);
            }
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
