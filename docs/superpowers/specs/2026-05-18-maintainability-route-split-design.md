# 后端路由可维护性重构设计

## 目标

把 `app.py` 从“应用入口 + 数据库初始化 + 大量业务路由”的混合文件，收敛为应用入口和路由注册中心。第一阶段只移动后端路由代码，不改变 API 路径、请求参数、响应结构、数据库 schema 或前端行为。

## 范围

- 保持 `/api/*` 公开路由列表不变。
- 新增小型路由模块，按职责拆分现有 `app.py` 里的业务接口。
- 保留现有 `get_db()`、`init_db()`、`storage_utils.py`、`reader_utils.py` 和已有 AI/角色/爬虫/管理员路由注册方式。
- 加强结构测试，防止 `app.py` 再次变成大型业务文件。

不在本阶段处理前端模板拆分、CSS 重组、认证/CORS 安全策略或数据库迁移框架。

## 模块设计

- `novel_routes.py`：小说列表、详情、增删改、上传、下载、文件检查、路径修复。
- `reader_routes.py`：阅读器打开、章节读取、阅读进度保存。
- `taxonomy_routes.py`：分类、标签、统计接口。
- `import_routes.py`：文件夹扫描和批量导入。
- `batch_routes.py`：批量标签、分类、状态、删除操作。
- `app.py`：Flask 实例、密钥、数据库连接、schema 初始化、路由注册和启动逻辑。

各路由模块通过 `register_*_routes(app, ..., get_db=...)` 接收依赖，延续现有 `ai_routes.py`、`character_routes.py`、`crawler_routes.py` 的风格。

## 测试策略

先修改 `tests/app_structure.test.py`，让它要求新模块存在、`app.py` 不直接声明 `/api` 路由、入口文件行数明显下降，并继续验证公开路由表不变。测试先失败，再移动代码让它通过。最后运行核心 Python 行为测试和语法检查。
