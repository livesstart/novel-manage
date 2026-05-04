# 全新角色卡系统设计

## 背景

当前角色卡功能是在小说详情页的“角色卡”Tab 中展示 AI 分析结果。虽然已经支持 `profile_json`、角色卡字段和关系谱，但用户感知仍接近旧的“角色关系分析增强版”：入口仍在小说详情内，展示仍围绕单本小说，角色本身还不是一个可维护的资料实体。

本次设计目标是把角色卡升级为独立系统：新增全局“角色库”主页面，支持统一搜索、筛选、编辑、AI 补全、按小说批量生成，以及轻量关系维护。小说详情页保留角色卡入口，但它只是该书角色库的子视图，不再是唯一入口。

## 产品定位

角色卡系统第一版同时服务两个核心目标：

1. 写作资料库：角色卡是可编辑档案，用户可以维护身份、标签、简介、性格、动机、能力、外貌和备注。
2. 检索管理系统：角色库是全局入口，用户可以跨全部小说搜索、筛选和管理角色。

角色仍按小说独立保存。同名角色出现在不同小说中，也视为不同角色。第一版不做跨书合并、相似角色提示或自动归并。

## 目标

1. 左侧导航新增“角色库”，作为和小说列表、分类管理、标签管理同级的主功能。
2. 角色库支持搜索、小说筛选、身份筛选、标签筛选和排序。
3. 角色以可扫描的卡片网格展示。
4. 点击角色卡打开详情抽屉，查看和编辑完整标准档案字段。
5. 支持手动新建、编辑、删除角色卡。
6. 支持单张角色 AI 补全。
7. 支持按小说 AI 批量生成角色卡和同书角色关系。
8. 支持轻量关系新增、编辑、删除。
9. 小说详情页的“角色卡”Tab 保留，但升级为该小说角色库子视图。
10. 兼容已有角色卡数据和现有 API，不破坏当前角色关系谱能力。

## 非目标

1. 不做跨书角色合并。
2. 不做角色头像、图片上传或图片生成。
3. 不做角色导入导出。
4. 不做角色时间线。
5. 不做章节证据管理。
6. 不做批量删除或批量编辑角色。
7. 不做完整关系库、关系筛选或关系统计面板。

## 信息架构

### 左侧导航

新增主导航项：

- 角色库

角色库位于“小说列表”之后或“标签管理”之后，图标使用 Font Awesome 中的身份卡、用户组或地址卡图标。它进入独立视图 `view-characters`。

### 角色库页面

角色库页面由三部分组成：

1. 顶部工具栏
   - 搜索框：按角色名、别名、简介、备注搜索。
   - 小说筛选：选择一本小说，只看该书角色。
   - 身份筛选：按 `role_type` 筛选，例如主角、反派、同伴、配角、未知。
   - 标签筛选：按角色标签筛选。
   - 排序：最近更新、名称、所属小说、身份。
   - 操作按钮：新建角色、AI 批量生成。

2. 角色卡网格
   - 每张卡显示角色名、所属小说、身份、标签、简介摘要、最近更新时间。
   - 空状态显示当前筛选下没有角色，并提供新建角色和 AI 生成入口。
   - 点击卡片打开详情抽屉。

3. 角色详情抽屉
   - 展示完整角色档案。
   - 支持编辑、保存、删除、AI 补全。
   - 底部展示同书相关角色关系，并支持轻量编辑。

### 小说详情页角色卡 Tab

保留当前小说详情中的“角色卡”Tab，但调整定位：

- 它展示该小说的角色卡子集。
- 它提供“打开角色库查看全部”入口，并跳转到角色库页面且自动带上 `novel_id` 筛选。
- 它保留“AI 生成该书角色卡”按钮。
- 它不再承担完整编辑体验；编辑仍通过角色详情抽屉完成。

## 角色卡字段

第一版使用标准档案型字段：

- `name`：角色名，必填。
- `aliases`：别名数组。
- `novel_id`：所属小说，必填。
- `novel_title`：所属小说标题，只读展示字段。
- `role_type`：身份定位，例如主角、反派、同伴、配角、未知。
- `tags`：角色标签数组，存放在 `profile_json.tags` 或等价结构中。
- `description`：角色简介。
- `traits`：性格或特征标签数组。
- `motivation`：动机。
- `skills`：能力或特长数组。
- `appearance`：外貌或气质。
- `notes`：用户备注。
- `confidence`：AI 可信度，手动角色可为空或 0。
- `is_manual`：是否由用户手动维护过。
- `updated_at`：最近更新时间。

现有 `profile_json` 继续用于扩展字段：

```json
{
  "summary": "一句话角色定位",
  "appearance": "外貌或气质",
  "personality": ["冷静", "执着"],
  "motivation": "当前明确动机",
  "skills": ["推理", "行动力"],
  "tags": ["核心角色", "调查者"]
}
```

前端展示时：

- `summary` 缺失时使用 `description`。
- `personality` 缺失时使用 `traits`。
- `tags` 缺失时显示为空标签。
- `notes` 只展示用户手动备注，不由 AI 自动覆盖。

## 数据模型

### `novel_characters`

继续作为角色卡主表。角色按小说独立，不跨书合并。

需要新增或明确字段：

```sql
ALTER TABLE novel_characters ADD COLUMN notes TEXT DEFAULT '';
ALTER TABLE novel_characters ADD COLUMN is_manual INTEGER DEFAULT 0;
```

现有字段继续使用：

- `id`
- `novel_id`
- `name`
- `aliases_json`
- `role_type`
- `description`
- `traits_json`
- `profile_json`
- `first_chapter_index`
- `evidence`
- `confidence`
- `sort_order`
- `created_at`
- `updated_at`

### `novel_character_relations`

继续作为同书角色关系表。第一版支持轻量手动编辑。

需要新增或明确字段：

```sql
ALTER TABLE novel_character_relations ADD COLUMN is_manual INTEGER DEFAULT 0;
```

关系只允许连接同一本小说内的两个角色。后端在新增和更新关系时必须验证 source、target 属于同一 `novel_id`。

### `novel_character_analysis_runs`

保留作为 AI 批量生成记录。它不再代表角色库本身，只记录最近一次批量生成状态、模型、数量和错误信息。

## API 设计

### 全局角色库

`GET /api/characters`

查询角色库列表。

Query 参数：

- `keyword`
- `novel_id`
- `role_type`
- `tag`
- `sort`

返回：

```json
{
  "success": true,
  "data": {
    "items": [],
    "total": 0
  }
}
```

`POST /api/characters`

手动新建角色卡。

请求字段：

- `novel_id`
- `name`
- `aliases`
- `role_type`
- `description`
- `traits`
- `profile`
- `notes`

`GET /api/characters/<id>`

获取单张角色卡详情，包括所属小说、完整 profile 和该角色关系。

`PUT /api/characters/<id>`

编辑角色卡。保存后设置 `is_manual = 1`，更新 `updated_at`。

`DELETE /api/characters/<id>`

删除角色卡，同时删除该角色作为 source 或 target 的关系。

### AI 补全

`POST /api/characters/<id>/ai-complete`

对单张角色卡进行 AI 补全。

输入上下文：

- 角色当前字段。
- 所属小说标题、作者、简介。
- 可读取正文片段。

行为：

- 不自动改 `name`。
- 不自动改 `novel_id`。
- 优先补空字段。
- 如果字段已有内容，可返回优化后的建议并由用户选择保存。第一版可以简化为直接写入空字段，不覆盖非空手动字段。
- 不写入 `notes`。

### 小说级角色生成

`GET /api/novels/<id>/characters`

保留现有接口，返回该小说角色卡列表。

`POST /api/ai/novels/<id>/characters/analyze`

保留现有批量生成接口，语义升级为“AI 生成该书角色卡和关系”。

第一版冲突策略：

- 同一本小说内已存在同名角色时，AI 生成结果覆盖 AI 管理字段。
- 如果该角色 `is_manual = 1`，不覆盖 `notes`，并尽量不覆盖非空手动字段。
- 新角色直接插入。
- 关系按 AI 结果重建或更新；手动关系 `is_manual = 1` 时保留。

### 关系编辑

`POST /api/characters/<id>/relations`

新增该角色与同书另一角色的关系。

请求字段：

- `target_character_id`
- `relation_type`
- `description`

`PUT /api/character-relations/<relation_id>`

编辑关系类型和说明，设置 `is_manual = 1`。

`DELETE /api/character-relations/<relation_id>`

删除关系。

## 交互流程

### 浏览和检索

1. 用户点击左侧“角色库”。
2. 系统加载全局角色卡列表。
3. 用户通过搜索、小说筛选、身份筛选、标签筛选缩小结果。
4. 用户点击角色卡打开详情抽屉。

### 手动新建角色

1. 用户点击“新建角色”。
2. 系统打开角色编辑抽屉或弹窗。
3. 用户选择所属小说，填写角色名和标准档案字段。
4. 保存后角色出现在角色库中。
5. 用户可继续点击“AI 补全”补齐空字段。

### 编辑角色

1. 用户打开角色详情抽屉。
2. 点击编辑或直接在表单中修改。
3. 保存后更新角色卡，设置 `is_manual = 1`。
4. 列表卡片同步刷新。

### 单张 AI 补全

1. 用户打开角色详情抽屉。
2. 点击“AI 补全”。
3. 系统调用 `POST /api/characters/<id>/ai-complete`。
4. 后端基于当前角色和小说上下文生成补全字段。
5. 前端显示补全后的角色卡。

### 小说级 AI 批量生成

1. 用户在角色库选择一本小说，或在小说详情角色卡 Tab 点击“AI 生成该书角色卡”。
2. 系统调用现有小说级分析接口。
3. AI 返回角色卡和关系。
4. 后端写入该小说角色卡和关系。
5. 角色库刷新到该小说筛选结果。

### 关系维护

1. 用户打开角色详情抽屉。
2. 在“相关角色”区新增、编辑或删除关系。
3. 新增关系时只能选择同书角色。
4. 保存关系后更新当前角色详情和关系谱。

## 前端设计

### 新增视图

新增 `view-characters`，由 `static/js/characters.js` 或现有模块中的角色库区域驱动。考虑当前 `novels.js` 已经较大，第一版建议新增独立前端文件：

- `static/js/characters.js`
- `static/css/characters.css`

`templates/index.html` 新增角色库视图和角色详情抽屉 DOM。

### 状态结构

新增前端状态：

```javascript
const characterState = {
  items: [],
  filters: {
    keyword: '',
    novelId: '',
    roleType: '',
    tag: '',
    sort: 'updated_desc'
  },
  activeCharacter: null,
  isLoading: false,
  isSaving: false
};
```

### 页面组件

1. `renderCharacterLibrary()`
2. `renderCharacterFilters()`
3. `renderCharacterCards()`
4. `openCharacterDrawer(characterId)`
5. `renderCharacterDrawer(character)`
6. `saveCharacter()`
7. `deleteCharacter()`
8. `completeCharacterWithAI()`
9. `saveCharacterRelation()`

### 视觉方向

角色库应区别于小说详情：

- 主页面使用角色卡网格，不再围绕关系谱。
- 卡片顶部突出角色名和所属小说。
- 身份、标签和更新时间用于快速扫描。
- 详情抽屉承载完整编辑表单。
- 关系区位于抽屉底部，是角色档案的辅助信息。

## 错误处理

1. 新建角色缺少 `novel_id` 或 `name` 时返回 400。
2. 编辑不存在角色返回 404。
3. 删除角色时同步删除关系；失败时事务回滚。
4. 新增关系时，如果目标角色不存在或不属于同一本小说，返回 400。
5. AI 未配置时返回现有 AI 配置错误。
6. AI 返回不可解析内容时保留当前角色，不写入半成品。
7. 角色库列表加载失败时保留当前筛选条件并显示错误状态。

## 测试计划

### 后端测试

1. `GET /api/characters` 支持全局列表、关键词、小说、身份和标签筛选。
2. `POST /api/characters` 可以新建角色。
3. `PUT /api/characters/<id>` 可以编辑标准档案字段并设置 `is_manual = 1`。
4. `DELETE /api/characters/<id>` 会删除该角色和相关关系。
5. `POST /api/characters/<id>/ai-complete` 可以补全空字段，不覆盖 `notes`。
6. 小说级 AI 批量生成可以写入角色和关系。
7. 批量生成遇到 `is_manual = 1` 角色时保留手动备注。
8. 新增关系时拒绝跨小说角色。
9. 旧角色卡数据仍能通过现有接口和新列表接口展示。

### 前端静态测试

1. 左侧导航包含“角色库”。
2. 模板包含 `view-characters`。
3. 模板包含角色库搜索、小说筛选、身份筛选、标签筛选、排序、新建和 AI 批量生成入口。
4. 模板包含角色卡网格和角色详情抽屉。
5. JS 包含角色库加载、筛选、渲染、详情打开、保存、删除、AI 补全、关系编辑函数。
6. JS 调用新增 API 路径。
7. CSS 包含角色库页面、角色卡、详情抽屉和关系编辑样式。
8. 小说详情角色卡 Tab 包含“打开角色库查看全部”入口。

### 回归测试

继续运行：

```powershell
python tests/character_analysis.test.py
python tests/app_structure.test.py
node tests/character-analysis-ui.test.js
node tests/novel-detail-ui.test.js
python -m py_compile app.py ai_client.py ai_routes.py crawler_routes.py reader_utils.py storage_utils.py
node --check static/js/app.js
node --check static/js/core.js
node --check static/js/novels.js
```

新增角色库文件后补充：

```powershell
node --check static/js/characters.js
node tests/character-library-ui.test.js
python tests/character_library.test.py
```

## 验收标准

1. 左侧导航能进入独立“角色库”页面。
2. 角色库能全局搜索和筛选角色。
3. 用户能手动新建角色卡。
4. 用户能编辑和删除角色卡。
5. 角色详情抽屉能维护标准档案字段。
6. 用户能对单张角色执行 AI 补全。
7. 用户能对一本小说执行 AI 批量生成角色卡。
8. 用户能新增、编辑、删除同书角色关系。
9. 小说详情里的角色卡 Tab 是该书角色库入口，不再只是旧关系分析展示。
10. 旧角色数据仍能正常显示。
11. 所有新增和回归测试通过。

## 实施顺序

1. 后端角色库 API 和 schema 扩展。
2. 后端角色 CRUD 测试和实现。
3. 后端关系编辑测试和实现。
4. 单张 AI 补全测试和实现。
5. 前端角色库静态测试。
6. 前端新增角色库视图、卡片网格和详情抽屉。
7. 前端接入 CRUD、AI 补全和关系编辑。
8. 小说详情角色卡 Tab 调整为角色库子视图入口。
9. 回归验证和视觉检查。
