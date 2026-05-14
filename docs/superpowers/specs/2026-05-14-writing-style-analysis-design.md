# 小说写作风格提取设计

## 背景

当前小说详情页已经支持 AI 提取设定集和生成角色卡。两者都使用同一套产品模式：详情页内独立 tab、后端 AI 分析接口、SQLite 持久化、分析状态记录、失败后可重试。

写作风格提取应复用这套模式，让用户能从本地小说正文中沉淀可查看、可复制、可用于后续创作参考的风格档案。它不应该混入设定集，因为写作风格关注的是叙事方法、语言节奏和仿写指导，而不是世界观事实。

## 目标

1. 在小说详情页新增“写作风格”tab，与“设定集”“角色卡”并列。
2. 支持点击按钮后用 AI 提取该小说的写作风格，并保存结果。
3. 同时输出分析卡片和仿写指南。
4. 提供可复制的风格复刻提示词，方便用户在后续写作或改写时使用。
5. 保持现有详情页、设定集、角色卡、阅读器和批量导入流程不受影响。
6. 用 Python 后端测试和 Node 静态 UI 测试覆盖新增行为。

## 非目标

1. 不做跨小说风格库或风格对比。
2. 不做批量风格提取。
3. 不把风格结果自动写入小说简介、标签或分类。
4. 不做风格手动编辑表单。
5. 不做长篇原文摘抄；代表片段只保留短证据，用于解释判断依据。

## 用户体验

小说详情弹窗新增一个内容 tab：

- 概览
- 本地文件
- 设定集
- 写作风格
- 角色卡

“写作风格”面板顶部显示标题、状态和操作按钮：

- 初始状态：显示“尚未提取写作风格”。
- 分析中：按钮禁用，显示“AI 正在提取写作风格...”。
- 完成：显示“已提取写作风格”，并展示分析内容。
- 失败：显示失败原因，并允许再次点击提取。

面板主体分为四块：

1. 风格总览：展示 `summary` 和整体可信度。
2. 分析维度：以紧凑卡片展示叙事视角、语言质感、节奏、描写重点、对话风格、情绪基调。
3. 代表技法和片段：展示 `signature_techniques` 与 `examples`，每条片段包含短标题、说明、证据片段和可信度。
4. 仿写指南：展示 `imitation_guide` 和 `style_prompt`。`style_prompt` 使用独立块展示，并提供复制按钮。

## 数据模型

新增 `novel_writing_style_analysis_runs`：

```sql
CREATE TABLE IF NOT EXISTS novel_writing_style_analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL UNIQUE,
    status TEXT DEFAULT 'pending',
    model TEXT,
    source_excerpt_chars INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
);
```

新增 `novel_writing_styles`：

```sql
CREATE TABLE IF NOT EXISTS novel_writing_styles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL UNIQUE,
    summary TEXT,
    narrative_perspective TEXT,
    language_texture TEXT,
    pacing TEXT,
    description_focus TEXT,
    dialogue_style TEXT,
    emotional_tone TEXT,
    signature_techniques_json TEXT DEFAULT '[]',
    examples_json TEXT DEFAULT '[]',
    imitation_guide TEXT,
    style_prompt TEXT,
    confidence REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
);
```

选择一张主结果表而不是多张维度表，是为了保持第一版简单。写作风格对每本小说通常只有一份当前结果，数组字段用 JSON 保存即可满足展示和复制需求。

## API 设计

新增读取接口：

`GET /api/novels/<novel_id>/writing-style`

不存在小说时返回 404。存在小说但尚未分析时返回 `analysis_status: "empty"` 和空字段。

新增 AI 提取接口：

`POST /api/ai/novels/<novel_id>/writing-style/analyze`

行为与设定集提取一致：

1. 获取小说标题、作者、简介和可读正文片段。
2. 如果没有标题、简介或正文片段，返回 400。
3. 如果没有激活 AI 配置，返回 400。
4. 调用 AI，解析 JSON，归一化字段。
5. 没有可用结果时返回 500。
6. 成功时替换该小说已有写作风格结果，并把 run 状态置为 completed。
7. AI 返回格式错误或模型异常时记录 failed 状态和错误信息。

## AI 输出格式

AI 必须只返回 JSON 对象：

```json
{
  "summary": "整体写作风格概述",
  "narrative_perspective": "叙事视角",
  "language_texture": "语言质感",
  "pacing": "节奏特征",
  "description_focus": "描写重点",
  "dialogue_style": "对话风格",
  "emotional_tone": "情绪基调",
  "signature_techniques": [
    {
      "name": "技法名称",
      "description": "技法说明",
      "evidence": "短证据片段",
      "confidence": 0.8
    }
  ],
  "examples": [
    {
      "label": "片段标签",
      "analysis": "片段体现的风格特征",
      "evidence": "短证据片段",
      "confidence": 0.8
    }
  ],
  "imitation_guide": "面向后续写作的具体指南",
  "style_prompt": "可复制给 AI 的风格复刻提示词",
  "confidence": 0.8
}
```

归一化规则：

- `summary` 最长 260 字符。
- 六个分析维度各最长 240 字符。
- `signature_techniques` 最多 8 条。
- `examples` 最多 6 条。
- 每条证据片段最长 220 字符。
- `imitation_guide` 最长 900 字符。
- `style_prompt` 最长 1200 字符。
- `confidence` 限制在 0 到 1。
- 所有判断只能基于提供的小说元数据和正文片段，不补写未出现的剧情。

## 前端设计

修改 `templates/index.html`：

- 新增 `novel-detail-tab-writing-style`。
- 新增 `novel-detail-panel-writing-style`。
- 新增按钮 `btn-detail-analyze-writing-style`。
- 新增状态节点 `novel-writing-style-status`。
- 新增展示容器：总览、维度、技法、例证、仿写指南、提示词。

修改 `static/js/core.js`：

- 在全局 `state` 中新增 `detailWritingStyleAnalysis: null`。

修改 `static/js/novels.js`：

- 新增 `resetNovelWritingStyleAnalysis()`。
- 新增 `renderNovelWritingStyleAnalysis(analysis)`。
- 新增 `loadNovelWritingStyleAnalysis(novelId)`。
- 新增 `analyzeNovelWritingStyleWithAI(novelId)`。
- 新增复制 `style_prompt` 的小函数，可优先使用 `navigator.clipboard.writeText`，失败时显示错误 toast。
- 在 `renderNovelDetail` 中重置、绑定按钮、打开详情时加载写作风格结果。

修改 `static/css/novels.css`：

- 新增 `.novel-writing-style-*` 样式。
- 复用设定集的白底卡片、边框和响应式网格模式。
- 提示词块使用等宽字体和浅色背景，保证长文本自动换行。
- 移动端维度卡片改为单列或双列，避免横向溢出。

## 错误处理

1. 小说不存在：读取和分析接口都返回 404。
2. 缺少可分析内容：分析接口返回 400，提示先填写书名或提供可读取文件。
3. 未配置 AI：分析接口返回 400，提示先在 AI 配置中激活可用模型。
4. AI JSON 解析失败：记录 failed 状态，返回 422。
5. AI 未返回可用风格结果：记录 failed 状态，返回 500。
6. 前端加载失败：只更新写作风格面板状态，不影响详情页其他 tab。
7. 复制提示词失败：显示错误 toast，不影响已生成内容。

## 测试计划

Python 测试新增 `tests/writing_style_analysis.test.py`：

- 成功调用分析接口后持久化写作风格结果。
- GET 接口能读回已保存的风格结果。
- AI 请求上下文包含正文片段。
- 不存在小说返回 404。
- schema 可重复执行，新增表和关键字段存在。
- AI 返回数组字段和异常字段时能归一化。

Node 静态测试新增 `tests/writing-style-ui.test.js`：

- 模板包含写作风格 tab、panel、按钮、状态节点和展示容器。
- `core.js` 跟踪 `detailWritingStyleAnalysis`。
- `novels.js` 包含 reset、render、load、analyze 函数。
- 前端调用 `/api/novels/${novelId}/writing-style`。
- 前端调用 `/api/ai/novels/${novelId}/writing-style/analyze`。
- 文案包含“AI 正在提取写作风格”和成功提示。
- CSS 包含 `.novel-writing-style-panel`、`.novel-writing-style-grid`、`.novel-writing-style-card`、`.novel-writing-style-prompt`。

回归检查：

```powershell
python -m py_compile app.py ai_client.py ai_routes.py crawler_routes.py reader_utils.py storage_utils.py
node --check static/js/app.js
node --check static/js/novels.js
python tests/writing_style_analysis.test.py
node tests/writing-style-ui.test.js
python tests/novel_setting_analysis.test.py
python tests/character_analysis.test.py
node tests/novel-setting-ui.test.js
node tests/character-analysis-ui.test.js
```

## 验收标准

1. 小说详情页能看到“写作风格”tab。
2. 点击“AI 提取风格”后，成功时展示风格总览、分析维度、代表技法、代表片段、仿写指南和风格提示词。
3. 刷新页面后已生成的风格结果仍可读回。
4. 风格提示词可以一键复制。
5. AI 失败时展示错误状态，并允许重试。
6. 设定集和角色卡功能保持原有行为。
7. 新增 Python 和 Node 测试通过，相关回归测试通过。
