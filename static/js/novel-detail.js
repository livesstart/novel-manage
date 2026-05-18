// ????????????????????

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

function switchNovelDetailTab(tabName) {
    const targetTab = tabName || 'overview';
    document.querySelectorAll('.novel-detail-tab').forEach(tab => {
        const isActive = tab.dataset.detailTab === targetTab;
        tab.classList.toggle('active', isActive);
        tab.setAttribute('aria-selected', String(isActive));
    });

    document.querySelectorAll('.novel-detail-panel').forEach(panel => {
        const isActive = panel.dataset.detailPanel === targetTab;
        panel.classList.toggle('active', isActive);
        panel.hidden = !isActive;
    });
}

function resetNovelCharacterAnalysis() {
    state.detailCharacterAnalysis = null;
    document.getElementById('novel-character-status').textContent = '尚未生成角色卡';
    document.getElementById('novel-character-status').className = '';
    document.getElementById('novel-character-list').innerHTML = '<div class="novel-character-empty">暂无角色卡数据</div>';
    document.getElementById('novel-character-graph').innerHTML = '<div class="novel-character-empty">生成后会展示关系谱</div>';
    document.getElementById('novel-character-relations').innerHTML = '';
}

function resetNovelSettingAnalysis() {
    state.detailSettingAnalysis = null;
    document.getElementById('novel-setting-status').textContent = '尚未提取小说设定';
    document.getElementById('novel-setting-status').className = '';
    document.getElementById('novel-setting-list').innerHTML = '<div class="novel-setting-empty">暂无小说设定数据</div>';
}

function renderNovelSettingAnalysis(analysis) {
    state.detailSettingAnalysis = analysis;
    const settings = Array.isArray(analysis?.settings) ? analysis.settings : [];
    const status = analysis?.analysis_status || 'empty';
    const statusEl = document.getElementById('novel-setting-status');

    if (status === 'failed') {
        statusEl.textContent = analysis.error_message || '上次提取失败';
        statusEl.className = 'failed';
    } else if (settings.length > 0) {
        statusEl.textContent = `已提取 ${settings.length} 条小说设定`;
        statusEl.className = 'completed';
    } else {
        statusEl.textContent = '尚未提取小说设定';
        statusEl.className = '';
    }

    const list = document.getElementById('novel-setting-list');
    if (settings.length === 0) {
        list.innerHTML = '<div class="novel-setting-empty">暂无小说设定数据</div>';
        return;
    }

    list.innerHTML = settings.map(setting => `
        <article class="novel-setting-card">
            <div class="novel-setting-card-head">
                <strong>${escapeHtml(setting.name || '未命名设定')}</strong>
                <span>${escapeHtml(setting.category || '其他')}</span>
            </div>
            <p class="novel-setting-summary">${escapeHtml(setting.summary || '暂无概要')}</p>
            ${setting.details ? `<p class="novel-setting-details">${escapeHtml(setting.details)}</p>` : ''}
            <div class="novel-setting-evidence">${escapeHtml(setting.evidence || '暂无证据片段')}</div>
            <div class="novel-setting-confidence">可信度 ${formatConfidence(setting.confidence)}</div>
        </article>
    `).join('');
}

async function loadNovelSettingAnalysis(novelId) {
    try {
        const res = await api.get(`/api/novels/${novelId}/settings`);
        if (!res.success) {
            document.getElementById('novel-setting-status').textContent = res.message || '小说设定数据加载失败';
            return;
        }
        renderNovelSettingAnalysis(res.data);
    } catch (err) {
        console.warn('加载小说设定数据失败:', err);
        document.getElementById('novel-setting-status').textContent = '小说设定数据加载失败';
    }
}

async function analyzeNovelSettingsWithAI(novelId) {
    const button = document.getElementById('btn-detail-analyze-settings');
    const originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="loading"></span> 提取中';
    document.getElementById('novel-setting-status').textContent = 'AI 正在提取小说设定...';

    try {
        const res = await api.post(`/api/ai/novels/${novelId}/settings/analyze`, {});
        if (!res.success) {
            showToast(res.message || '小说设定提取失败', 'error');
            await loadNovelSettingAnalysis(novelId);
            return;
        }

        renderNovelSettingAnalysis(res.data);
        switchNovelDetailTab('settings');
        showToast(`已提取 ${res.data.setting_count} 条小说设定`, 'success');
    } catch (err) {
        console.error('AI 提取小说设定失败:', err);
        showToast('AI 提取小说设定失败: ' + err.message, 'error');
    } finally {
        button.disabled = false;
        button.innerHTML = originalHtml;
    }
}

function resetNovelWritingStyleAnalysis() {
    state.detailWritingStyleAnalysis = null;
    document.getElementById('novel-writing-style-status').textContent = '尚未提取写作风格';
    document.getElementById('novel-writing-style-status').className = '';
    document.getElementById('novel-writing-style-summary').textContent = '暂无写作风格数据';
    document.getElementById('novel-writing-style-confidence').textContent = '可信度 --';
    document.getElementById('novel-writing-style-dimensions').innerHTML = '<div class="novel-writing-style-empty">暂无分析维度</div>';
    document.getElementById('novel-writing-style-techniques').innerHTML = '<div class="novel-writing-style-empty">暂无代表技法</div>';
    document.getElementById('novel-writing-style-examples').innerHTML = '<div class="novel-writing-style-empty">暂无代表片段</div>';
    document.getElementById('novel-writing-style-guide').textContent = '暂无仿写指南';
    document.getElementById('novel-writing-style-prompt').textContent = '暂无风格提示词';
}

function renderWritingStyleCard(label, value) {
    return `
        <article class="novel-writing-style-card">
            <span>${escapeHtml(label)}</span>
            <p>${escapeHtml(value || '暂无')}</p>
        </article>
    `;
}

function renderWritingStyleItems(items = [], { titleKey = 'name', bodyKey = 'description', emptyText = '暂无数据' } = {}) {
    if (!Array.isArray(items) || items.length === 0) {
        return `<div class="novel-writing-style-empty">${escapeHtml(emptyText)}</div>`;
    }

    return items.map(item => `
        <article class="novel-writing-style-item">
            <div class="novel-writing-style-item-head">
                <strong>${escapeHtml(item?.[titleKey] || '未命名')}</strong>
                <span>可信度 ${formatConfidence(item?.confidence)}</span>
            </div>
            <p>${escapeHtml(item?.[bodyKey] || '暂无说明')}</p>
            <div class="novel-writing-style-evidence">${escapeHtml(item?.evidence || '暂无证据片段')}</div>
        </article>
    `).join('');
}

function renderNovelWritingStyleAnalysis(analysis) {
    state.detailWritingStyleAnalysis = analysis;
    const status = analysis?.analysis_status || 'empty';
    const statusEl = document.getElementById('novel-writing-style-status');
    const hasStyle = Boolean(
        analysis?.summary ||
        analysis?.imitation_guide ||
        analysis?.style_prompt ||
        (Array.isArray(analysis?.signature_techniques) && analysis.signature_techniques.length) ||
        (Array.isArray(analysis?.examples) && analysis.examples.length)
    );

    if (status === 'failed') {
        statusEl.textContent = analysis.error_message || '上次提取失败';
        statusEl.className = 'failed';
    } else if (hasStyle) {
        statusEl.textContent = '已提取写作风格';
        statusEl.className = 'completed';
    } else {
        statusEl.textContent = '尚未提取写作风格';
        statusEl.className = '';
    }

    const dimensions = [
        ['叙事视角', analysis?.narrative_perspective],
        ['语言质感', analysis?.language_texture],
        ['节奏特征', analysis?.pacing],
        ['描写重点', analysis?.description_focus],
        ['对话风格', analysis?.dialogue_style],
        ['情绪基调', analysis?.emotional_tone]
    ];

    document.getElementById('novel-writing-style-summary').textContent = analysis?.summary || '暂无写作风格数据';
    document.getElementById('novel-writing-style-confidence').textContent = `可信度 ${formatConfidence(analysis?.confidence)}`;
    document.getElementById('novel-writing-style-dimensions').innerHTML = dimensions
        .map(([label, value]) => renderWritingStyleCard(label, value))
        .join('');
    document.getElementById('novel-writing-style-techniques').innerHTML = renderWritingStyleItems(
        analysis?.signature_techniques,
        { titleKey: 'name', bodyKey: 'description', emptyText: '暂无代表技法' }
    );
    document.getElementById('novel-writing-style-examples').innerHTML = renderWritingStyleItems(
        analysis?.examples,
        { titleKey: 'label', bodyKey: 'analysis', emptyText: '暂无代表片段' }
    );
    document.getElementById('novel-writing-style-guide').textContent = analysis?.imitation_guide || '暂无仿写指南';
    document.getElementById('novel-writing-style-prompt').textContent = analysis?.style_prompt || '暂无风格提示词';
}

async function loadNovelWritingStyleAnalysis(novelId) {
    try {
        const res = await api.get(`/api/novels/${novelId}/writing-style`);
        if (!res.success) {
            document.getElementById('novel-writing-style-status').textContent = res.message || '写作风格数据加载失败';
            return;
        }
        renderNovelWritingStyleAnalysis(res.data);
    } catch (err) {
        console.warn('加载写作风格数据失败:', err);
        document.getElementById('novel-writing-style-status').textContent = '写作风格数据加载失败';
    }
}

async function analyzeNovelWritingStyleWithAI(novelId) {
    const button = document.getElementById('btn-detail-analyze-writing-style');
    const originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="loading"></span> 提取中';
    document.getElementById('novel-writing-style-status').textContent = 'AI 正在提取写作风格...';

    try {
        const res = await api.post(`/api/ai/novels/${novelId}/writing-style/analyze`, {});
        if (!res.success) {
            showToast(res.message || '写作风格提取失败', 'error');
            await loadNovelWritingStyleAnalysis(novelId);
            return;
        }

        renderNovelWritingStyleAnalysis(res.data);
        switchNovelDetailTab('writing-style');
        showToast('已提取写作风格', 'success');
    } catch (err) {
        console.error('AI 提取写作风格失败:', err);
        showToast('AI 提取写作风格失败: ' + err.message, 'error');
    } finally {
        button.disabled = false;
        button.innerHTML = originalHtml;
    }
}

async function copyNovelWritingStylePrompt() {
    const prompt = state.detailWritingStyleAnalysis?.style_prompt || '';
    if (!prompt) {
        showToast('暂无可复制的风格提示词', 'warning');
        return;
    }

    try {
        await navigator.clipboard.writeText(prompt);
        showToast('已复制风格提示词', 'success');
    } catch (err) {
        console.error('复制风格提示词失败:', err);
        showToast('复制风格提示词失败', 'error');
    }
}

function renderCharacterBadges(items = []) {
    if (!Array.isArray(items) || items.length === 0) return '';
    return `
        <div class="novel-character-badges">
            ${items.map(item => `<span>${escapeHtml(item)}</span>`).join('')}
        </div>
    `;
}

function getCharacterProfile(character) {
    character = character || {};
    const profile = character.profile && typeof character.profile === 'object' ? character.profile : {};
    const firstSeen = profile.first_seen || (
        Number.isInteger(character.first_chapter_index) ? `第 ${character.first_chapter_index + 1} 章` : ''
    );

    return {
        summary: profile.summary || character.description || '暂无角色定位',
        appearance: profile.appearance || '',
        personality: Array.isArray(profile.personality) && profile.personality.length
            ? profile.personality
            : (Array.isArray(character.traits) ? character.traits : []),
        motivation: profile.motivation || '',
        skills: Array.isArray(profile.skills) ? profile.skills : [],
        firstSeen,
        cardEvidence: profile.card_evidence || character.evidence || '',
    };
}

function renderCharacterProfileMeta(label, value) {
    const hasArrayValue = Array.isArray(value) && value.length > 0;
    const hasTextValue = !Array.isArray(value) && value;
    if (!hasArrayValue && !hasTextValue) return '';

    const content = Array.isArray(value)
        ? value.map(item => `<span>${escapeHtml(item)}</span>`).join('')
        : escapeHtml(value);

    return `
        <div class="novel-character-profile-item">
            <span>${escapeHtml(label)}</span>
            <strong${Array.isArray(value) ? ' class="tag-list"' : ''}>${content}</strong>
        </div>
    `;
}

function getRelationStrength(confidence) {
    const number = Number(confidence);
    if (Number.isFinite(number) && number >= 0.78) return 'high';
    if (Number.isFinite(number) && number >= 0.48) return 'medium';
    return 'low';
}

function renderCharacterRelationshipGraph(characters = [], relations = []) {
    const graph = document.getElementById('novel-character-graph');
    if (!Array.isArray(characters) || characters.length === 0) {
        graph.innerHTML = '<div class="novel-character-empty">暂无角色卡数据</div>';
        return;
    }

    const width = 640;
    const height = 380;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = characters.length === 1 ? 0 : Math.min(146, 78 + characters.length * 10);
    const nodePositions = new Map();

    characters.forEach((character, index) => {
        const angle = characters.length === 1 ? 0 : (Math.PI * 2 * index) / characters.length - Math.PI / 2;
        const offset = index % 2 === 0 ? 0 : 12;
        nodePositions.set(character.id, {
            x: centerX + Math.cos(angle) * (radius + offset),
            y: centerY + Math.sin(angle) * (radius + offset)
        });
    });

    const relationLines = (relations || [])
        .map(relation => {
            const source = nodePositions.get(relation.source_character_id);
            const target = nodePositions.get(relation.target_character_id);
            if (!source || !target) return '';
            const dx = target.x - source.x;
            const dy = target.y - source.y;
            const distance = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
            const unitX = dx / distance;
            const unitY = dy / distance;
            const sourceEdge = {
                x: source.x + unitX * 42,
                y: source.y + unitY * 42
            };
            const targetEdge = {
                x: target.x - unitX * 46,
                y: target.y - unitY * 46
            };
            const midX = (sourceEdge.x + targetEdge.x) / 2;
            const midY = (sourceEdge.y + targetEdge.y) / 2;
            const strength = getRelationStrength(relation.confidence);
            return `
                <line x1="${sourceEdge.x}" y1="${sourceEdge.y}" x2="${targetEdge.x}" y2="${targetEdge.y}" class="novel-relation-line strength-${strength}" marker-end="url(#relation-arrow)"></line>
                <text x="${midX}" y="${midY - 6}" class="novel-relation-label">${escapeHtml(relation.relation_type || '相关')}</text>
            `;
        })
        .join('');

    const nodes = characters.map(character => {
        const position = nodePositions.get(character.id);
        const initials = String(character.name || '?').slice(0, 2);
        const strength = getRelationStrength(character.confidence);
        return `
            <g class="novel-character-node strength-${strength}" transform="translate(${position.x}, ${position.y})">
                <circle class="novel-character-node-halo" r="45"></circle>
                <circle r="34"></circle>
                <text class="novel-character-node-name" text-anchor="middle" y="5">${escapeHtml(initials)}</text>
                <text class="novel-character-node-role" text-anchor="middle" y="52">${escapeHtml(character.role_type || '角色')}</text>
            </g>
        `;
    }).join('');

    graph.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="角色关系谱">
            <defs>
                <marker id="relation-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z"></path>
                </marker>
                <radialGradient id="character-node-fill" cx="38%" cy="28%" r="70%">
                    <stop offset="0%" stop-color="#ffffff"></stop>
                    <stop offset="100%" stop-color="#dbeafe"></stop>
                </radialGradient>
            </defs>
            ${relationLines}
            ${nodes}
        </svg>
        <div class="novel-relation-legend">
            <span><i class="strength-high"></i>高可信</span>
            <span><i class="strength-medium"></i>中可信</span>
            <span><i class="strength-low"></i>低可信</span>
        </div>
    `;
}

function renderNovelCharacterAnalysis(analysis) {
    state.detailCharacterAnalysis = analysis;
    const characters = Array.isArray(analysis?.characters) ? analysis.characters : [];
    const relations = Array.isArray(analysis?.relations) ? analysis.relations : [];
    const status = analysis?.analysis_status || 'empty';
    const statusEl = document.getElementById('novel-character-status');

    if (status === 'failed') {
        statusEl.textContent = analysis.error_message || '上次生成失败';
        statusEl.className = 'failed';
    } else if (characters.length > 0 || relations.length > 0) {
        statusEl.textContent = `已生成 ${characters.length} 张角色卡、${relations.length} 条关系`;
        statusEl.className = 'completed';
    } else {
        statusEl.textContent = '尚未生成角色卡';
        statusEl.className = '';
    }

    const list = document.getElementById('novel-character-list');
    if (characters.length === 0) {
        list.innerHTML = '<div class="novel-character-empty">暂无角色卡数据</div>';
    } else {
        list.innerHTML = characters.map(character => {
            const profile = getCharacterProfile(character);
            return `
                <article class="novel-character-card">
                    <div class="novel-character-card-head">
                        <strong>${escapeHtml(character.name)}</strong>
                        <span>${escapeHtml(character.role_type || '角色')}</span>
                    </div>
                    ${character.aliases?.length ? `<div class="novel-character-alias">别名：${escapeHtml(character.aliases.join('、'))}</div>` : ''}
                    <p class="novel-character-card-summary">${escapeHtml(profile.summary)}</p>
                    ${renderCharacterBadges(profile.personality)}
                    <div class="novel-character-profile-grid">
                        ${renderCharacterProfileMeta('气质', profile.appearance)}
                        ${renderCharacterProfileMeta('动机', profile.motivation)}
                        ${renderCharacterProfileMeta('能力', profile.skills)}
                        ${renderCharacterProfileMeta('首次出现', profile.firstSeen)}
                    </div>
                    <div class="novel-character-evidence">${escapeHtml(profile.cardEvidence || '暂无证据片段')}</div>
                    <div class="novel-character-confidence">可信度 ${formatConfidence(character.confidence)}</div>
                </article>
            `;
        }).join('');
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
            document.getElementById('novel-character-status').textContent = res.message || '角色卡数据加载失败';
            return;
        }
        renderNovelCharacterAnalysis(res.data);
    } catch (err) {
        console.warn('加载角色卡数据失败:', err);
        document.getElementById('novel-character-status').textContent = '角色卡数据加载失败';
    }
}

async function analyzeNovelCharactersWithAI(novelId) {
    const button = document.getElementById('btn-detail-analyze-characters');
    const originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="loading"></span> 生成中';
    document.getElementById('novel-character-status').textContent = 'AI 正在生成角色卡...';

    try {
        const res = await api.post(`/api/ai/novels/${novelId}/characters/analyze`, {});
        if (!res.success) {
            showToast(res.message || '角色卡生成失败', 'error');
            await loadNovelCharacterAnalysis(novelId);
            return;
        }

        renderNovelCharacterAnalysis(res.data);
        switchNovelDetailTab('characters');
        showToast(`已生成 ${res.data.character_count} 张角色卡、${res.data.relation_count} 条关系`, 'success');
    } catch (err) {
        console.error('AI 生成角色卡失败:', err);
        showToast('AI 生成角色卡失败: ' + err.message, 'error');
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
    resetNovelSettingAnalysis();
    resetNovelWritingStyleAnalysis();
    switchNovelDetailTab('overview');
    renderNovelDetailTags(novel.tags);

    document.getElementById('btn-detail-read').onclick = () => openNovelFile(novel.id);
    document.getElementById('btn-detail-download').onclick = () => downloadNovel(novel.id);
    document.getElementById('btn-detail-edit').onclick = () => {
        closeModal('novel-detail-modal');
        editNovel(novel.id);
    };
    document.getElementById('btn-detail-check-file').onclick = () => loadNovelDetailFileInfo(novel.id);
    document.getElementById('btn-open-character-library').onclick = () => openCharacterLibraryForNovel(novel.id);
    document.getElementById('btn-detail-analyze-characters').onclick = () => analyzeNovelCharactersWithAI(novel.id);
    document.getElementById('btn-detail-analyze-settings').onclick = () => analyzeNovelSettingsWithAI(novel.id);
    document.getElementById('btn-detail-analyze-writing-style').onclick = () => analyzeNovelWritingStyleWithAI(novel.id);
    document.getElementById('btn-copy-writing-style-prompt').onclick = copyNovelWritingStylePrompt;
    document.querySelectorAll('.novel-detail-tab').forEach(tab => {
        tab.onclick = () => switchNovelDetailTab(tab.dataset.detailTab);
    });
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
        loadNovelSettingAnalysis(novelId);
        loadNovelWritingStyleAnalysis(novelId);
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
        loadNovelSettingAnalysis(novelId);
        loadNovelWritingStyleAnalysis(novelId);
        loadNovelCharacterAnalysis(novelId);
    } catch (err) {
        console.error('加载小说详情失败:', err);
        showToast('加载小说详情失败: ' + err.message, 'error');
    }
}

// ==================== 阅读器功能 ====================
