# Frontend JS Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the largest frontend JavaScript files into focused, ordered browser scripts without changing runtime behavior.

**Architecture:** Keep the existing no-build global-script architecture. Move cohesive functions from `novels.js` and `app.js` into new scripts loaded before their existing entry files so public globals remain available.

**Tech Stack:** Browser JavaScript, Flask template script tags, Node-based structural/UI tests.

---

### Task 1: Add Frontend Structure Tests

**Files:**
- Modify: `tests/frontend-split.test.js`

- [ ] Update expected scripts to include `novel-render.js`, `novel-detail.js`, `novel-download.js`, and `app-bindings.js`.
- [ ] Add line-count checks for `static/js/novels.js` and `static/js/app.js`.
- [ ] Run `node tests/frontend-split.test.js` and verify it fails because the new files and script tags do not exist yet.

### Task 2: Split Novel Rendering

**Files:**
- Create: `static/js/novel-render.js`
- Modify: `static/js/novels.js`
- Modify: `templates/index.html`

- [ ] Move list/category/tag rendering functions from `novels.js` into `novel-render.js`.
- [ ] Load `novel-render.js` after `core.js` and before `novels.js`.
- [ ] Run `node tests/frontend-split.test.js` and `node tests/novel-card-ui.test.js`.

### Task 3: Split Novel Detail And Download Logic

**Files:**
- Create: `static/js/novel-detail.js`
- Create: `static/js/novel-download.js`
- Modify: `static/js/novels.js`
- Modify: `templates/index.html`

- [ ] Move detail drawer, analysis rendering, and analysis actions to `novel-detail.js`.
- [ ] Move open/download filename helpers to `novel-download.js`.
- [ ] Run `node tests/novel-detail-ui.test.js`, `node tests/novel-download-filename-ui.test.js`, `node tests/novel-setting-ui.test.js`, `node tests/character-analysis-ui.test.js`, and `node tests/writing-style-ui.test.js`.

### Task 4: Split App Event Binding

**Files:**
- Create: `static/js/app-bindings.js`
- Modify: `static/js/app.js`
- Modify: `templates/index.html`

- [ ] Move event binding body into named binding functions in `app-bindings.js`.
- [ ] Keep `app.js` responsible for `init()` and startup sequencing.
- [ ] Run `node tests/frontend-split.test.js` and all Node UI tests.

### Task 5: Final Verification

**Files:**
- No new files expected.

- [ ] Run `Get-ChildItem static/js -Filter *.js | ForEach-Object { node --check $_.FullName }`.
- [ ] Run all `tests/*.js`.
- [ ] Run all `tests/*.py`.
- [ ] Run `git diff --check`.
