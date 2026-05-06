# Local Novel Manager

**Language:** [简体中文](README.md) | [English](README.en.md)

A local novel management web application built with Flask, SQLite, and a vanilla frontend. It helps organize local novel files, manage categories and tags, track reading status, and provides local TXT reading, batch import, AI metadata generation, and web crawling into the local library.

This project is intended only for learning, research, and personal local use. Do not use it for any purpose that violates target site terms of service, copyright rules, or applicable laws and regulations.

## Features

- Novel management: create, edit, and delete novels, and maintain title, author, description, file path, category, tags, reading status, and detail metadata.
- Local reading: TXT chapter detection, chapter switching, text reading, reading progress restoration, reader preferences, immersive reading, and single-book download.
- Categories and tags: custom categories, colored tags, multi-tag filtering, and filtering novels without tags.
- Batch operations: batch add tags, set categories, update reading status, delete novels, and generate descriptions/tags with AI.
- Batch import: scan a local folder for novel files and infer categories from folder names.
- AI configuration: configure OpenAI, Anthropic, Gemini, or OpenAI-compatible endpoints, test connections, and generate novel descriptions, tags, settings, characters, and character relationships.
- Crawler management: create crawl tasks, manage site rules, batch-create tasks from list pages, retry tasks, resume tasks, and save crawl results to the local library.
- Local-first storage: the database and uploaded files are stored locally by default for easier backup and migration.

## Tech Stack

- Backend: Python 3, Flask, Flask-CORS, SQLite
- Frontend: HTML, CSS, vanilla JavaScript, Font Awesome
- AI SDKs: OpenAI, Anthropic, Google Generative AI
- Web parsing: Requests, BeautifulSoup4, chardet

## Project Structure

```text
novel/
|-- app.py                 # Flask backend and APIs
|-- ai_client.py           # AI provider adapters and call wrappers
|-- requirements.txt       # Python dependencies
|-- README.md              # Chinese documentation
|-- README.en.md           # English documentation
|-- templates/
|   `-- index.html         # Single-page application template
|-- static/
|   |-- css/
|   |   |-- style.css      # CSS entry, imports split styles in order
|   |   |-- base.css       # Base variables and global styles
|   |   |-- layout.css     # App layout, sidebar, and top bar
|   |   |-- components.css # Shared buttons and content regions
|   |   |-- novels.css     # Novel list, categories, and tags
|   |   |-- forms.css      # Dialogs, forms, empty states, and hints
|   |   |-- import.css     # Batch import
|   |   |-- batch.css      # Batch operations
|   |   |-- crawler.css    # Crawler management
|   |   |-- reader.css     # Reader
|   |   |-- ai.css         # AI configuration
|   |   `-- overrides.css  # Post-refresh overrides and refinements
|   `-- js/
|       |-- core.js        # Shared frontend state, APIs, and utilities
|       |-- novels.js      # Novel, category, tag, and filter interactions
|       |-- reader.js      # TXT reader and reading progress
|       |-- crawler.js     # Crawler rules and task interactions
|       |-- ai.js          # AI configuration, model tests, and chat
|       |-- batch.js       # Batch operations and batch AI
|       |-- import.js      # Batch import
|       `-- app.js         # App initialization and event binding entry
|-- tests/
|   |-- novel-card-ui.test.js
|   `-- novels-view-hero.test.js
`-- library/               # Local upload/import output, generated at runtime and not committed
```

Runtime files such as `novels.db`, logs, and `library/` content are local data and should not be committed to the remote repository.

## Quick Start

### 1. Install Dependencies

Creating a virtual environment first is recommended:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the Server

```bash
python app.py
```

Default URL:

```text
http://localhost:5000
```

On first startup, the app automatically initializes the SQLite database and required tables.

## Common Workflows

### Novel List

On the home page, you can search by novel title or author and filter by category, tags, and reading status. Each card provides detail, read, download, edit, and delete actions. The detail page shows description, tags, reading progress, last reading time, chapter count, word count, file path, file size, file check status, AI character analysis, and character relationship graph. The circular checkbox in the top-left corner is used for batch operations. When opening a TXT novel, the reader restores the last chapter and scroll position. The reader supports themes, font size, line height, content width, paragraph spacing, collapsible table of contents, and immersive mode.

### Add a Novel

Click "Add Novel" and fill in the title, author, description, category, status, and tags. You can manually enter a file path or upload a local file into `library/`.

### Batch Import

Click "Batch Import" and select a local folder. The system scans supported novel files and can automatically create categories from folder names. During import, you can apply shared tags and a default reading status.

Supported file types:

```text
.txt .epub .pdf .mobi .azw3 .doc .docx .rtf
```

The built-in online reader is currently focused on TXT files.

### AI Features

After adding and activating a provider in "AI Configuration", you can:

- Test the AI chat connection.
- Generate descriptions and tags when editing a single novel.
- Extract settings such as worldbuilding, locations, organizations, rule systems, timelines, key items, and terminology on a novel detail page.
- Analyze characters, aliases, identities, traits, evidence snippets, and character relationships on a novel detail page.
- Batch-generate descriptions and tags for selected novels, confirm each result, and write it back to the database.

Sensitive configuration such as API keys is stored only in the local database. Please manage local backups and file permissions yourself.

### Crawler Management

In "Crawler Management", you can maintain site rules and crawl tasks.

Site rules can configure:

- Domain matching rules.
- Selectors for title, chapter title, and content.
- List page link selectors.
- Related post selectors for the same book.
- Chapter link selectors.
- Ad or toolbar selectors to remove from content.

The project includes these built-in site rules:

| Site Rule | Domain Match | Capability |
| --- | --- | --- |
| cool18 forum thread | `www.cool18.com` | Supports thread content crawling, batch task creation from list pages, and merging related posts for the same book. |
| AliceSW novel page | `www.alicesw.com` | Supports detail, catalog, and chapter page crawling; chapter content is extracted by decrypting the site API response. |
| Linovelib light novel | `*.linovelib.com` | Supports catalog and content crawling, and automatically merges paginated content from the same chapter. |
| Bilinovel light novel | `*.bilinovel.com` | Supports catalog and content crawling, and automatically merges paginated content from the same chapter. |
| Kakuyomu | `kakuyomu.jp` | Supports work catalog and chapter content crawling, preferring catalog extraction from `__NEXT_DATA__` / `__APOLLO_STATE__`. |
| Shosetsuka ni Naro | `*.syosetu.com` | Supports syosetu / ncode catalog and content crawling. |
| Novel18 | `novel18.syosetu.com` | Supports Novel18 catalog and content crawling, automatically attaching the `over18` cookie during crawling. |
| Pixiv novels | `www.pixiv.net` | Supports single works and series; catalogs and content are fetched through ajax APIs. |
| Hameln | `syosetu.org` | Supports catalog and content crawling, and appends afterword content to the body. |
| Alphapolis | `www.alphapolis.co.jp` | Supports parsing `#app-cover-data` for catalogs and content, with an Edge CDP session fallback when needed. |

Crawl tasks support:

- Automatic matching or manual site rule selection.
- Treating the current URL as a list page and batch-creating recent post crawl tasks.
- Automatic retry, failure reason logging, and resuming running tasks after service restart.
- Writing successful crawl results into the novel library and linking local files.

By default, the crawler refuses local and private network targets. If you really need to crawl a private-network target, set this before startup:

```powershell
$env:ALLOW_PRIVATE_CRAWLER_TARGETS='1'
python app.py
```

Or on macOS / Linux:

```bash
ALLOW_PRIVATE_CRAWLER_TARGETS=1 python app.py
```

Only enable this in a trusted network and when you clearly understand the target address.

## Data and Backup

Main local data:

- `novels.db`: SQLite database storing novel metadata, categories, tags, AI configuration, and crawler tasks.
- `library/`: novel files generated by upload, import, and crawling.
- `server-*.log`: local startup or debug logs.

Back up both `novels.db` and `library/` when needed. These files are ignored by Git by default.

## Tests and Checks

The repository contains lightweight Node and Python regression tests:

```bash
node tests/frontend-split.test.js
node tests/frontend-css-split.test.js
node tests/novel-detail-ui.test.js
node tests/reader-experience-ui.test.js
node tests/full-text-search-removed-ui.test.js
node tests/character-analysis-ui.test.js
node tests/novels-view-hero.test.js
node tests/novel-card-ui.test.js
python tests/app_structure.test.py
python tests/full_text_search_removed.test.py
python tests/character_analysis.test.py
python tests/novel_detail_file.test.py
```

Common pre-commit checks:

```bash
python -m py_compile app.py ai_client.py ai_routes.py crawler_routes.py reader_utils.py storage_utils.py
node --check static/js/app.js
node --check static/js/novels.js
node tests/frontend-split.test.js
node tests/frontend-css-split.test.js
node tests/novel-detail-ui.test.js
node tests/reader-experience-ui.test.js
node tests/full-text-search-removed-ui.test.js
node tests/character-analysis-ui.test.js
node tests/novels-view-hero.test.js
node tests/novel-card-ui.test.js
python tests/app_structure.test.py
python tests/full_text_search_removed.test.py
python tests/character_analysis.test.py
python tests/novel_detail_file.test.py
git diff --check
```

## Deployment Notes

This project is designed for local use and personal library management. Before deploying it in production, at least add:

- Login authentication and access control.
- HTTPS and reverse proxy configuration.
- Stricter file upload size, type, and path restrictions.
- A database backup strategy.
- API key encryption or a safer secret-management approach.
