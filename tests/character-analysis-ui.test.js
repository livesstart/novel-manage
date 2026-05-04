const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const novelsJs = fs.readFileSync(path.join(root, 'static/js/novels.js'), 'utf8');
const coreJs = fs.readFileSync(path.join(root, 'static/js/core.js'), 'utf8');
const novelsCss = fs.readFileSync(path.join(root, 'static/css/novels.css'), 'utf8');

const requiredTemplateIds = [
    'novel-detail-tabs',
    'novel-detail-tab-overview',
    'novel-detail-tab-file',
    'novel-detail-tab-characters',
    'novel-detail-panel-overview',
    'novel-detail-panel-file',
    'novel-detail-panel-characters',
    'novel-character-panel',
    'btn-detail-analyze-characters',
    'novel-character-status',
    'novel-character-list',
    'novel-character-graph',
    'novel-character-relations',
];

for (const id of requiredTemplateIds) {
    assert.match(template, new RegExp(`id="${id}"`), `template should include #${id}`);
}

assert.match(template, />\s*角色卡\s*</, 'detail tab should be labeled as character cards');
assert.match(template, /<h4>角色卡<\/h4>/, 'character panel heading should use character-card copy');
assert.match(template, /AI 生成角色卡/, 'analysis button should generate character cards');
assert.match(template, /id="btn-open-character-library"/, 'novel detail should link to full character library');

assert.match(novelsJs, /async function loadNovelCharacterAnalysis\(novelId\)/, 'detail view should load character analysis');
assert.match(novelsJs, /async function analyzeNovelCharactersWithAI\(novelId\)/, 'detail view should trigger AI analysis');
assert.match(novelsJs, /openCharacterLibraryForNovel/, 'novel detail should open character library filtered by novel');
assert.match(novelsJs, /function getCharacterProfile\(character\)/, 'frontend should normalize role-card profile fields');
assert.match(novelsJs, /function renderCharacterProfileMeta/, 'frontend should render role-card profile metadata');
assert.match(novelsJs, /function renderNovelCharacterAnalysis\(analysis\)/, 'frontend should render character-card analysis');
assert.match(novelsJs, /AI 正在生成角色卡/, 'frontend should show role-card generation loading copy');
assert.match(novelsJs, /已生成 \$\{res\.data\.character_count\} 张角色卡/, 'success toast should use role-card copy');
assert.match(novelsJs, /function renderCharacterRelationshipGraph/, 'frontend should render a relationship graph');
assert.match(novelsJs, /function switchNovelDetailTab\(tabName\)/, 'detail view should switch tab panels');
assert.match(novelsJs, /novel-detail-tab'\)\.forEach/, 'detail tabs should be updated together');
assert.match(novelsJs, /\/api\/novels\/\$\{novelId\}\/characters/, 'frontend should call the character data API');
assert.match(novelsJs, /\/api\/ai\/novels\/\$\{novelId\}\/characters\/analyze/, 'frontend should call the AI character analysis API');
assert.match(novelsJs, /<defs>[\s\S]*marker/, 'relationship graph should define arrow markers');
assert.match(novelsJs, /novel-relation-legend/, 'relationship graph should render a legend');
assert.match(novelsJs, /novel-relation-line strength-/, 'relationship graph should style relation confidence');
assert.match(template, /\u751f\u6210\u540e\u4f1a\u5c55\u793a\u5173\u7cfb\u8c31/, 'template graph empty state should use role-card copy');
assert.doesNotMatch(template, /\u5206\u6790\u540e\u4f1a\u751f\u6210\u5173\u7cfb\u56fe/, 'template should not use stale relationship-analysis graph empty copy');
assert.match(novelsJs, /\u6682\u65e0\u89d2\u8272\u5361\u6570\u636e/, 'character graph/list empty states should use role-card copy');
assert.match(novelsJs, /\u89d2\u8272\u5361\u6570\u636e\u52a0\u8f7d\u5931\u8d25/, 'character-card load failure should use role-card copy');
assert.match(novelsJs, /\u52a0\u8f7d\u89d2\u8272\u5361\u6570\u636e\u5931\u8d25:/, 'character-card load warning should use role-card copy');
assert.doesNotMatch(novelsJs, /\u52a0\u8f7d\u89d2\u8272\u5173\u7cfb\u5206\u6790\u5931\u8d25|'\u89d2\u8272\u6570\u636e\u52a0\u8f7d\u5931\u8d25'|\u6682\u65e0\u89d2\u8272\u6570\u636e/, 'role-card flow should not use stale role/relationship-analysis copy');

const showToastMatch = coreJs.match(/function showToast\(message, type = 'success'\) \{[\s\S]*?\n\}/);
assert.ok(showToastMatch, 'core should define showToast');
const showToastBody = showToastMatch[0];
assert.match(showToastBody, /\.textContent\s*=\s*message/, 'showToast should render the message with textContent');
assert.doesNotMatch(showToastBody, /innerHTML\s*=\s*`[\s\S]*\$\{message\}/, 'showToast should not interpolate message into innerHTML');

assert.match(novelsCss, /\.novel-detail-tabs/, 'detail tabs should be styled');
assert.match(novelsCss, /\.novel-detail-tab/, 'detail tab buttons should be styled');
assert.match(novelsCss, /\.novel-detail-panel/, 'detail tab panels should be styled');
assert.match(novelsCss, /\.novel-character-panel/, 'character panel should be styled');
assert.match(novelsCss, /\.novel-character-graph/, 'relationship graph should be styled');
assert.match(novelsCss, /\.novel-character-card/, 'character cards should be styled');
assert.match(novelsCss, /\.novel-character-card-summary/, 'character cards should style summary text');
assert.match(novelsCss, /\.novel-character-profile-grid/, 'character cards should style profile metadata');
assert.match(novelsCss, /\.novel-character-profile-item/, 'character cards should style each profile item');
assert.match(novelsCss, /\.novel-relation-card/, 'relation cards should be styled');
assert.match(novelsCss, /\.novel-relation-line\.strength-high/, 'high-confidence graph lines should be styled');
assert.match(novelsCss, /\.novel-relation-legend/, 'relationship graph legend should be styled');

console.log('character analysis UI checks passed');
