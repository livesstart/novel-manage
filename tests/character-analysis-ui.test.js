const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const novelsJs = fs.readFileSync(path.join(root, 'static/js/novels.js'), 'utf8');
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

assert.match(novelsJs, /async function loadNovelCharacterAnalysis\(novelId\)/, 'detail view should load character analysis');
assert.match(novelsJs, /async function analyzeNovelCharactersWithAI\(novelId\)/, 'detail view should trigger AI analysis');
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
