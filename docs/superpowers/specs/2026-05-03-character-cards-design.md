# 角色卡升级设计

## 背景

当前小说详情页已经有“角色关系”功能：后端通过 AI 分析角色和关系，保存到 `novel_characters`、`novel_character_relations` 和 `novel_character_analysis_runs`，前端在详情页的“角色关系”Tab 中展示角色列表、关系谱和关系列表。

这套能力已经能支撑角色识别，但用户感知仍是“关系图附属信息”。本次升级目标是把它变成以角色为中心的“角色卡”功能，让用户打开详情页时能快速理解每个角色是谁、有什么特征、在故事中的作用，以及与其他角色的连接。

## 目标

1. 将详情页入口从“角色关系”升级为“角色卡”。
2. 保留现有 AI 分析、角色关系、关系谱能力，避免推倒重来。
3. 为每个角色增加更完整的卡片字段，包括一句话定位、外貌或气质、性格、动机、能力或特长、首次出现、关键证据、相关角色。
4. 保持旧数据兼容：已有角色分析记录仍可正常展示，只是缺少新增字段时显示精简卡片。
5. 第一版支持 AI 生成和展示，不加入手动编辑、跨书角色库、角色头像生成。

## 非目标

1. 不做全局角色库，不把同名角色跨小说合并。
2. 不做角色卡手动编辑表单。
3. 不做图片头像生成或上传。
4. 不新增独立页面，继续放在小说详情弹窗中。
5. 不改变小说列表、阅读器、批量导入等无关流程。

## 用户体验

小说详情页保留三个 Tab：概览、本地文件、角色卡。原“角色关系”Tab 改名为“角色卡”，图标可以从关系图标调整为身份卡或用户组图标。

角色卡 Tab 顶部显示分析状态和操作按钮：

- 未分析：显示“尚未生成角色卡”，按钮为“AI 生成角色卡”。
- 分析中：显示“AI 正在生成角色卡...”。
- 完成：显示“已生成 N 张角色卡、M 条关系”。
- 失败：显示失败原因，并允许重新生成。

主体布局分为两块：

1. 角色卡区域：作为主内容，使用卡片网格展示角色。每张卡包含姓名、角色定位、别名、角色摘要、性格或特征标签、动机、能力或特长、首次出现、可信度和证据片段。
2. 关系区域：作为辅助内容，保留关系谱和关系列表。关系谱不再压过角色卡，可放在角色卡下方或右侧，窄屏下自然堆叠。

旧数据展示规则：

- `summary` 缺失时使用现有 `description`。
- `personality` 缺失时使用现有 `traits`。
- `first_seen` 缺失时使用 `first_chapter_index`。
- 扩展字段都缺失时仍展示姓名、定位、描述、特征、证据和可信度。

## 数据设计

沿用现有三张表，只给 `novel_characters` 增加一个扩展字段：

```sql
ALTER TABLE novel_characters ADD COLUMN profile_json TEXT DEFAULT '{}';
```

`profile_json` 保存角色卡扩展信息：

```json
{
  "summary": "一句话角色定位",
  "appearance": "外貌或气质描述",
  "personality": ["冷静", "执着"],
  "motivation": "当前明确动机",
  "skills": ["推理", "行动力"],
  "first_seen": "第一章 星河钥匙",
  "card_evidence": "支持角色卡判断的文本片段"
}
```

继续保留现有字段：

- `name`：角色名。
- `aliases_json`：别名。
- `role_type`：主角、反派、同伴、配角、未知等。
- `description`：角色说明，兼容旧展示。
- `traits_json`：旧特征标签，兼容旧展示。
- `first_chapter_index`：旧首次章节索引。
- `evidence`：旧证据片段。
- `confidence`：可信度。

这样做的原因是新增字段仍属于单个角色的描述，不需要拆成新表；同时可以减少迁移风险和前端调用变化。

## 后端设计

继续使用现有接口：

- `GET /api/novels/<novel_id>/characters`
- `POST /api/ai/novels/<novel_id>/characters/analyze`

接口路径不改，语义升级为“获取或生成角色卡与关系”。这样可以降低前端和测试变动，也避免破坏已有路由结构测试。

需要调整的后端行为：

1. `ensure_character_analysis_schema` 检查 `novel_characters` 是否存在 `profile_json`，不存在时添加。
2. `normalize_character_analysis_payload` 接收新格式字段，同时兼容旧格式字段。
3. `replace_character_analysis` 写入 `profile_json`。
4. `serialize_character_analysis` 解析 `profile_json` 并把 `profile` 放进每个 character 对象。
5. AI 提示词从“角色关系分析”升级为“角色卡生成和角色关系分析”。

AI 返回格式建议：

```json
{
  "characters": [
    {
      "name": "角色名",
      "aliases": ["别名"],
      "role_type": "主角",
      "summary": "一句话角色定位",
      "description": "较完整的角色说明",
      "appearance": "外貌或气质",
      "personality": ["性格标签"],
      "motivation": "明确动机",
      "skills": ["能力或特长"],
      "first_seen": "首次出现位置",
      "first_chapter_index": 0,
      "evidence": "证据片段",
      "confidence": 0.8
    }
  ],
  "relations": [
    {
      "source": "角色A",
      "target": "角色B",
      "relation_type": "同盟",
      "description": "关系说明",
      "evidence": "证据片段",
      "confidence": 0.8
    }
  ]
}
```

归一化限制：

- 角色最多 24 个，AI 提示首版仍建议最多 12 个，后端保留较高上限兼容未来扩展。
- 关系最多 40 条，AI 提示首版仍建议最多 20 条。
- `summary` 最长 120 字符。
- `appearance`、`motivation`、`first_seen`、`card_evidence` 最长 180 字符。
- `personality` 和 `skills` 各最多 8 项，每项最长 18 字符。
- 所有字段只基于提供文本和小说已有元数据，不允许编造未出现的情节、关系和结局。

## 前端设计

`templates/index.html`：

- Tab 文案改为“角色卡”。
- 面板标题改为“角色卡”。
- 按钮文案改为“AI 生成角色卡”。
- 保留现有 `novel-character-*` id，减少 JavaScript 改动。

`static/js/novels.js`：

- `resetNovelCharacterAnalysis` 文案升级为角色卡。
- `renderNovelCharacterAnalysis` 改为渲染角色卡网格。
- 新增小函数读取 profile 字段，例如 `getCharacterProfile(character)`，统一兼容 `character.profile` 和旧字段。
- `analyzeNovelCharactersWithAI` 的状态、Toast 文案升级为角色卡。
- 关系谱函数可以继续复用 `renderCharacterRelationshipGraph`。

`static/css/novels.css`：

- 复用现有 `.novel-character-*` 样式，新增角色卡字段的层级样式。
- 角色卡区域应更像资料卡：姓名和定位在顶部，摘要为主要正文，标签和证据为辅助信息。
- 移动端保持单列，关系谱在卡片之后。

## 错误处理

1. AI 未识别到角色时，继续返回失败提示：“AI 未识别到可用角色卡，请换更多正文内容后重试”。
2. AI 返回旧格式时仍可保存并展示精简角色卡。
3. `profile_json` 解析失败时忽略扩展字段，不影响角色基础信息展示。
4. 已有失败状态继续通过 `analysis_status = failed` 和 `error_message` 展示。

## 测试计划

Python 测试：

- 更新 `tests/character_analysis.test.py`，验证 AI 生成角色卡后会持久化 `profile_json` 并通过 GET 接口返回 `profile`。
- 增加旧格式兼容断言：AI 只返回旧字段时仍能成功保存和读取。
- 保留不存在小说返回 404 的测试。

Node 静态测试：

- 更新 `tests/character-analysis-ui.test.js`，验证模板文案和按钮文案升级为角色卡。
- 验证前端仍调用现有两个接口。
- 验证 JS 中存在角色卡渲染逻辑、关系谱仍保留。
- 验证 CSS 中存在角色卡样式和关系谱样式。

通用检查：

```powershell
python -m py_compile app.py ai_client.py ai_routes.py crawler_routes.py reader_utils.py storage_utils.py
node --check static/js/app.js
node --check static/js/novels.js
python tests/character_analysis.test.py
node tests/character-analysis-ui.test.js
python tests/app_structure.test.py
```

## 实施顺序

1. 后端先加 schema 迁移和 profile 字段序列化。
2. 写 Python 测试覆盖新字段和旧格式兼容。
3. 调整 AI 提示词和 payload 归一化。
4. 调整前端模板文案。
5. 调整前端渲染和样式。
6. 更新 Node 静态测试。
7. 跑完整相关测试并修复回归。

## 验收标准

1. 打开小说详情页能看到“角色卡”Tab。
2. 点击“AI 生成角色卡”后，成功时显示角色卡数量和关系数量。
3. 每张角色卡至少展示姓名、角色定位、摘要、标签、证据和可信度。
4. AI 返回扩展字段时，前端展示动机、能力、外貌或气质、首次出现。
5. 旧角色关系数据不会报错，仍能以精简角色卡展示。
6. 关系谱和关系列表仍可查看。
7. 相关 Python 和 Node 测试通过。
