const READER_SETTINGS_STORAGE_KEY = 'novel-manager-reader-settings';

const READER_DEFAULT_SETTINGS = {
    fontSize: 19,
    lineHeight: 1.9,
    width: 1000,
    paragraphSpacing: 1,
    theme: 'light'
};

const READER_THEMES = ['light', 'sepia', 'green', 'dark'];
const READER_REQUEST_TIMEOUT_MS = 30000;

const readerState = {
    novelId: null,
    chapters: [],
    currentChapter: 0,
    fontSize: READER_DEFAULT_SETTINGS.fontSize,
    darkTheme: false,
    settings: loadReaderSettings(),
    currentChapterContent: '',
    searchQuery: '',
    searchActiveIndex: -1,
    searchResultCount: 0,
    isSearchOpen: false,
    progressSaveTimer: null,
    isRestoringProgress: false,
    isSettingsOpen: false,
    isTocOpen: true,
    isImmersive: false
};

function clampReaderNumber(value, min, max, fallback) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return fallback;
    return Math.max(min, Math.min(parsed, max));
}

function normalizeReaderSettings(settings = {}) {
    const theme = READER_THEMES.includes(settings.theme) ? settings.theme : READER_DEFAULT_SETTINGS.theme;

    return {
        fontSize: clampReaderNumber(settings.fontSize, 14, 32, READER_DEFAULT_SETTINGS.fontSize),
        lineHeight: clampReaderNumber(settings.lineHeight, 1.4, 2.4, READER_DEFAULT_SETTINGS.lineHeight),
        width: clampReaderNumber(settings.width, 620, 1280, READER_DEFAULT_SETTINGS.width),
        paragraphSpacing: clampReaderNumber(settings.paragraphSpacing, 0.6, 1.8, READER_DEFAULT_SETTINGS.paragraphSpacing),
        theme
    };
}

function loadReaderSettings() {
    try {
        const saved = localStorage.getItem(READER_SETTINGS_STORAGE_KEY);
        if (!saved) return { ...READER_DEFAULT_SETTINGS };
        return normalizeReaderSettings(JSON.parse(saved));
    } catch (err) {
        console.warn('读取阅读器设置失败:', err);
        return { ...READER_DEFAULT_SETTINGS };
    }
}

function saveReaderSettings() {
    try {
        localStorage.setItem(READER_SETTINGS_STORAGE_KEY, JSON.stringify(readerState.settings));
    } catch (err) {
        console.warn('保存阅读器设置失败:', err);
    }
}

function syncReaderSettingsControls() {
    const settings = readerState.settings;
    const controlMap = {
        'reader-theme-select': settings.theme,
        'reader-font-size': settings.fontSize,
        'reader-line-height': settings.lineHeight,
        'reader-width': settings.width,
        'reader-spacing': settings.paragraphSpacing
    };

    Object.entries(controlMap).forEach(([id, value]) => {
        const control = document.getElementById(id);
        if (control) control.value = String(value);
    });

    const valueMap = {
        'reader-font-size-value': settings.fontSize,
        'reader-line-height-value': settings.lineHeight.toFixed(1),
        'reader-width-value': settings.width,
        'reader-spacing-value': settings.paragraphSpacing.toFixed(1)
    };

    Object.entries(valueMap).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    });
}

function applyReaderSettings(options = {}) {
    readerState.settings = normalizeReaderSettings(readerState.settings);
    readerState.fontSize = readerState.settings.fontSize;
    readerState.darkTheme = readerState.settings.theme === 'dark';

    const modal = document.getElementById('reader-modal');
    const text = document.getElementById('reader-text');
    if (modal) {
        READER_THEMES.forEach(theme => modal.classList.remove(`theme-${theme}`));
        modal.classList.add(`theme-${readerState.settings.theme}`);
        modal.classList.toggle('dark-theme', readerState.darkTheme);
    }

    if (text) {
        text.style.fontSize = `${readerState.settings.fontSize}px`;
        text.style.lineHeight = String(readerState.settings.lineHeight);
        text.style.maxWidth = `${readerState.settings.width}px`;
        text.style.setProperty('--reader-paragraph-spacing', `${readerState.settings.paragraphSpacing}em`);
    }

    const themeIcon = document.querySelector('#reader-theme-toggle i');
    if (themeIcon) {
        themeIcon.className = readerState.darkTheme ? 'fas fa-sun' : 'fas fa-moon';
    }

    syncReaderSettingsControls();
    updateReaderViewportProgress();

    if (options.persist) {
        saveReaderSettings();
    }
}

function updateReaderSettingsFromControls() {
    readerState.settings = normalizeReaderSettings({
        theme: document.getElementById('reader-theme-select').value,
        fontSize: document.getElementById('reader-font-size').value,
        lineHeight: document.getElementById('reader-line-height').value,
        width: document.getElementById('reader-width').value,
        paragraphSpacing: document.getElementById('reader-spacing').value
    });

    applyReaderSettings({ persist: true });
}

function setReaderSetting(key, value) {
    readerState.settings = normalizeReaderSettings({
        ...readerState.settings,
        [key]: value
    });
    applyReaderSettings({ persist: true });
}

async function fetchReaderJson(url, options = {}) {
    const timeoutMs = options.timeoutMs || READER_REQUEST_TIMEOUT_MS;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(url, { signal: controller.signal });
        const payload = await response.json();
        if (!response.ok && payload && typeof payload === 'object') {
            return payload;
        }
        return payload;
    } catch (err) {
        if (err.name === 'AbortError') {
            throw new Error('加载超时，请稍后重试');
        }
        throw err;
    } finally {
        window.clearTimeout(timeoutId);
    }
}

function showReaderLoadingState() {
    document.getElementById('reader-loading').classList.remove('hidden');
    document.getElementById('reader-text').classList.add('hidden');
    document.getElementById('reader-empty').classList.add('hidden');
}

function showReaderEmptyState(message) {
    document.getElementById('reader-loading').classList.add('hidden');
    document.getElementById('reader-text').classList.add('hidden');
    document.getElementById('reader-empty').classList.remove('hidden');
    document.querySelector('#reader-empty p').textContent = message || '无法加载小说';
}

function countReaderSearchMatches(text, query) {
    if (!query) return 0;

    const source = String(text || '').toLocaleLowerCase();
    const needle = String(query).toLocaleLowerCase();
    let count = 0;
    let offset = 0;

    while (needle && offset < source.length) {
        const index = source.indexOf(needle, offset);
        if (index === -1) break;
        count += 1;
        offset = index + needle.length;
    }

    return count;
}

function buildReaderSearchHighlightedHtml(text, query, context) {
    if (!query) {
        return escapeHtml(text);
    }

    const source = String(text || '');
    const lowerSource = source.toLocaleLowerCase();
    const needle = String(query).toLocaleLowerCase();
    let offset = 0;
    let html = '';

    while (needle && offset < source.length) {
        const index = lowerSource.indexOf(needle, offset);
        if (index === -1) break;

        html += escapeHtml(source.slice(offset, index));
        const matchIndex = context.index;
        const activeClass = matchIndex === readerState.searchActiveIndex ? ' active' : '';
        html += `<mark class="reader-search-hit${activeClass}" data-reader-search-index="${matchIndex}">${escapeHtml(source.slice(index, index + needle.length))}</mark>`;
        context.index += 1;
        offset = index + needle.length;
    }

    html += escapeHtml(source.slice(offset));
    return html;
}

function syncReaderSearchControls() {
    const input = document.getElementById('reader-search-input');
    const count = document.getElementById('reader-search-count');
    const prev = document.getElementById('reader-search-prev');
    const next = document.getElementById('reader-search-next');
    const toggle = document.getElementById('reader-search-toggle');
    const hasQuery = Boolean(readerState.searchQuery);
    const hasResults = readerState.searchResultCount > 0;

    if (input && input.value !== readerState.searchQuery) {
        input.value = readerState.searchQuery;
    }

    if (count) {
        if (!hasQuery) {
            count.textContent = '0 / 0';
        } else if (hasResults) {
            count.textContent = `${readerState.searchActiveIndex + 1} / ${readerState.searchResultCount}`;
        } else {
            count.textContent = '未找到';
        }
    }

    if (prev) prev.disabled = !hasResults;
    if (next) next.disabled = !hasResults;
    if (toggle) toggle.setAttribute('aria-expanded', String(readerState.isSearchOpen));
}

function renderReaderContentWithSearch(options = {}) {
    const contentDiv = document.getElementById('reader-text');
    const content = readerState.currentChapterContent || '';
    const query = readerState.searchQuery.trim();
    const scrollContainer = document.getElementById('reader-content');
    const previousScrollTop = scrollContainer ? scrollContainer.scrollTop : 0;

    readerState.searchResultCount = countReaderSearchMatches(content, query);
    if (!query || readerState.searchResultCount === 0) {
        readerState.searchActiveIndex = -1;
    } else if (readerState.searchActiveIndex < 0 || readerState.searchActiveIndex >= readerState.searchResultCount) {
        readerState.searchActiveIndex = 0;
    }

    const context = { index: 0 };
    const paragraphs = content.split('\n')
        .filter(line => line.trim())
        .map(line => `<p>${buildReaderSearchHighlightedHtml(line, query, context)}</p>`)
        .join('');

    contentDiv.innerHTML = paragraphs || '<p>本章暂无内容</p>';
    syncReaderSearchControls();

    if (options.preserveScroll && scrollContainer) {
        scrollContainer.scrollTop = previousScrollTop;
        updateReaderViewportProgress();
    }
}

function scrollReaderSearchHit() {
    if (readerState.searchActiveIndex < 0) return;

    requestAnimationFrame(() => {
        const hit = document.querySelector(`.reader-search-hit[data-reader-search-index="${readerState.searchActiveIndex}"]`);
        if (hit) {
            hit.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });
}

function updateReaderSearchFromInput() {
    const input = document.getElementById('reader-search-input');
    const query = (input?.value || '').trim();
    if (query === readerState.searchQuery) return;

    readerState.searchQuery = query;
    readerState.searchActiveIndex = query ? 0 : -1;
    renderReaderContentWithSearch({ preserveScroll: true });
    applyReaderSettings();

    if (readerState.searchResultCount > 0) {
        scrollReaderSearchHit();
    }
}

function moveReaderSearchResult(direction) {
    if (readerState.searchResultCount <= 0) return;

    readerState.searchActiveIndex =
        (readerState.searchActiveIndex + direction + readerState.searchResultCount) % readerState.searchResultCount;
    renderReaderContentWithSearch({ preserveScroll: true });
    applyReaderSettings();
    scrollReaderSearchHit();
}

function clearReaderSearch() {
    readerState.searchQuery = '';
    readerState.searchActiveIndex = -1;
    readerState.searchResultCount = 0;
    renderReaderContentWithSearch({ preserveScroll: true });
    applyReaderSettings();
    document.getElementById('reader-search-input')?.focus();
}

function openReaderSearchPanel() {
    const panel = document.getElementById('reader-search-panel');
    readerState.isSearchOpen = true;
    closeReaderSettingsPanel();
    if (panel) panel.classList.remove('hidden');
    syncReaderSearchControls();
    document.getElementById('reader-search-input')?.focus();
}

function closeReaderSearchPanel() {
    const panel = document.getElementById('reader-search-panel');
    readerState.isSearchOpen = false;
    if (panel) panel.classList.add('hidden');
    syncReaderSearchControls();
}

function toggleReaderSearchPanel() {
    if (readerState.isSearchOpen) {
        closeReaderSearchPanel();
    } else {
        openReaderSearchPanel();
    }
}

async function openReader(novelId) {
    readerState.novelId = novelId;
    readerState.currentChapter = 0;
    readerState.currentChapterContent = '';
    readerState.searchQuery = '';
    readerState.searchActiveIndex = -1;
    readerState.searchResultCount = 0;
    readerState.isSearchOpen = false;
    readerState.settings = loadReaderSettings();
    readerState.isImmersive = false;
    if (readerState.progressSaveTimer) {
        clearTimeout(readerState.progressSaveTimer);
        readerState.progressSaveTimer = null;
    }

    openModal('reader-modal');
    applyReaderSettings();
    closeReaderSearchPanel();
    closeReaderSettingsPanel();
    setReaderImmersiveMode(false);
    syncReaderResponsiveState();

    showReaderLoadingState();
    updateReaderViewportProgress();

    try {
        const res = await fetchReaderJson(`/api/novels/${novelId}/read`);

        if (res.success) {
            const data = res.data;
            readerState.chapters = data.chapters;
            if (!readerState.chapters.length) {
                renderTOC();
                showReaderEmptyState('未识别到可阅读内容');
                return;
            }

            const readingProgress = data.reading_progress || {};
            const startChapterIndex = normalizeReaderChapterIndex(
                readingProgress.chapter_index,
                data.chapters.length
            );
            readerState.currentChapter = startChapterIndex;

            document.getElementById('reader-novel-title').textContent = data.novel.title;
            document.getElementById('reader-toc-count').textContent = `${data.chapters.length}章`;

            renderTOC();
            if (data.initial_chapter && data.initial_chapter.index === startChapterIndex) {
                renderReaderChapter(data.initial_chapter, startChapterIndex, {
                    scrollPercent: readingProgress.scroll_percent,
                    skipSave: true
                });
            } else {
                await loadChapter(startChapterIndex, {
                    scrollPercent: readingProgress.scroll_percent,
                    skipSave: true
                });
            }
        } else {
            showReaderEmptyState(res.message || '无法加载小说');

            if (res.data && res.data.chapters) {
                readerState.chapters = res.data.chapters;
                renderTOC();
            }
        }
    } catch (err) {
        console.error('加载小说失败:', err);
        showReaderEmptyState('加载失败: ' + err.message);
    }
}

function renderTOC() {
    const container = document.getElementById('reader-toc');

    if (readerState.chapters.length === 0) {
        container.innerHTML = '<div class="reader-toc-empty">未识别到章节</div>';
        return;
    }

    container.innerHTML = readerState.chapters.map((chapter, index) => `
        <div class="toc-item ${index === readerState.currentChapter ? 'active' : ''}"
             data-index="${index}"
             title="${escapeHtml(chapter.title)}"
             onclick="loadChapter(${index}); closeReaderTocOnCompact();">
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

function updateReaderViewportProgress() {
    const percent = calculateReaderScrollPercent();
    const fill = document.getElementById('reader-progress-fill');
    const label = document.getElementById('reader-scroll-percent');

    if (fill) {
        fill.style.width = `${percent}%`;
    }

    if (label) {
        label.textContent = `${Math.round(percent)}%`;
    }
}

function restoreReaderScrollPercent(scrollPercent) {
    const content = document.getElementById('reader-content');
    const percent = Math.max(0, Math.min(Number(scrollPercent) || 0, 100));
    const maxScroll = content.scrollHeight - content.clientHeight;

    readerState.isRestoringProgress = true;
    content.scrollTop = maxScroll > 0 ? (maxScroll * percent) / 100 : 0;
    updateReaderViewportProgress();

    setTimeout(() => {
        readerState.isRestoringProgress = false;
        updateReaderViewportProgress();
    }, 0);
}

function scheduleSaveReadingProgress(delayMs = 800) {
    updateReaderViewportProgress();
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

function renderReaderChapter(chapter, index, options = {}) {
    readerState.currentChapter = index;
    readerState.currentChapterContent = chapter.content || '';
    if (readerState.searchQuery) {
        readerState.searchActiveIndex = 0;
    }

    document.getElementById('reader-chapter-title').textContent = chapter.title;
    renderReaderContentWithSearch();

    document.getElementById('reader-progress').textContent =
        `${index + 1} / ${chapter.total_chapters}`;

    document.getElementById('reader-prev-chapter').disabled = index === 0;
    document.getElementById('reader-next-chapter').disabled =
        index >= chapter.total_chapters - 1;

    document.getElementById('reader-loading').classList.add('hidden');
    document.getElementById('reader-empty').classList.add('hidden');
    document.getElementById('reader-text').classList.remove('hidden');
    applyReaderSettings();

    if (Number.isFinite(Number(options.scrollPercent)) && Number(options.scrollPercent) > 0) {
        restoreReaderScrollPercent(options.scrollPercent);
    } else {
        document.getElementById('reader-content').scrollTop = 0;
        updateReaderViewportProgress();
    }

    if (!options.skipSave) {
        scheduleSaveReadingProgress(0);
    }
}

async function loadChapter(index, options = {}) {
    if (index < 0 || index >= readerState.chapters.length) return;

    readerState.currentChapter = index;

    document.querySelectorAll('.toc-item').forEach((item, i) => {
        item.classList.toggle('active', i === index);
    });

    const activeItem = document.querySelector('.toc-item.active');
    if (activeItem) {
        activeItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    showReaderLoadingState();

    try {
        const res = await fetchReaderJson(`/api/novels/${readerState.novelId}/chapters/${index}`);

        if (res.success) {
            const chapter = res.data.chapter;
            renderReaderChapter(chapter, index, options);
        } else {
            showReaderEmptyState(res.message || '章节加载失败');
        }
    } catch (err) {
        console.error('加载章节失败:', err);
        showReaderEmptyState('章节加载失败: ' + err.message);
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

function scrollReaderByPage(direction) {
    const content = document.getElementById('reader-content');
    const maxScroll = Math.max(content.scrollHeight - content.clientHeight, 0);
    const distance = Math.max(Math.floor(content.clientHeight * 0.86), 240) * direction;
    const nearTop = content.scrollTop <= 4;
    const nearBottom = content.scrollTop >= maxScroll - 4;

    if (direction > 0 && nearBottom) {
        nextChapter();
        return;
    }

    if (direction < 0 && nearTop && readerState.currentChapter > 0) {
        loadChapter(readerState.currentChapter - 1, { scrollPercent: 100 });
        return;
    }

    content.scrollBy({ top: distance, behavior: 'smooth' });
    window.setTimeout(updateReaderViewportProgress, 220);
}

function increaseFontSize() {
    setReaderSetting('fontSize', readerState.settings.fontSize + 1);
}

function decreaseFontSize() {
    setReaderSetting('fontSize', readerState.settings.fontSize - 1);
}

function toggleReaderTheme() {
    const nextTheme = readerState.settings.theme === 'dark' ? 'light' : 'dark';
    setReaderSetting('theme', nextTheme);
}

function toggleReaderSettingsPanel() {
    const panel = document.getElementById('reader-settings-panel');
    const button = document.getElementById('reader-settings-toggle');
    readerState.isSettingsOpen = !readerState.isSettingsOpen;

    if (readerState.isSettingsOpen) {
        closeReaderSearchPanel();
    }

    panel.classList.toggle('hidden', !readerState.isSettingsOpen);
    button.setAttribute('aria-expanded', String(readerState.isSettingsOpen));
}

function closeReaderSettingsPanel() {
    const panel = document.getElementById('reader-settings-panel');
    const button = document.getElementById('reader-settings-toggle');
    readerState.isSettingsOpen = false;

    if (panel) panel.classList.add('hidden');
    if (button) button.setAttribute('aria-expanded', 'false');
}

function isReaderCompactViewport() {
    return window.matchMedia('(max-width: 768px)').matches;
}

function setReaderTocOpen(open) {
    const modal = document.getElementById('reader-modal');
    const sidebar = document.querySelector('#reader-modal .reader-sidebar');
    const button = document.getElementById('reader-toc-toggle');
    const compact = isReaderCompactViewport();

    readerState.isTocOpen = open;
    if (sidebar) sidebar.classList.toggle('open', open);
    if (modal) modal.classList.toggle('toc-collapsed', !compact && !open);
    if (button) button.setAttribute('aria-pressed', String(open));
}

function toggleReaderToc() {
    setReaderTocOpen(!readerState.isTocOpen);
}

function closeReaderTocOnCompact() {
    if (isReaderCompactViewport()) {
        setReaderTocOpen(false);
    }
}

function syncReaderResponsiveState() {
    setReaderTocOpen(!isReaderCompactViewport());
}

function setReaderImmersiveMode(enabled) {
    const modal = document.getElementById('reader-modal');
    const button = document.getElementById('reader-immersive-toggle');
    const icon = document.querySelector('#reader-immersive-toggle i');

    readerState.isImmersive = enabled;
    modal.classList.toggle('immersive', readerState.isImmersive);
    button.setAttribute('aria-pressed', String(readerState.isImmersive));
    if (icon) {
        icon.className = readerState.isImmersive ? 'fas fa-compress' : 'fas fa-expand';
    }

    if (readerState.isImmersive) {
        closeReaderSearchPanel();
        closeReaderSettingsPanel();
    }
}

function toggleReaderImmersiveMode() {
    setReaderImmersiveMode(!readerState.isImmersive);
}

// ==================== 下载功能 ====================
