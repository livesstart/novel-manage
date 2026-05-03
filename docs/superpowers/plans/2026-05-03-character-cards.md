# 角色卡升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将小说详情页的“角色关系”升级为以角色资料为中心的“角色卡”，同时保留现有 AI 分析接口和关系谱能力。

**Architecture:** 后端沿用现有 `characters` 路由和三张角色分析表，只给 `novel_characters` 增加 `profile_json` 存放角色卡扩展信息。前端保留现有详情页 Tab 和 `novel-character-*` DOM id，将文案与渲染结构升级为角色卡，关系谱作为辅助区域继续复用。

**Tech Stack:** Python 3, Flask, SQLite, native JavaScript, CSS, Node static checks, unittest.

---

## Spec

Design document: `docs/superpowers/specs/2026-05-03-character-cards-design.md`

## File Structure

- Modify: `ai_routes.py`
  - Add backward-compatible `profile_json` schema migration.
  - Normalize role-card profile fields from AI output.
  - Persist and serialize `profile`.
  - Update AI prompt and user-facing error text to role-card language.
- Modify: `tests/character_analysis.test.py`
  - Assert generated role-card profile fields are saved and returned.
  - Assert old character-analysis payloads still work as compact cards.
- Modify: `templates/index.html`
  - Change the detail Tab and panel copy from “角色关系” to “角色卡”.
  - Keep existing ids so route and event bindings remain stable.
- Modify: `static/js/novels.js`
  - Add profile compatibility helpers.
  - Render profile-rich role cards.
  - Update empty/loading/toast copy.
  - Keep relationship graph rendering.
- Modify: `static/css/novels.css`
  - Add card-grid and profile-field styles.
  - Preserve relationship graph styles.
- Modify: `tests/character-analysis-ui.test.js`
  - Check role-card copy, helpers, profile rendering, and existing graph behavior.

## Task 1: Backend Tests For Role-Card Profiles

**Files:**
- Modify: `tests/character_analysis.test.py`
- Test: `tests/character_analysis.test.py`

- [ ] **Step 1: Write the failing profile persistence assertions**

Replace the `FakeAIClient.chat` return payload with this richer role-card payload:

```python
    def chat(self, messages, stream=False):
        self.messages = messages
        return json.dumps({
            'characters': [
                {
                    'name': '林舟',
                    'aliases': ['小舟'],
                    'role_type': '主角',
                    'summary': '追查星河钥匙的核心行动者。',
                    'description': '负责追查星河钥匙的核心人物。',
                    'appearance': '气质冷静，行动时克制而专注。',
                    'personality': ['冷静', '执着'],
                    'motivation': '查清星河钥匙的来源。',
                    'skills': ['推理', '行动力'],
                    'first_seen': '第一章 星河钥匙',
                    'first_chapter_index': 0,
                    'evidence': '林舟第一次发现星河钥匙。',
                    'confidence': 0.92,
                },
                {
                    'name': '沈秋',
                    'aliases': [],
                    'role_type': '同伴',
                    'summary': '协助主角破解线索的同伴。',
                    'description': '协助林舟破解线索。',
                    'appearance': '观察细致，表达直接。',
                    'personality': ['敏锐'],
                    'motivation': '帮助林舟确认另一种推理方向。',
                    'skills': ['观察', '分析'],
                    'first_seen': '第二章 同行',
                    'first_chapter_index': 1,
                    'evidence': '沈秋提出另一种推理方向。',
                    'confidence': 0.88,
                },
            ],
            'relations': [
                {
                    'source': '林舟',
                    'target': '沈秋',
                    'relation_type': '同盟',
                    'description': '两人共同追查星河钥匙。',
                    'evidence': '林舟和沈秋决定一起行动。',
                    'confidence': 0.84,
                }
            ],
        }, ensure_ascii=False)
```

In `test_character_analysis_is_generated_and_persisted`, add these assertions after the existing character alias assertion:

```python
        self.assertEqual(data['characters'][0]['profile']['summary'], '追查星河钥匙的核心行动者。')
        self.assertEqual(data['characters'][0]['profile']['appearance'], '气质冷静，行动时克制而专注。')
        self.assertEqual(data['characters'][0]['profile']['personality'], ['冷静', '执着'])
        self.assertEqual(data['characters'][0]['profile']['motivation'], '查清星河钥匙的来源。')
        self.assertEqual(data['characters'][0]['profile']['skills'], ['推理', '行动力'])
        self.assertEqual(data['characters'][0]['profile']['first_seen'], '第一章 星河钥匙')
```

Add these assertions after `read_payload` has been checked for `analysis_status`:

```python
        read_character = read_payload['data']['characters'][0]
        self.assertEqual(read_character['profile']['summary'], '追查星河钥匙的核心行动者。')
        self.assertEqual(read_character['profile']['skills'], ['推理', '行动力'])
```

- [ ] **Step 2: Add old-payload compatibility coverage**

Add this test method to `CharacterAnalysisTest`:

```python
    def test_character_analysis_accepts_legacy_character_payload(self):
        class LegacyAIClient:
            def chat(self, messages, stream=False):
                return json.dumps({
                    'characters': [
                        {
                            'name': '旧角色',
                            'aliases': ['旧名'],
                            'role_type': '配角',
                            'description': '旧格式中的角色说明。',
                            'traits': ['谨慎'],
                            'first_chapter_index': 0,
                            'evidence': '旧角色在第一章出现。',
                            'confidence': 0.7,
                        }
                    ],
                    'relations': [],
                }, ensure_ascii=False)

        ai_routes.get_ai_client = lambda: LegacyAIClient()

        response = self.client.post(f'/api/ai/novels/{self.novel_id}/characters/analyze')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        character = payload['data']['characters'][0]
        self.assertEqual(character['name'], '旧角色')
        self.assertEqual(character['description'], '旧格式中的角色说明。')
        self.assertEqual(character['traits'], ['谨慎'])
        self.assertEqual(character['profile']['summary'], '旧格式中的角色说明。')
        self.assertEqual(character['profile']['personality'], ['谨慎'])
        self.assertEqual(character['profile']['first_seen'], '第 1 章')
```

- [ ] **Step 3: Run the backend test and verify it fails for missing profile support**

Run:

```powershell
python tests/character_analysis.test.py
```

Expected: FAIL with a missing `profile` key or missing `profile_json` column behavior.

- [ ] **Step 4: Commit the failing tests**

Run:

```powershell
git add tests/character_analysis.test.py
git commit -m "test: cover character card profiles"
```

Expected: commit succeeds and only `tests/character_analysis.test.py` is included.

## Task 2: Backend Role-Card Persistence

**Files:**
- Modify: `ai_routes.py:18-75`
- Modify: `ai_routes.py:185-301`
- Modify: `ai_routes.py:304-333`
- Modify: `ai_routes.py:339-473`
- Modify: `ai_routes.py:923-976`
- Test: `tests/character_analysis.test.py`

- [ ] **Step 1: Add the `profile_json` migration**

In `ensure_character_analysis_schema`, after the `CREATE TABLE IF NOT EXISTS novel_characters` statement and before creating indexes, add:

```python
    cursor.execute('PRAGMA table_info(novel_characters)')
    character_columns = {row[1] for row in cursor.fetchall()}
    if 'profile_json' not in character_columns:
        cursor.execute("ALTER TABLE novel_characters ADD COLUMN profile_json TEXT DEFAULT '{}'")
```

- [ ] **Step 2: Add JSON object parsing helper**

After `parse_json_list`, add:

```python
    def parse_json_dict(value):
        if not value:
            return {}
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}
```

- [ ] **Step 3: Add profile normalization helper**

After `normalize_string_list`, add:

```python
    def normalize_character_profile(item, *, description='', traits=None, first_chapter_index=None, evidence=''):
        traits = traits or []
        first_seen = normalize_short_text(item.get('first_seen'), max_length=180)
        if not first_seen and first_chapter_index is not None:
            first_seen = f'第 {first_chapter_index + 1} 章'

        return {
            'summary': normalize_short_text(item.get('summary') or description, max_length=120),
            'appearance': normalize_short_text(item.get('appearance'), max_length=180),
            'personality': normalize_string_list(item.get('personality') or traits, max_items=8, max_length=18),
            'motivation': normalize_short_text(item.get('motivation'), max_length=180),
            'skills': normalize_string_list(item.get('skills'), max_items=8, max_length=18),
            'first_seen': first_seen,
            'card_evidence': normalize_short_text(item.get('card_evidence') or evidence, max_length=180),
        }
```

- [ ] **Step 4: Include `profile` in normalized characters**

Inside `normalize_character_analysis_payload`, replace the current `character = { ... }` block with:

```python
            description = normalize_short_text(item.get('description'), max_length=260)
            traits = normalize_string_list(item.get('traits') or item.get('personality'), max_items=8, max_length=18)
            evidence = normalize_short_text(item.get('evidence'), max_length=220)
            profile = normalize_character_profile(
                item,
                description=description,
                traits=traits,
                first_chapter_index=first_chapter_index if first_chapter_index is None or first_chapter_index >= 0 else None,
                evidence=evidence,
            )

            character = {
                'name': name,
                'aliases': normalize_string_list(item.get('aliases'), max_items=6, max_length=24),
                'role_type': normalize_short_text(item.get('role_type'), max_length=32),
                'description': description,
                'traits': traits,
                'first_chapter_index': first_chapter_index if first_chapter_index is None or first_chapter_index >= 0 else None,
                'evidence': evidence,
                'confidence': clamp_confidence(item.get('confidence')),
                'profile': profile,
            }
```

- [ ] **Step 5: Update the AI prompt for role cards**

Replace the user prompt body in `build_character_analysis_messages` with:

```python
        user_prompt = '\n\n'.join(context_blocks) + textwrap.dedent("""

    请为这本小说中已经明确出现或被文本直接支持的角色生成角色卡，并整理角色之间的关系。

    要求：
    1. 只输出一个 JSON 对象，不要输出 Markdown。
    2. JSON 格式必须为：
       {"characters":[{"name":"角色名","aliases":["别名"],"role_type":"主角/反派/同伴/配角/未知","summary":"一句话角色定位","description":"角色说明","appearance":"外貌或气质","personality":["性格标签"],"motivation":"明确动机","skills":["能力或特长"],"first_seen":"首次出现位置","first_chapter_index":0,"evidence":"证据片段","confidence":0.8}],"relations":[{"source":"角色A","target":"角色B","relation_type":"关系类型","description":"关系说明","evidence":"证据片段","confidence":0.8}]}
    3. 只基于已提供文本判断，不要编造未出现的人物、关系和结局。
    4. characters 最多 12 个，relations 最多 20 条。
    5. evidence 必须是能支持判断的简短文本依据。
    6. 信息不足的扩展字段可以留空字符串或空数组，不要补写未被文本支持的细节。
    7. confidence 用 0 到 1 的数字表示可信度。
    """)
```

Replace the system prompt string in the returned messages with:

```python
                'content': '你是一个严谨的小说角色卡整理助手，只根据文本证据整理角色资料和关系。'
```

- [ ] **Step 6: Serialize `profile` from the database**

Inside `serialize_character_analysis`, after parsing `aliases` and `traits`, add:

```python
            item['profile'] = parse_json_dict(item.pop('profile_json', '{}'))
            if not item['profile']:
                first_seen = f"第 {item['first_chapter_index'] + 1} 章" if item.get('first_chapter_index') is not None else ''
                item['profile'] = {
                    'summary': item.get('description') or '',
                    'appearance': '',
                    'personality': item.get('traits') or [],
                    'motivation': '',
                    'skills': [],
                    'first_seen': first_seen,
                    'card_evidence': item.get('evidence') or '',
                }
```

- [ ] **Step 7: Persist `profile_json`**

In `replace_character_analysis`, replace the character insert SQL and values with:

```python
                cursor.execute('''
                    INSERT INTO novel_characters (
                        novel_id, name, aliases_json, role_type, description,
                        traits_json, first_chapter_index, evidence, confidence,
                        profile_json, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    novel_id,
                    character['name'],
                    json.dumps(character['aliases'], ensure_ascii=False),
                    character['role_type'],
                    character['description'],
                    json.dumps(character['traits'], ensure_ascii=False),
                    character['first_chapter_index'],
                    character['evidence'],
                    character['confidence'],
                    json.dumps(character.get('profile') or {}, ensure_ascii=False),
                    index,
                ))
```

- [ ] **Step 8: Update route copy for no-character failures**

In `analyze_novel_characters`, replace:

```python
                return jsonify({'success': False, 'message': 'AI 未识别到可用角色，请换更多正文内容后重试'}), 500
```

with:

```python
                return jsonify({'success': False, 'message': 'AI 未识别到可用角色卡，请换更多正文内容后重试'}), 500
```

- [ ] **Step 9: Run backend tests and compile checks**

Run:

```powershell
python tests/character_analysis.test.py
python -m py_compile app.py ai_client.py ai_routes.py crawler_routes.py reader_utils.py storage_utils.py
```

Expected: both commands pass.

- [ ] **Step 10: Commit backend implementation**

Run:

```powershell
git add ai_routes.py tests/character_analysis.test.py
git commit -m "feat: persist character card profiles"
```

Expected: commit succeeds with backend code and backend tests.

## Task 3: Frontend Static Tests For Role-Card UI

**Files:**
- Modify: `tests/character-analysis-ui.test.js`
- Test: `tests/character-analysis-ui.test.js`

- [ ] **Step 1: Update UI copy expectations**

After the template id loop, add:

```javascript
assert.match(template, />\s*角色卡\s*</, 'detail tab should be labeled as character cards');
assert.match(template, /<h4>角色卡<\/h4>/, 'character panel heading should use character-card copy');
assert.match(template, /AI 生成角色卡/, 'analysis button should generate character cards');
```

- [ ] **Step 2: Update JavaScript expectations**

Replace:

```javascript
assert.match(novelsJs, /function renderNovelCharacterAnalysis\(analysis\)/, 'frontend should render character analysis');
```

with:

```javascript
assert.match(novelsJs, /function getCharacterProfile\(character\)/, 'frontend should normalize role-card profile fields');
assert.match(novelsJs, /function renderCharacterProfileMeta/, 'frontend should render role-card profile metadata');
assert.match(novelsJs, /function renderNovelCharacterAnalysis\(analysis\)/, 'frontend should render character-card analysis');
assert.match(novelsJs, /AI 正在生成角色卡/, 'frontend should show role-card generation loading copy');
assert.match(novelsJs, /已生成 \$\{res\.data\.character_count\} 张角色卡/, 'success toast should use role-card copy');
```

- [ ] **Step 3: Update CSS expectations**

After the existing `.novel-character-card` assertion, add:

```javascript
assert.match(novelsCss, /\.novel-character-card-summary/, 'character cards should style summary text');
assert.match(novelsCss, /\.novel-character-profile-grid/, 'character cards should style profile metadata');
assert.match(novelsCss, /\.novel-character-profile-item/, 'character cards should style each profile item');
```

- [ ] **Step 4: Run the UI static test and verify it fails**

Run:

```powershell
node tests/character-analysis-ui.test.js
```

Expected: FAIL because role-card helpers, copy, and CSS classes are not implemented yet.

- [ ] **Step 5: Commit failing frontend tests**

Run:

```powershell
git add tests/character-analysis-ui.test.js
git commit -m "test: cover character card UI"
```

Expected: commit succeeds with only the UI static test update.

## Task 4: Frontend Role-Card UI

**Files:**
- Modify: `templates/index.html:464-530`
- Modify: `static/js/novels.js:613-830`
- Modify: `static/css/novels.css:420-735`
- Test: `tests/character-analysis-ui.test.js`

- [ ] **Step 1: Update template copy**

In `templates/index.html`, change the characters Tab icon and text to:

```html
                    <button class="novel-detail-tab" id="novel-detail-tab-characters" type="button" role="tab" aria-selected="false" data-detail-tab="characters">
                        <i class="fas fa-address-card"></i>
                        角色卡
                    </button>
```

In the characters panel header, replace the heading and button with:

```html
                                    <h4>角色卡</h4>
                                    <p id="novel-character-status">尚未生成角色卡</p>
```

```html
                                <button class="btn btn-sm btn-secondary" id="btn-detail-analyze-characters">
                                    <i class="fas fa-address-card"></i>
                                    AI 生成角色卡
                                </button>
```

Change the left column title from `角色` to:

```html
                                    <div class="novel-character-column-title">角色卡</div>
```

Change the initial empty state inside `#novel-character-list` to:

```html
                                        <div class="novel-character-empty">暂无角色卡数据</div>
```

- [ ] **Step 2: Update reset copy in JavaScript**

Replace `resetNovelCharacterAnalysis` with:

```javascript
function resetNovelCharacterAnalysis() {
    state.detailCharacterAnalysis = null;
    document.getElementById('novel-character-status').textContent = '尚未生成角色卡';
    document.getElementById('novel-character-status').className = '';
    document.getElementById('novel-character-list').innerHTML = '<div class="novel-character-empty">暂无角色卡数据</div>';
    document.getElementById('novel-character-graph').innerHTML = '<div class="novel-character-empty">生成后会展示关系谱</div>';
    document.getElementById('novel-character-relations').innerHTML = '';
}
```

- [ ] **Step 3: Add role-card helper functions**

After `renderCharacterBadges`, add:

```javascript
function getCharacterProfile(character = {}) {
    const profile = character.profile && typeof character.profile === 'object' ? character.profile : {};
    const firstSeen = profile.first_seen || (
        Number.isInteger(character.first_chapter_index) ? `第 ${character.first_chapter_index + 1} 章` : ''
    );

    return {
        summary: profile.summary || character.description || '暂无角色定位',
        appearance: profile.appearance || '',
        personality: Array.isArray(profile.personality) && profile.personality.length
            ? profile.personality
            : (Array.isArray(character.traits) ? character.traits : []),
        motivation: profile.motivation || '',
        skills: Array.isArray(profile.skills) ? profile.skills : [],
        firstSeen,
        cardEvidence: profile.card_evidence || character.evidence || '',
    };
}

function renderCharacterProfileMeta(label, value) {
    const hasArrayValue = Array.isArray(value) && value.length > 0;
    const hasTextValue = !Array.isArray(value) && value;
    if (!hasArrayValue && !hasTextValue) return '';

    const content = Array.isArray(value)
        ? value.map(item => `<span>${escapeHtml(item)}</span>`).join('')
        : escapeHtml(value);

    return `
        <div class="novel-character-profile-item">
            <span>${escapeHtml(label)}</span>
            <strong${Array.isArray(value) ? ' class="tag-list"' : ''}>${content}</strong>
        </div>
    `;
}
```

- [ ] **Step 4: Replace role-card rendering in `renderNovelCharacterAnalysis`**

Inside `renderNovelCharacterAnalysis`, replace the status text branch with:

```javascript
    if (status === 'failed') {
        statusEl.textContent = analysis.error_message || '上次生成失败';
        statusEl.className = 'failed';
    } else if (characters.length > 0 || relations.length > 0) {
        statusEl.textContent = `已生成 ${characters.length} 张角色卡、${relations.length} 条关系`;
        statusEl.className = 'completed';
    } else {
        statusEl.textContent = '尚未生成角色卡';
        statusEl.className = '';
    }
```

Replace the `characters.length === 0` branch and character map with:

```javascript
    if (characters.length === 0) {
        list.innerHTML = '<div class="novel-character-empty">暂无角色卡数据</div>';
    } else {
        list.innerHTML = characters.map(character => {
            const profile = getCharacterProfile(character);
            return `
                <article class="novel-character-card">
                    <div class="novel-character-card-head">
                        <strong>${escapeHtml(character.name)}</strong>
                        <span>${escapeHtml(character.role_type || '角色')}</span>
                    </div>
                    ${character.aliases?.length ? `<div class="novel-character-alias">别名：${escapeHtml(character.aliases.join('、'))}</div>` : ''}
                    <p class="novel-character-card-summary">${escapeHtml(profile.summary)}</p>
                    ${renderCharacterBadges(profile.personality)}
                    <div class="novel-character-profile-grid">
                        ${renderCharacterProfileMeta('气质', profile.appearance)}
                        ${renderCharacterProfileMeta('动机', profile.motivation)}
                        ${renderCharacterProfileMeta('能力', profile.skills)}
                        ${renderCharacterProfileMeta('首次出现', profile.firstSeen)}
                    </div>
                    <div class="novel-character-evidence">${escapeHtml(profile.cardEvidence || '暂无证据片段')}</div>
                    <div class="novel-character-confidence">可信度 ${formatConfidence(character.confidence)}</div>
                </article>
            `;
        }).join('');
    }
```

- [ ] **Step 5: Update loading and toast copy**

In `analyzeNovelCharactersWithAI`, replace:

```javascript
    button.innerHTML = '<span class="loading"></span> 分析中';
    document.getElementById('novel-character-status').textContent = 'AI 正在分析角色关系...';
```

with:

```javascript
    button.innerHTML = '<span class="loading"></span> 生成中';
    document.getElementById('novel-character-status').textContent = 'AI 正在生成角色卡...';
```

Replace:

```javascript
            showToast(res.message || '角色分析失败', 'error');
```

with:

```javascript
            showToast(res.message || '角色卡生成失败', 'error');
```

Replace:

```javascript
        showToast(`已识别 ${res.data.character_count} 个角色、${res.data.relation_count} 条关系`, 'success');
```

with:

```javascript
        showToast(`已生成 ${res.data.character_count} 张角色卡、${res.data.relation_count} 条关系`, 'success');
```

Replace the catch block copy:

```javascript
        console.error('AI 分析角色关系失败:', err);
        showToast('AI 分析角色关系失败: ' + err.message, 'error');
```

with:

```javascript
        console.error('AI 生成角色卡失败:', err);
        showToast('AI 生成角色卡失败: ' + err.message, 'error');
```

- [ ] **Step 6: Add CSS for role-card details**

In `static/css/novels.css`, after the existing `.novel-character-card p, .novel-relation-card p` block, add:

```css
.novel-character-card-summary {
    color: var(--text-primary);
    font-weight: 600;
}

.novel-character-profile-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 8px;
    margin: 10px 0;
}

.novel-character-profile-item {
    display: grid;
    gap: 4px;
    padding: 8px 10px;
    border-radius: var(--radius);
    background: #f8fafc;
}

.novel-character-profile-item > span {
    color: var(--text-secondary);
    font-size: 12px;
    font-weight: 700;
}

.novel-character-profile-item > strong {
    color: var(--text-primary);
    font-size: 13px;
    font-weight: 600;
    line-height: 1.5;
}

.novel-character-profile-item .tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.novel-character-profile-item .tag-list span {
    padding: 2px 7px;
    border-radius: 999px;
    background: #fef3c7;
    color: #92400e;
    font-size: 12px;
}
```

- [ ] **Step 7: Run frontend checks**

Run:

```powershell
node tests/character-analysis-ui.test.js
node --check static/js/novels.js
```

Expected: both commands pass.

- [ ] **Step 8: Commit frontend implementation**

Run:

```powershell
git add templates/index.html static/js/novels.js static/css/novels.css tests/character-analysis-ui.test.js
git commit -m "feat: upgrade character tab to cards"
```

Expected: commit succeeds with frontend implementation and UI static test.

## Task 5: Regression Verification

**Files:**
- Verify: `ai_routes.py`
- Verify: `static/js/novels.js`
- Verify: `templates/index.html`
- Verify: `static/css/novels.css`
- Verify: `tests/character_analysis.test.py`
- Verify: `tests/character-analysis-ui.test.js`

- [ ] **Step 1: Run the focused role-card regression suite**

Run:

```powershell
python tests/character_analysis.test.py
node tests/character-analysis-ui.test.js
```

Expected: both commands pass.

- [ ] **Step 2: Run structure and syntax checks**

Run:

```powershell
python tests/app_structure.test.py
python -m py_compile app.py ai_client.py ai_routes.py crawler_routes.py reader_utils.py storage_utils.py
node --check static/js/app.js
node --check static/js/novels.js
```

Expected: all commands pass.

- [ ] **Step 3: Run adjacent detail-view UI checks**

Run:

```powershell
node tests/novel-detail-ui.test.js
```

Expected: command passes.

- [ ] **Step 4: Inspect final git diff**

Run:

```powershell
git status --short
git diff --stat HEAD
```

Expected: status shows only intentional working changes or a clean tree; diff stat includes role-card files only if commits have not been made yet.

- [ ] **Step 5: Final implementation commit if any verified changes remain uncommitted**

If Step 4 shows uncommitted role-card changes, run:

```powershell
git add ai_routes.py tests/character_analysis.test.py templates/index.html static/js/novels.js static/css/novels.css tests/character-analysis-ui.test.js
git commit -m "feat: finish character card upgrade"
```

Expected: commit succeeds, or no commit is needed because prior task commits already captured the verified changes.

## Self-Review

- Spec coverage: The plan covers schema migration, AI prompt, payload normalization, persistence, serialization, UI copy, card rendering, relationship graph preservation, old-data compatibility, and verification.
- Placeholder scan: The plan contains concrete fields, commands, copy, helper names, and code snippets for each implementation step.
- Type consistency: The backend exposes `character.profile`; the frontend reads `character.profile`; the stored column is `profile_json`; profile keys are `summary`, `appearance`, `personality`, `motivation`, `skills`, `first_seen`, and `card_evidence`.
