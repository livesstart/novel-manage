const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const novelsJs = fs.readFileSync(path.join(root, 'static/js/novel-detail.js'), 'utf8');
const coreJs = fs.readFileSync(path.join(root, 'static/js/core.js'), 'utf8');
const novelsCss = fs.readFileSync(path.join(root, 'static/css/novels.css'), 'utf8');

const requiredTemplateIds = [
    'novel-detail-tab-settings',
    'novel-detail-panel-settings',
    'novel-setting-panel',
    'btn-detail-analyze-settings',
    'novel-setting-status',
    'novel-setting-list',
];

for (const id of requiredTemplateIds) {
    assert.match(template, new RegExp(`id="${id}"`), `template should include #${id}`);
}

assert.match(template, />\s*设定集\s*</, 'detail tab should expose the setting analysis panel');
assert.match(template, /AI 提取设定/, 'detail panel should trigger AI setting extraction');
assert.match(coreJs, /detailSettingAnalysis: null/, 'shared state should track setting analysis');

assert.match(novelsJs, /function resetNovelSettingAnalysis\(\)/, 'detail view should reset setting analysis');
assert.match(novelsJs, /function renderNovelSettingAnalysis\(analysis\)/, 'detail view should render setting analysis');
assert.match(novelsJs, /async function loadNovelSettingAnalysis\(novelId\)/, 'detail view should load setting analysis');
assert.match(novelsJs, /async function analyzeNovelSettingsWithAI\(novelId\)/, 'detail view should trigger AI setting extraction');
assert.match(novelsJs, /\/api\/novels\/\$\{novelId\}\/settings/, 'frontend should call the setting data API');
assert.match(novelsJs, /\/api\/ai\/novels\/\$\{novelId\}\/settings\/analyze/, 'frontend should call the AI setting extraction API');
assert.match(novelsJs, /AI 正在提取小说设定/, 'frontend should show setting extraction loading copy');
assert.match(novelsJs, /已提取 \$\{res\.data\.setting_count\} 条小说设定/, 'success toast should report setting count');

assert.match(novelsCss, /\.novel-setting-panel/, 'setting panel should be styled');
assert.match(novelsCss, /\.novel-setting-list/, 'setting list should be styled');
assert.match(novelsCss, /\.novel-setting-card/, 'setting cards should be styled');
assert.match(novelsCss, /\.novel-setting-evidence/, 'setting cards should show evidence styling');

console.log('novel setting UI checks passed');
