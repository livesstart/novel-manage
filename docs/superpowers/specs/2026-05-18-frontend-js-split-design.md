# 前端 JS 可维护性拆分设计

## 目标

在不改变用户行为、不引入打包器、不调整 CSS 视觉层的前提下，把前端最大、最难维护的原生 JavaScript 文件拆成按职责命名的小文件。第一阶段聚焦 `novels.js` 和 `app.js`。

## 范围

- 保持现有全局函数调用方式和 `<script>` 顺序加载模式。
- 保持所有 DOM id、class、API 调用、响应处理和 UI 文案不变。
- 不改 `static/css/*`，不做视觉重构。
- 新增结构测试，约束脚本顺序、文件存在和单个前端文件体积，防止后续重新膨胀。

## 模块设计

`novels.js` 拆成：

- `novel-render.js`：小说列表、分类、标签和选择器渲染。
- `novel-detail.js`：小说详情、设定/角色/写作风格展示和 AI 分析入口。
- `novel-download.js`：文件打开、下载、Content-Disposition 文件名解析。
- `novels.js`：保留小说 CRUD、筛选、表单状态和对外入口函数。

`app.js` 拆成：

- `app-bindings.js`：按功能组织事件绑定函数。
- `app.js`：保留初始化流程和跨模块启动顺序。

## 测试策略

先更新 `tests/frontend-split.test.js`，让它要求新增脚本按正确顺序加载，并限制 `novels.js` 与 `app.js` 的行数。测试应先失败，再移动代码使其通过。最终运行所有 Node UI 回归测试、JS 语法检查、核心 Python 测试和 `git diff --check`。
