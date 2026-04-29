# 本地小说管理器

一个基于 Flask、SQLite 和原生前端的本地小说管理 Web 应用。它用于整理本地小说文件、维护分类和标签、记录阅读状态，并提供本地 TXT 阅读、批量导入、AI 元数据生成和网页抓取入库等辅助能力。

本项目仅供学习、研究和个人本地使用，请勿用于任何违反目标站点服务条款、版权法规或其他法律法规的用途。

## 功能概览

- 小说管理：新增、编辑、删除小说，维护书名、作者、简介、文件路径、分类、标签、阅读状态和书籍详情档案。
- 本地阅读：支持 TXT 文件章节识别、章节切换、正文阅读、阅读进度自动恢复、阅读偏好设置、沉浸阅读和单本下载。
- 全文搜索：支持对可在线阅读的 TXT 正文建立 SQLite FTS 索引，按关键词定位命中小说和章节。
- 分类与标签：支持自定义分类、彩色标签、多标签筛选、仅看无标签小说。
- 批量操作：支持批量添加标签、设置分类、设置阅读状态、删除小说和批量 AI 生成简介/标签。
- 批量导入：支持选择本地文件夹扫描小说文件，并按文件夹自动推断分类。
- AI 配置：支持配置 OpenAI、Anthropic、Gemini 兼容接口，测试连接，并用于小说简介和标签生成。
- 爬虫管理：支持创建抓取任务、站点规则、列表页批量建任务、任务重试、任务恢复和抓取结果入库。
- 本地优先：数据库和上传文件默认保存在项目本地，方便备份和迁移。

## 技术栈

- 后端：Python 3、Flask、Flask-CORS、SQLite
- 前端：HTML、CSS、原生 JavaScript、Font Awesome
- AI SDK：OpenAI、Anthropic、Google Generative AI
- 网页解析：Requests、BeautifulSoup4、chardet

## 目录结构

```text
novel/
├── app.py                 # Flask 后端与 API
├── ai_client.py           # AI 供应商适配与调用封装
├── search_routes.py       # TXT 全文搜索索引与接口
├── requirements.txt       # Python 依赖
├── README.md              # 项目说明
├── templates/
│   └── index.html         # 单页应用模板
├── static/
│   ├── css/
│   │   ├── style.css      # CSS 入口，按顺序引入样式分片
│   │   ├── base.css       # 基础变量与全局样式
│   │   ├── layout.css     # 应用布局、侧边栏与顶部栏
│   │   ├── components.css # 通用按钮和内容区域
│   │   ├── novels.css     # 小说列表、分类和标签
│   │   ├── forms.css      # 弹窗、表单、空态和提示
│   │   ├── import.css     # 批量导入
│   │   ├── batch.css      # 批量操作
│   │   ├── crawler.css    # 爬虫管理
│   │   ├── reader.css     # 阅读器
│   │   ├── ai.css         # AI 配置
│   │   └── overrides.css  # 页面刷新后的覆盖和细化样式
│   └── js/
│       ├── core.js        # 前端共享状态、API 与通用工具
│       ├── novels.js      # 小说、分类、标签和筛选交互
│       ├── reader.js      # TXT 阅读器与阅读进度
│       ├── crawler.js     # 爬虫规则和任务交互
│       ├── ai.js          # AI 配置、模型测试和聊天
│       ├── batch.js       # 批量操作和批量 AI
│       ├── import.js      # 批量导入
│       └── app.js         # 应用初始化和事件绑定入口
├── tests/
│   ├── novel-card-ui.test.js
│   └── novels-view-hero.test.js
└── library/               # 本地上传/导入文件目录，运行时生成，不提交
```

运行时会生成 `novels.db`、日志文件和 `library/` 内容，这些属于本地数据，不建议提交到远程仓库。

## 快速开始

### 1. 安装依赖

建议先创建虚拟环境：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python app.py
```

默认监听：

```text
http://localhost:5000
```

首次启动会自动初始化 SQLite 数据库和必要表结构。

## 常用操作

### 小说列表

进入首页后可以搜索小说名或作者，并按分类、标签、阅读状态筛选。搜索框右侧开启“全文”后，会对可在线阅读的 TXT 正文和章节进行全文搜索，结果会展示命中小说、章节和摘要，点击可直接打开对应章节。卡片上提供详情、阅读、下载、编辑和删除操作；详情页会集中展示简介、标签、阅读进度、最近阅读时间、章节数、字数、文件路径、文件大小和文件检查状态。左上角圆形勾选控件用于批量操作。打开 TXT 小说阅读时会自动恢复到上次阅读的章节和滚动位置，阅读器支持主题、字号、行高、正文宽度、段落间距、目录收起和沉浸模式。

### 添加小说

点击“添加小说”，填写书名、作者、简介、分类、状态和标签。可以手动填写文件路径，也可以选择本地文件上传到 `library/`。

### 批量导入

点击“批量导入”，选择本地文件夹后，系统会扫描支持的小说文件，并可按文件夹自动创建分类。导入时可统一设置标签和默认阅读状态。

支持的文件类型包括：

```text
.txt .epub .pdf .mobi .azw3 .doc .docx .rtf
```

当前在线阅读主要面向 TXT 文件。

### AI 功能

在“AI 配置”中添加供应商配置并设为启用后，可以：

- 测试 AI 对话连接。
- 在单本小说编辑时生成简介和标签。
- 对已勾选的多本小说批量生成简介和标签，并逐本确认后写回数据库。

API Key 等敏感配置只保存在本地数据库中，请自行做好本地备份和权限管理。

### 爬虫管理

在“爬虫管理”中可以维护站点规则和抓取任务。

站点规则支持配置：

- 域名匹配规则。
- 书名、章节标题、正文选择器。
- 列表页链接选择器。
- 同书关联帖子选择器。
- 章节链接选择器。
- 需要从正文中移除的广告或工具栏选择器。

项目已内置以下站点规则：

| 站点规则 | 域名匹配 | 支持能力 |
| --- | --- | --- |
| cool18 禁忌书屋帖子页 | `www.cool18.com` | 支持 threadview 帖子正文抓取、列表页批量建任务、同书关联帖子合并。 |
| AliceSW 小说页 | `www.alicesw.com` | 支持小说详情页、目录页和章节页抓取，章节正文通过站点接口解密提取。 |
| Linovelib 轻小说 | `*.linovelib.com` | 支持目录与正文抓取，并自动合并同章节分页。 |
| Bilinovel 轻小说 | `*.bilinovel.com` | 支持目录与正文抓取，并自动合并同章节分页。 |
| Kakuyomu | `kakuyomu.jp` | 支持作品目录与章节正文抓取，优先从 `__NEXT_DATA__` / `__APOLLO_STATE__` 提取目录。 |
| 小説家になろう | `*.syosetu.com` | 支持 syosetu / ncode 目录与正文抓取。 |
| Novel18 | `novel18.syosetu.com` | 支持 Novel18 目录与正文抓取，抓取时自动附带 `over18` cookie。 |
| Pixiv 小说 | `www.pixiv.net` | 支持 Pixiv 单篇与系列，目录和正文通过 ajax 接口抓取。 |
| Hameln | `syosetu.org` | 支持目录与正文抓取，正文会附加后记内容。 |
| Alphapolis | `www.alphapolis.co.jp` | 支持解析 `#app-cover-data` 获取目录和正文，必要时通过 Edge CDP 会话兜底抓取。 |

抓取任务支持：

- 自动匹配或手动指定站点规则。
- 把当前链接当作列表页，批量创建最近帖子抓取任务。
- 自动重试、失败原因记录、服务重启后恢复运行中任务。
- 抓取成功后写入小说库并关联本地文件。

默认情况下，爬虫会拒绝抓取本地地址或内网地址。如果确实需要抓取内网目标，可以在启动前设置：

```powershell
$env:ALLOW_PRIVATE_CRAWLER_TARGETS='1'
python app.py
```

或在 macOS / Linux 中：

```bash
ALLOW_PRIVATE_CRAWLER_TARGETS=1 python app.py
```

只建议在可信网络和明确知道目标地址的情况下开启。

## 数据与备份

主要本地数据：

- `novels.db`：SQLite 数据库，保存小说元数据、分类、标签、AI 配置和爬虫任务。
- `library/`：上传、导入和抓取生成的小说文件。
- `server-*.log`：本地启动或调试日志。

备份时建议同时备份 `novels.db` 和 `library/`。这些文件默认不纳入 Git。

## 测试与检查

当前仓库包含轻量 Node 与 Python 回归测试：

```bash
node tests/frontend-split.test.js
node tests/frontend-css-split.test.js
node tests/novel-detail-ui.test.js
node tests/reader-experience-ui.test.js
node tests/full-text-search-ui.test.js
node tests/novels-view-hero.test.js
node tests/novel-card-ui.test.js
python tests/app_structure.test.py
python tests/full_text_search.test.py
python tests/novel_detail_file.test.py
```

常用提交前检查：

```bash
python -m py_compile app.py ai_client.py ai_routes.py crawler_routes.py reader_utils.py search_routes.py storage_utils.py
node --check static/js/app.js
node --check static/js/novels.js
node tests/frontend-split.test.js
node tests/frontend-css-split.test.js
node tests/novel-detail-ui.test.js
node tests/reader-experience-ui.test.js
node tests/full-text-search-ui.test.js
node tests/novels-view-hero.test.js
node tests/novel-card-ui.test.js
python tests/app_structure.test.py
python tests/full_text_search.test.py
python tests/novel_detail_file.test.py
git diff --check
```

## 部署说明

当前项目面向本地使用和个人书库管理。生产部署前建议至少补充：

- 登录认证和访问控制。
- HTTPS 与反向代理配置。
- 更严格的文件上传大小、类型和路径限制。
- 数据库备份策略。
- API Key 加密或更安全的密钥管理方式。

## GitHub 推送

本地仓库远端地址：

```bash
git@github.com:livesstart/novel-manage.git
```

如果 SSH Key 已配置并拥有仓库权限，可以执行：

```bash
git push -u origin master
```

如果出现 `Permission denied (publickey)`，需要先把本机 SSH 公钥添加到 GitHub 账户，或改用已登录的 HTTPS 远端。
