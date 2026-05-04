const characterState = {
    items: [],
    relationCandidates: [],
    activeCharacter: null,
    filters: {
        keyword: '',
        novelId: '',
        roleType: '',
        tag: '',
        sort: 'updated_desc'
    },
    isLoading: false,
    isSaving: false
};

function splitCharacterListInput(value) {
    return String(value || '')
        .split(/[、,，/\n]+/)
        .map(item => item.trim())
        .filter(Boolean);
}

function joinCharacterListInput(items) {
    return Array.isArray(items) ? items.join('、') : '';
}

function getCharacterProfileForDisplay(character = {}) {
    const profile = character.profile && typeof character.profile === 'object' ? character.profile : {};
    return {
        summary: profile.summary || character.description || '暂无角色简介',
        appearance: profile.appearance || '',
        personality: Array.isArray(profile.personality) && profile.personality.length ? profile.personality : (character.traits || []),
        motivation: profile.motivation || '',
        skills: Array.isArray(profile.skills) ? profile.skills : [],
        tags: Array.isArray(profile.tags) ? profile.tags : []
    };
}

function buildCharacterLibraryQuery() {
    const params = new URLSearchParams();
    if (characterState.filters.keyword) params.set('keyword', characterState.filters.keyword);
    if (characterState.filters.novelId) params.set('novel_id', characterState.filters.novelId);
    if (characterState.filters.roleType) params.set('role_type', characterState.filters.roleType);
    if (characterState.filters.tag) params.set('tag', characterState.filters.tag);
    if (characterState.filters.sort) params.set('sort', characterState.filters.sort);
    const query = params.toString();
    return query ? `?${query}` : '';
}

async function loadCharacterLibrary(overrides = {}) {
    characterState.filters = { ...characterState.filters, ...overrides };
    characterState.isLoading = true;
    renderCharacterCards();

    try {
        const res = await api.get(`/api/characters${buildCharacterLibraryQuery()}`);
        if (!res.success) {
            showToast(res.message || '角色库加载失败', 'error');
            return;
        }
        characterState.items = res.data.items || [];
        renderCharacterFilters();
    } catch (err) {
        console.error('加载角色库失败:', err);
        showToast('加载角色库失败: ' + err.message, 'error');
    } finally {
        characterState.isLoading = false;
        renderCharacterCards();
    }
}

function renderCharacterFilters() {
    const novelSelect = document.getElementById('character-library-novel-filter');
    const drawerNovelSelect = document.getElementById('character-novel-id');
    if (!novelSelect || !drawerNovelSelect) return;

    const novels = Array.isArray(state.novels) ? state.novels : [];
    const listOptions = ['<option value="">全部小说</option>']
        .concat(novels.map(novel => `<option value="${novel.id}">${escapeHtml(novel.title)}</option>`));
    novelSelect.innerHTML = listOptions.join('');
    novelSelect.value = characterState.filters.novelId || '';

    drawerNovelSelect.innerHTML = ['<option value="">请选择小说</option>']
        .concat(novels.map(novel => `<option value="${novel.id}">${escapeHtml(novel.title)}</option>`))
        .join('');
}

function renderCharacterCards() {
    const grid = document.getElementById('character-library-grid');
    if (!grid) return;

    if (characterState.isLoading) {
        grid.innerHTML = '<div class="character-library-empty">角色库加载中...</div>';
        return;
    }

    if (!characterState.items.length) {
        grid.innerHTML = '<div class="character-library-empty">暂无角色卡</div>';
        return;
    }

    grid.innerHTML = characterState.items.map(character => {
        const profile = getCharacterProfileForDisplay(character);
        const notes = character.notes ? `<div class="character-library-card-notes">${escapeHtml(character.notes)}</div>` : '';
        return `
            <article class="character-library-card" data-character-id="${character.id}">
                <div class="character-library-card-meta">
                    <span>${escapeHtml(character.novel_title || '未关联小说')}</span>
                    <span>${escapeHtml(character.role_type || '角色')}</span>
                </div>
                <h3>${escapeHtml(character.name)}</h3>
                <p>${escapeHtml(profile.summary)}</p>
                <div class="character-library-card-tags">
                    ${profile.tags.map(tag => `<span>${escapeHtml(tag)}</span>`).join('')}
                </div>
                ${notes}
            </article>
        `;
    }).join('');

    grid.querySelectorAll('.character-library-card').forEach(card => {
        card.addEventListener('click', () => openCharacterDrawer(Number(card.dataset.characterId)));
    });
}

function openCharacterDrawerElement() {
    const drawer = document.getElementById('character-drawer');
    drawer.classList.add('active');
    drawer.setAttribute('aria-hidden', 'false');
}

function closeCharacterDrawer() {
    const drawer = document.getElementById('character-drawer');
    drawer.classList.remove('active');
    drawer.setAttribute('aria-hidden', 'true');
    characterState.activeCharacter = null;
}

function fillCharacterForm(character = {}) {
    const profile = getCharacterProfileForDisplay(character);
    const summary = profile.summary === '暂无角色简介' ? '' : profile.summary;

    document.getElementById('character-id').value = character.id || '';
    document.getElementById('character-novel-id').value = character.novel_id || characterState.filters.novelId || '';
    document.getElementById('character-name').value = character.name || '';
    document.getElementById('character-aliases').value = joinCharacterListInput(character.aliases);
    document.getElementById('character-role-type').value = character.role_type || '未知';
    document.getElementById('character-description').value = character.description || '';
    document.getElementById('character-traits').value = joinCharacterListInput(character.traits);
    document.getElementById('character-tags').value = joinCharacterListInput(profile.tags);
    document.getElementById('character-summary').value = summary;
    document.getElementById('character-appearance').value = profile.appearance;
    document.getElementById('character-motivation').value = profile.motivation;
    document.getElementById('character-skills').value = joinCharacterListInput(profile.skills);
    document.getElementById('character-notes').value = character.notes || '';
}

function collectCharacterFormData() {
    return {
        novel_id: document.getElementById('character-novel-id').value,
        name: document.getElementById('character-name').value.trim(),
        aliases: splitCharacterListInput(document.getElementById('character-aliases').value),
        role_type: document.getElementById('character-role-type').value.trim() || '未知',
        description: document.getElementById('character-description').value.trim(),
        traits: splitCharacterListInput(document.getElementById('character-traits').value),
        profile: {
            summary: document.getElementById('character-summary').value.trim(),
            appearance: document.getElementById('character-appearance').value.trim(),
            personality: splitCharacterListInput(document.getElementById('character-traits').value),
            motivation: document.getElementById('character-motivation').value.trim(),
            skills: splitCharacterListInput(document.getElementById('character-skills').value),
            tags: splitCharacterListInput(document.getElementById('character-tags').value)
        },
        notes: document.getElementById('character-notes').value.trim()
    };
}

function renderCharacterRelations(relations = []) {
    const list = document.getElementById('character-relation-list');
    if (!list) return;

    if (!relations.length) {
        list.innerHTML = '<div class="character-relation-empty">暂无相关角色</div>';
        return;
    }

    list.innerHTML = relations.map(relation => `
        <div class="character-relation-item" data-relation-id="${relation.id}">
            <strong>${escapeHtml(relation.other_name || relation.target_name || relation.source_name || '未知角色')}</strong>
            <span>${escapeHtml(relation.relation_type || '相关')}</span>
            <p>${escapeHtml(relation.description || '暂无说明')}</p>
            <button class="btn btn-sm btn-secondary" data-relation-delete="${relation.id}">删除</button>
        </div>
    `).join('');

    list.querySelectorAll('[data-relation-delete]').forEach(button => {
        button.addEventListener('click', () => deleteCharacterRelation(Number(button.dataset.relationDelete)));
    });
}

function renderCharacterRelationTargets(character = {}) {
    const select = document.getElementById('character-relation-target');
    if (!select) return;

    const currentId = Number(character.id || document.getElementById('character-id').value || 0);
    const options = characterState.relationCandidates
        .filter(item => item.id !== currentId)
        .map(item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`);
    select.innerHTML = '<option value="">选择同书角色</option>' + options.join('');
}

async function refreshCharacterRelationTargets(novelId, currentId = 0) {
    characterState.relationCandidates = [];
    if (!novelId) {
        renderCharacterRelationTargets({ id: currentId });
        return;
    }

    try {
        const res = await api.get(`/api/characters?novel_id=${encodeURIComponent(novelId)}&sort=name`);
        characterState.relationCandidates = res.success ? (res.data.items || []) : [];
    } catch (err) {
        console.warn('加载同书角色失败:', err);
        characterState.relationCandidates = [];
    }
    renderCharacterRelationTargets({ id: currentId });
}

async function openCharacterDrawer(characterId) {
    renderCharacterFilters();
    document.getElementById('character-relation-type').value = '';
    document.getElementById('character-relation-description').value = '';

    if (!characterId) {
        characterState.activeCharacter = null;
        document.getElementById('character-drawer-title').textContent = '新建角色';
        document.getElementById('character-drawer-novel').textContent = '选择所属小说';
        fillCharacterForm({});
        renderCharacterRelations([]);
        await refreshCharacterRelationTargets(characterState.filters.novelId, 0);
        openCharacterDrawerElement();
        return;
    }

    const res = await api.get(`/api/characters/${characterId}`);
    if (!res.success) {
        showToast(res.message || '角色详情加载失败', 'error');
        return;
    }

    characterState.activeCharacter = res.data;
    document.getElementById('character-drawer-title').textContent = res.data.name;
    document.getElementById('character-drawer-novel').textContent = res.data.novel_title || '未关联小说';
    fillCharacterForm(res.data);
    renderCharacterRelations(res.data.relations || []);
    await refreshCharacterRelationTargets(res.data.novel_id, res.data.id);
    openCharacterDrawerElement();
}

async function saveCharacter() {
    const data = collectCharacterFormData();
    if (!data.name) {
        showToast('请填写角色名', 'error');
        return;
    }
    if (!data.novel_id) {
        showToast('请选择所属小说', 'error');
        return;
    }

    const id = document.getElementById('character-id').value;
    const res = id
        ? await api.put(`/api/characters/${id}`, data)
        : await api.post('/api/characters', data);
    if (!res.success) {
        showToast(res.message || '保存角色失败', 'error');
        return;
    }

    showToast(id ? '角色已更新' : '角色已创建', 'success');
    await loadCharacterLibrary();
    await openCharacterDrawer(res.data.id);
}

async function deleteCharacter() {
    const id = document.getElementById('character-id').value;
    if (!id) {
        closeCharacterDrawer();
        return;
    }
    if (!confirm('确定要删除这张角色卡吗？相关关系也会删除。')) return;

    const res = await api.delete(`/api/characters/${id}`);
    if (!res.success) {
        showToast(res.message || '删除角色失败', 'error');
        return;
    }

    showToast('角色已删除', 'success');
    closeCharacterDrawer();
    await loadCharacterLibrary();
}

async function completeCharacterWithAI() {
    const id = document.getElementById('character-id').value;
    if (!id) {
        showToast('请先保存角色，再使用 AI 补全', 'error');
        return;
    }

    const res = await api.post(`/api/characters/${id}/ai-complete`, {});
    if (!res.success) {
        showToast(res.message || 'AI 补全失败', 'error');
        return;
    }

    showToast('AI 已补全角色卡', 'success');
    await loadCharacterLibrary();
    await openCharacterDrawer(res.data.id);
}

async function saveCharacterRelation() {
    const sourceId = document.getElementById('character-id').value;
    const targetId = document.getElementById('character-relation-target').value;
    const relationType = document.getElementById('character-relation-type').value.trim();
    const description = document.getElementById('character-relation-description').value.trim();
    if (!sourceId || !targetId) {
        showToast('请选择要关联的角色', 'error');
        return;
    }

    const res = await api.post(`/api/characters/${sourceId}/relations`, {
        target_character_id: targetId,
        relation_type: relationType || '相关',
        description
    });
    if (!res.success) {
        showToast(res.message || '保存关系失败', 'error');
        return;
    }

    document.getElementById('character-relation-type').value = '';
    document.getElementById('character-relation-description').value = '';
    await openCharacterDrawer(Number(sourceId));
}

async function deleteCharacterRelation(relationId) {
    const res = await api.delete(`/api/character-relations/${relationId}`);
    if (!res.success) {
        showToast(res.message || '删除关系失败', 'error');
        return;
    }
    await openCharacterDrawer(Number(document.getElementById('character-id').value));
}

async function generateCharacterCardsForCurrentNovel() {
    const novelId = characterState.filters.novelId || document.getElementById('character-library-novel-filter').value;
    if (!novelId) {
        showToast('请先选择一本小说，再批量生成角色卡', 'error');
        return;
    }

    const button = document.getElementById('btn-character-ai-generate');
    const originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="loading"></span> 生成中';
    try {
        const res = await api.post(`/api/ai/novels/${novelId}/characters/analyze`, {});
        if (!res.success) {
            showToast(res.message || '角色卡生成失败', 'error');
            return;
        }
        showToast(`已生成 ${res.data.character_count} 张角色卡`, 'success');
        await loadCharacterLibrary({ novelId: String(novelId) });
    } catch (err) {
        console.error('角色库批量生成失败:', err);
        showToast('角色卡生成失败: ' + err.message, 'error');
    } finally {
        button.disabled = false;
        button.innerHTML = originalHtml;
    }
}

function openCharacterLibraryForNovel(novelId) {
    characterState.filters.novelId = novelId ? String(novelId) : '';
    closeModal('novel-detail-modal');
    switchView('characters');
}
