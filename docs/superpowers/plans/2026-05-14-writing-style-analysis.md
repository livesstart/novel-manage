# Writing Style Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add AI-powered novel writing style extraction with persisted analysis, imitation guide, and copyable style prompt.

**Architecture:** Reuse the existing setting/character analysis pattern in `ai_routes.py`: schema setup, normalization, serialization, replace-on-generate persistence, and GET/POST routes. Add a dedicated writing-style tab in the novel detail modal with frontend state, renderer, API calls, and focused static tests.

**Tech Stack:** Flask, SQLite, vanilla JavaScript, CSS, Node static tests, Python unittest.

---

## File Structure

- Modify `ai_routes.py`
  - Extend `ensure_character_analysis_schema`.
  - Add writing-style normalization, AI prompt builder, serializers, persistence helpers, failure marker, GET route, and analyze route.
- Modify `templates/index.html`
  - Add the writing-style tab and panel markup.
- Modify `static/js/core.js`
  - Add `detailWritingStyleAnalysis` to shared state.
- Modify `static/js/novels.js`
  - Add reset/render/load/analyze/copy functions and bind them in detail rendering.
- Modify `static/css/novels.css`
  - Add `.novel-writing-style-*` styles and mobile behavior.
- Create `tests/writing_style_analysis.test.py`
  - Backend behavior and schema tests.
- Create `tests/writing-style-ui.test.js`
  - Static UI contract tests.

## Task 1: Backend Failing Tests

**Files:**
- Create: `tests/writing_style_analysis.test.py`

- [ ] **Step 1: Write the failing backend test**

Create `tests/writing_style_analysis.test.py` with a fake AI client returning:

```python
{
    'summary': '冷静克制的悬疑叙事，靠细节递进推动真相。',
    'narrative_perspective': '第三人称有限视角，贴近主角观察。',
    'language_texture': '句式简洁，偏理性，偶尔用具象物象压住情绪。',
    'pacing': '线索逐层推进，章节末尾保留轻微悬念。',
    'description_focus': '重视物件、光线和动作细节。',
    'dialogue_style': '对话短促，常用试探和反问推进信息。',
    'emotional_tone': '冷峻、克制、带一点不安。',
    'signature_techniques': [
        {
            'name': '物件锚点',
            'description': '用关键物件承载线索和情绪压力。',
            'evidence': '星河钥匙在满月下发光。',
            'confidence': 0.91,
        }
    ],
    'examples': [
        {
            'label': '线索片段',
            'analysis': '用物件变化暗示谜团正在扩大。',
            'evidence': '钥匙边缘浮出细小的银色刻痕。',
            'confidence': 0.86,
        }
    ],
    'imitation_guide': '续写时保持短句和克制心理描写，先写可观察细节，再给出人物判断。',
    'style_prompt': '请用冷静克制的悬疑叙事续写：第三人称有限视角，短句，重视物件和动作细节。',
    'confidence': 0.89,
}
```

Assertions:
- `POST /api/ai/novels/<id>/writing-style/analyze` returns 200.
- Response contains `analysis_status == "completed"`.
- Response contains `summary`, `style_prompt`, one technique, and one example.
- Fake client prompt includes the source excerpt marker.
- `GET /api/novels/<id>/writing-style` reads back the same persisted fields.
- Missing novel returns 404.
- Running `ensure_character_analysis_schema` twice creates `novel_writing_styles` and `novel_writing_style_analysis_runs`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python tests/writing_style_analysis.test.py
```

Expected: FAIL because `/writing-style` routes and tables do not exist.

## Task 2: Backend Implementation

**Files:**
- Modify: `ai_routes.py`
- Test: `tests/writing_style_analysis.test.py`

- [ ] **Step 1: Extend schema**

In `ensure_character_analysis_schema(cursor)`, after setting tables, add:

```python
cursor.execute('''
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
    )
''')
cursor.execute('''
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
    )
''')
```

- [ ] **Step 2: Add normalization helpers**

Inside `register_ai_routes`, near `normalize_setting_analysis_payload`, add:

```python
def normalize_writing_style_items(items, *, max_items=8, name_key='name'):
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        normalized.append({
            name_key: normalize_short_text(item.get(name_key) or item.get('title') or item.get('label'), max_length=48),
            'description': normalize_short_text(item.get('description') or item.get('analysis'), max_length=260),
            'evidence': normalize_short_text(item.get('evidence'), max_length=220),
            'confidence': clamp_confidence(item.get('confidence')),
        })
        if len(normalized) >= max_items:
            break
    return [item for item in normalized if item.get(name_key) or item.get('description') or item.get('evidence')]
```

Add `normalize_writing_style_payload(payload)` that returns a dict with all fields listed in the spec and clamps array sizes.

- [ ] **Step 3: Add prompt builder**

Add `build_writing_style_analysis_messages(novel, content_excerpt)` mirroring `build_setting_analysis_messages`, asking for only JSON and the exact keys from the spec.

- [ ] **Step 4: Add serialization/persistence helpers**

Add:
- `serialize_writing_style_analysis(novel_id)`
- `replace_writing_style_analysis(novel_id, style, *, model='', source_excerpt_chars=0)`
- `mark_writing_style_analysis_failed(novel_id, error_message, *, model='', source_excerpt_chars=0)`

Use the same transaction shape as `replace_setting_analysis`.

- [ ] **Step 5: Add routes**

Add:

```python
@app.route('/api/novels/<int:novel_id>/writing-style', methods=['GET'])
def get_novel_writing_style_analysis(novel_id):
    novel = get_novel_detail_record(novel_id)
    if not novel:
        return jsonify({'success': False, 'message': '小说不存在'}), 404
    return jsonify({'success': True, 'data': serialize_writing_style_analysis(novel_id)})
```

Add:

```python
@app.route('/api/ai/novels/<int:novel_id>/writing-style/analyze', methods=['POST'])
def analyze_novel_writing_style(novel_id):
    ...
```

Use the same validation/error behavior as `analyze_novel_settings`.

- [ ] **Step 6: Run backend test**

Run:

```powershell
python tests/writing_style_analysis.test.py
```

Expected: PASS.

## Task 3: UI Failing Tests

**Files:**
- Create: `tests/writing-style-ui.test.js`

- [ ] **Step 1: Write the failing UI test**

Create a Node static test that reads `templates/index.html`, `static/js/core.js`, `static/js/novels.js`, and `static/css/novels.css`.

Assert:

```javascript
[
  'novel-detail-tab-writing-style',
  'novel-detail-panel-writing-style',
  'novel-writing-style-panel',
  'btn-detail-analyze-writing-style',
  'novel-writing-style-status',
  'novel-writing-style-summary',
  'novel-writing-style-dimensions',
  'novel-writing-style-techniques',
  'novel-writing-style-examples',
  'novel-writing-style-guide',
  'novel-writing-style-prompt',
].forEach(id => assert.match(template, new RegExp(`id="${id}"`)));
```

Also assert:
- Template contains `写作风格` and `AI 提取风格`.
- `core.js` contains `detailWritingStyleAnalysis: null`.
- `novels.js` contains `resetNovelWritingStyleAnalysis`, `renderNovelWritingStyleAnalysis`, `loadNovelWritingStyleAnalysis`, `analyzeNovelWritingStyleWithAI`, and `copyNovelWritingStylePrompt`.
- `novels.js` calls `/api/novels/${novelId}/writing-style`.
- `novels.js` calls `/api/ai/novels/${novelId}/writing-style/analyze`.
- CSS contains `.novel-writing-style-panel`, `.novel-writing-style-grid`, `.novel-writing-style-card`, and `.novel-writing-style-prompt`.

- [ ] **Step 2: Run UI test to verify it fails**

Run:

```powershell
node tests/writing-style-ui.test.js
```

Expected: FAIL because the tab, functions, and CSS do not exist.

## Task 4: Frontend Implementation

**Files:**
- Modify: `templates/index.html`
- Modify: `static/js/core.js`
- Modify: `static/js/novels.js`
- Modify: `static/css/novels.css`
- Test: `tests/writing-style-ui.test.js`

- [ ] **Step 1: Add shared state**

In `static/js/core.js`, add:

```javascript
detailWritingStyleAnalysis: null,
```

next to the existing detail analysis state.

- [ ] **Step 2: Add template tab and panel**

In `templates/index.html`, add a writing-style tab between settings and characters:

```html
<button class="novel-detail-tab" id="novel-detail-tab-writing-style" type="button" role="tab" aria-selected="false" data-detail-tab="writing-style">
    <i class="fas fa-pen-nib"></i>
    写作风格
</button>
```

Add a panel with IDs required by the test and the copy button `btn-copy-writing-style-prompt`.

- [ ] **Step 3: Add frontend functions**

In `static/js/novels.js`, after setting analysis functions, add:

- `resetNovelWritingStyleAnalysis()`
- `renderNovelWritingStyleAnalysis(analysis)`
- `renderWritingStyleCard(label, value)`
- `renderWritingStyleItems(items, emptyText)`
- `loadNovelWritingStyleAnalysis(novelId)`
- `analyzeNovelWritingStyleWithAI(novelId)`
- `copyNovelWritingStylePrompt()`

The renderer should safely handle empty values and always use `escapeHtml`.

- [ ] **Step 4: Bind detail behavior**

In `renderNovelDetail(novel)`:

- Call `resetNovelWritingStyleAnalysis()`.
- Bind `btn-detail-analyze-writing-style` to `analyzeNovelWritingStyleWithAI(novel.id)`.
- Bind `btn-copy-writing-style-prompt` to `copyNovelWritingStylePrompt`.

In the detail load flow, call `loadNovelWritingStyleAnalysis(novelId)` alongside settings/characters loading.

- [ ] **Step 5: Add CSS**

Add `.novel-writing-style-*` rules near setting/character detail styles. Use grid layout for dimensions, techniques, and examples; make prompt text wrap.

- [ ] **Step 6: Run UI test**

Run:

```powershell
node tests/writing-style-ui.test.js
```

Expected: PASS.

## Task 5: Verification

**Files:**
- All changed files

- [ ] **Step 1: Run syntax checks**

Run:

```powershell
python -m py_compile app.py ai_client.py ai_routes.py crawler_routes.py reader_utils.py storage_utils.py
node --check static/js/app.js
node --check static/js/novels.js
```

Expected: all commands pass.

- [ ] **Step 2: Run focused regression tests**

Run:

```powershell
python tests/writing_style_analysis.test.py
node tests/writing-style-ui.test.js
python tests/novel_setting_analysis.test.py
python tests/character_analysis.test.py
node tests/novel-setting-ui.test.js
node tests/character-analysis-ui.test.js
```

Expected: all tests pass.

- [ ] **Step 3: Run diff check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.
