# Maintainability Route Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split backend route responsibilities out of `app.py` while keeping all public API behavior unchanged.

**Architecture:** Keep `app.py` as the application composition root. Move cohesive API groups into route modules with explicit `register_*_routes()` functions that receive `app` and dependencies from `app.py`.

**Tech Stack:** Python, Flask, SQLite, existing `unittest` tests.

---

### Task 1: Add Structure Guard Tests

**Files:**
- Modify: `tests/app_structure.test.py`

- [ ] Add tests requiring `novel_routes.py`, `reader_routes.py`, `taxonomy_routes.py`, `import_routes.py`, and `batch_routes.py`.
- [ ] Add a test that rejects direct `/api` route decorators in `app.py`.
- [ ] Tighten the `app.py` line-count target to 450 lines.
- [ ] Run `python tests/app_structure.test.py` and verify the new tests fail before implementation.

### Task 2: Move Reader Routes

**Files:**
- Create: `reader_routes.py`
- Modify: `app.py`

- [ ] Move reading progress serialization and reader endpoints into `reader_routes.py`.
- [ ] Register with `register_reader_routes(app, get_db=get_db, resolve_novel_file_path=..., is_text_readable_file=...)`.
- [ ] Run `python tests/reader_progress.test.py` and `python tests/app_structure.test.py`.

### Task 3: Move Novel And Taxonomy Routes

**Files:**
- Create: `novel_routes.py`
- Create: `taxonomy_routes.py`
- Modify: `app.py`

- [ ] Move novel CRUD, upload, download, file check, and fix-path routes into `novel_routes.py`.
- [ ] Move categories, tags, and stats into `taxonomy_routes.py`.
- [ ] Run `python tests/novel_detail_file.test.py`, `python tests/full_text_search_removed.test.py`, and `python tests/app_structure.test.py`.

### Task 4: Move Import And Batch Routes

**Files:**
- Create: `import_routes.py`
- Create: `batch_routes.py`
- Modify: `app.py`

- [ ] Move folder scan and batch import into `import_routes.py`.
- [ ] Move batch operations into `batch_routes.py`.
- [ ] Run `python tests/app_structure.test.py`.

### Task 5: Final Verification

**Files:**
- No new files expected.

- [ ] Run Python compilation for all backend modules.
- [ ] Run the affected Python test suite.
- [ ] Run `node --check` for existing JavaScript files.
- [ ] Run `git diff --check`.
