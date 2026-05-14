const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const novelsJs = fs.readFileSync(path.join(root, 'static/js/novels.js'), 'utf8');
const coreJs = fs.readFileSync(path.join(root, 'static/js/core.js'), 'utf8');
const novelsCss = fs.readFileSync(path.join(root, 'static/css/novels.css'), 'utf8');

const requiredTemplateIds = [
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
    'btn-copy-writing-style-prompt',
];

for (const id of requiredTemplateIds) {
    assert.match(template, new RegExp(`id="${id}"`), `template should include #${id}`);
}

assert.match(template, />\s*写作风格\s*</, 'detail tab should expose the writing style panel');
assert.match(template, /AI 提取风格/, 'detail panel should trigger AI writing style extraction');
assert.match(coreJs, /detailWritingStyleAnalysis: null/, 'shared state should track writing style analysis');

assert.match(novelsJs, /function resetNovelWritingStyleAnalysis\(\)/, 'detail view should reset writing style analysis');
assert.match(novelsJs, /function renderNovelWritingStyleAnalysis\(analysis\)/, 'detail view should render writing style analysis');
assert.match(novelsJs, /async function loadNovelWritingStyleAnalysis\(novelId\)/, 'detail view should load writing style analysis');
assert.match(novelsJs, /async function analyzeNovelWritingStyleWithAI\(novelId\)/, 'detail view should trigger AI writing style extraction');
assert.match(novelsJs, /async function copyNovelWritingStylePrompt\(\)/, 'detail view should copy the generated style prompt');
assert.match(novelsJs, /\/api\/novels\/\$\{novelId\}\/writing-style/, 'frontend should call the writing style data API');
assert.match(novelsJs, /\/api\/ai\/novels\/\$\{novelId\}\/writing-style\/analyze/, 'frontend should call the AI writing style extraction API');
assert.match(novelsJs, /AI 正在提取写作风格/, 'frontend should show writing style extraction loading copy');
assert.match(novelsJs, /已提取写作风格/, 'success toast should report writing style extraction');

assert.match(novelsCss, /\.novel-writing-style-panel/, 'writing style panel should be styled');
assert.match(novelsCss, /\.novel-writing-style-grid/, 'writing style dimensions should use a grid');
assert.match(novelsCss, /\.novel-writing-style-card/, 'writing style cards should be styled');
assert.match(novelsCss, /\.novel-writing-style-prompt/, 'writing style prompt should be styled');

console.log('writing style UI checks passed');
