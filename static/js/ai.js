const aiConfigState = {
    configs: [],
    providers: [],
    editingConfig: null,
    activeConfigId: null,
    discoveredModels: []
};

// 提供商模型提示
const providerModels = {
    openai: {
        hint: '常用模型：gpt-3.5-turbo, gpt-4, gpt-4-turbo, gpt-4o',
        defaultModel: 'gpt-3.5-turbo',
        models: ['gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o']
    },
    'openai-compatible': {
        hint: '阿里：qwen-turbo, qwen-plus | 月之暗面：moonshot-v1-8k | DeepSeek：deepseek-chat | Google AI Studio：gemini-2.5-flash, gemini-3-pro-preview',
        defaultModel: 'qwen-turbo',
        models: ['qwen-turbo', 'qwen-plus', 'deepseek-chat', 'moonshot-v1-8k', 'gemini-2.5-flash', 'gemini-3-pro-preview']
    },
    'new-api': {
        hint: 'New API gateway: API Base usually uses http(s)://your-new-api-host/v1; common models: gpt-4o, gpt-4o-mini, deepseek-chat, gemini-2.5-flash',
        defaultModel: 'gpt-4o-mini',
        models: ['gpt-4o', 'gpt-4o-mini', 'deepseek-chat', 'gemini-2.5-flash', 'claude-3-5-sonnet']
    },
    claude: {
        hint: '常用模型：claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307',
        defaultModel: 'claude-3-haiku-20240307',
        models: ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307']
    },
    gemini: {
        hint: '常用模型：gemini-2.5-flash, gemini-3-pro-preview, gemini-2.0-flash',
        defaultModel: 'gemini-2.5-flash',
        models: ['gemini-2.5-flash', 'gemini-3-pro-preview', 'gemini-2.0-flash']
    },
    'gemini-native': {
        hint: '原生 Gemini API：支持官方 safety feedback，适合排查内容拦截',
        defaultModel: 'gemini-2.5-flash',
        models: ['gemini-2.5-flash', 'gemini-3-pro-preview', 'gemini-2.0-flash']
    },
    ollama: {
        hint: '本地模型：llama2, llama3, mistral, qwen, phi3 等',
        defaultModel: 'llama3',
        models: ['llama2', 'llama3', 'mistral', 'qwen', 'phi3']
    }
};

function getProviderPresetModels(provider) {
    const providerConfig = aiConfigState.providers.find(item => item.id === provider);
    if (providerConfig?.models?.length) {
        return providerConfig.models;
    }
    return providerModels[provider]?.models || [];
}

function mergeModelLists(...groups) {
    const seen = new Set();
    const merged = [];

    groups.flat().forEach(model => {
        if (!model || typeof model !== 'string') {
            return;
        }
        const trimmed = model.trim();
        if (!trimmed) {
            return;
        }
        const lowered = trimmed.toLowerCase();
        if (seen.has(lowered)) {
            return;
        }
        seen.add(lowered);
        merged.push(trimmed);
    });

    return merged;
}

function setAIModelDiscoveryStatus(message) {
    document.getElementById('ai-model-discovery-status').textContent = message;
}

function renderDiscoveredModels(models = [], preferredModel = '') {
    const select = document.getElementById('ai-discovered-models');
    const currentModel = preferredModel || document.getElementById('ai-config-model').value.trim();
    aiConfigState.discoveredModels = mergeModelLists(models, currentModel ? [currentModel] : []);

    if (!aiConfigState.discoveredModels.length) {
        select.innerHTML = '<option value="">测试连接后，可在这里选择当前接口返回的模型</option>';
        return;
    }

    select.innerHTML = [
        '<option value="">请选择一个模型写入上方输入框</option>',
        ...aiConfigState.discoveredModels.map(model => `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`)
    ].join('');

    if (currentModel && aiConfigState.discoveredModels.includes(currentModel)) {
        select.value = currentModel;
    }
}

function isAIProxyEnabled(value) {
    if (typeof value === 'boolean') return value;
    if (typeof value === 'number') return value !== 0;
    if (typeof value === 'string') return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase());
    return false;
}

function updateAIProxyFields() {
    const toggle = document.getElementById('ai-config-use-proxy');
    const proxyUrlInput = document.getElementById('ai-config-proxy-url');
    const proxyUrlField = proxyUrlInput?.closest('.ai-proxy-url-field');
    if (!toggle || !proxyUrlInput) return;

    proxyUrlInput.disabled = !toggle.checked;
    proxyUrlField?.classList.toggle('is-disabled', !toggle.checked);
}

function collectAIConfigFormData() {
    const id = document.getElementById('ai-config-id').value.trim();
    const apiKey = document.getElementById('ai-config-api-key').value.trim();
    const configData = {
        name: document.getElementById('ai-config-name').value.trim(),
        provider: document.getElementById('ai-config-provider').value,
        model: document.getElementById('ai-config-model').value.trim(),
        api_base: document.getElementById('ai-config-api-base').value.trim(),
        use_proxy: document.getElementById('ai-config-use-proxy').checked,
        proxy_url: document.getElementById('ai-config-proxy-url').value.trim(),
        temperature: parseFloat(document.getElementById('ai-config-temperature').value),
        max_tokens: parseInt(document.getElementById('ai-config-max-tokens').value, 10)
    };

    if (id) {
        configData.id = parseInt(id, 10);
    }
    if (apiKey) {
        configData.api_key = apiKey;
    }

    return configData;
}

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

    // 检查是否有 Gemini 配置，显示代理提示
    const hasGemini = aiConfigState.configs.some(c => ['gemini', 'gemini-native'].includes(c.provider));
    const proxyHint = document.getElementById('gemini-proxy-hint');
    if (proxyHint) {
        proxyHint.style.display = hasGemini ? 'flex' : 'none';
    }

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
        const proxyEnabled = isAIProxyEnabled(config.use_proxy);

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
                            ${proxyEnabled ? '<span class="ai-config-proxy active"><i class="fas fa-route"></i> 代理</span>' : ''}
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
                    <button class="btn btn-sm btn-danger btn-icon-only" onclick="deleteAIConfig(${config.id})" title="删除配置" aria-label="删除配置">
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
        'new-api': 'network-wired',
        claude: 'feather-alt',
        gemini: 'sparkles',
        'gemini-native': 'shield-halved',
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
    document.getElementById('ai-config-api-key').placeholder = 'sk-...';
    document.getElementById('ai-config-api-base').value = '';
    document.getElementById('ai-config-use-proxy').checked = false;
    document.getElementById('ai-config-proxy-url').value = '';
    document.getElementById('ai-config-temperature').value = '0.7';
    document.getElementById('ai-config-max-tokens').value = '2000';
    document.getElementById('ai-config-modal-title').textContent = '添加 AI 配置';

    renderDiscoveredModels(getProviderPresetModels('openai'));
    setAIModelDiscoveryStatus('支持手动填写模型，也支持测试连接后自动拉取模型列表');
    updateProviderHint('openai');
    updateAIProxyFields();
}

function updateProviderHint(provider) {
    const hint = providerModels[provider]?.hint || '';
    const defaultModel = providerModels[provider]?.defaultModel || '';
    document.getElementById('ai-model-hint').textContent = hint;

    const modelInput = document.getElementById('ai-config-model');
    if (!modelInput.value && defaultModel) {
        modelInput.value = defaultModel;
    }

    renderDiscoveredModels(getProviderPresetModels(provider), modelInput.value);
    setAIModelDiscoveryStatus('点击“测试连接”后，会刷新为当前接口真正可用的模型');

    // 显示/隐藏 Gemini 代理提示
    const proxyHint = document.getElementById('gemini-proxy-hint');
    if (proxyHint) {
        proxyHint.style.display = ['gemini', 'gemini-native'].includes(provider) ? 'flex' : 'none';
    }
}

async function saveAIConfig() {
    const id = document.getElementById('ai-config-id').value;
    const apiKey = document.getElementById('ai-config-api-key').value.trim();
    const configData = collectAIConfigFormData();

    if (!configData.name) {
        showToast('请输入配置名称', 'error');
        return;
    }
    if (!configData.model) {
        showToast('请输入模型名称', 'error');
        return;
    }
    if (!id && configData.provider !== 'ollama' && !apiKey) {
        showToast('请输入 API Key', 'error');
        return;
    }
    if (configData.use_proxy && !configData.proxy_url) {
        showToast('启用代理时请输入代理地址', 'error');
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
    document.getElementById('ai-config-api-key').value = '';
    document.getElementById('ai-config-api-key').placeholder = config.api_key ? '已保存，留空则保持不变' : 'sk-...';
    document.getElementById('ai-config-api-base').value = config.api_base || '';
    document.getElementById('ai-config-use-proxy').checked = isAIProxyEnabled(config.use_proxy);
    document.getElementById('ai-config-proxy-url').value = config.proxy_url || '';
    document.getElementById('ai-config-temperature').value = config.temperature;
    document.getElementById('ai-config-max-tokens').value = config.max_tokens;
    document.getElementById('ai-config-modal-title').textContent = '编辑 AI 配置';

    updateProviderHint(config.provider);
    updateAIProxyFields();
    renderDiscoveredModels(getProviderPresetModels(config.provider), config.model);
    setAIModelDiscoveryStatus('当前可先从推荐模型中选，点击“测试连接”可刷新为接口返回的模型');
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
            const modelCount = res.data?.model_count || 0;
            showToast(modelCount ? `连接成功，已识别 ${modelCount} 个模型` : '连接成功', 'success');
        } else {
            showToast('连接失败: ' + res.message, 'error');
        }
    } catch (err) {
        console.error('测试 AI 连接失败:', err);
        showToast('测试失败: ' + err.message, 'error');
    }
}

async function testCurrentAIConfig() {
    const configData = collectAIConfigFormData();
    const requiresApiKey = configData.provider !== 'ollama';

    if (!configData.provider) {
        showToast('请选择 AI 提供商', 'error');
        return;
    }
    if (!configData.model) {
        showToast('请输入模型名称', 'error');
        return;
    }
    if (!configData.id && requiresApiKey && !configData.api_key) {
        showToast('请输入 API Key', 'error');
        return;
    }
    if (configData.use_proxy && !configData.proxy_url) {
        showToast('启用代理时请输入代理地址', 'error');
        return;
    }

    const testButton = document.getElementById('btn-test-ai-config');
    const originalHtml = testButton.innerHTML;
    testButton.disabled = true;
    testButton.innerHTML = '<span class="loading"></span> 测试中';

    try {
        const res = await api.post('/api/ai/configs/test', configData);
        if (res.success) {
            const discoveredModels = res.data?.models || [];
            renderDiscoveredModels(discoveredModels, configData.model);
            setAIModelDiscoveryStatus(
                discoveredModels.length
                    ? `已从当前接口获取 ${discoveredModels.length} 个可选模型，可直接在下拉框中选择`
                    : '连接成功，但接口未返回模型列表，已保留推荐模型'
            );
            showToast(
                discoveredModels.length
                    ? `连接成功，已获取 ${discoveredModels.length} 个模型`
                    : '连接成功',
                'success'
            );
        } else {
            setAIModelDiscoveryStatus('测试失败，请检查 API 地址、Key 和代理设置');
            showToast('连接失败: ' + res.message, 'error');
        }
    } catch (err) {
        console.error('测试当前 AI 配置失败:', err);
        setAIModelDiscoveryStatus('测试失败，请检查配置后重试');
        showToast('测试失败: ' + err.message, 'error');
    } finally {
        testButton.disabled = false;
        testButton.innerHTML = originalHtml;
    }
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
