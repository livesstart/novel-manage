const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const novelsJs = fs.readFileSync(path.join(root, 'static/js/novels.js'), 'utf8');
const novelsCss = fs.readFileSync(path.join(root, 'static/css/novels.css'), 'utf8');

const requiredTemplateIds = [
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

assert.match(novelsJs, /async function loadNovelCharacterAnalysis\(novelId\)/, 'detail view should load character analysis');
assert.match(novelsJs, /async function analyzeNovelCharactersWithAI\(novelId\)/, 'detail view should trigger AI analysis');
assert.match(novelsJs, /function renderNovelCharacterAnalysis\(analysis\)/, 'frontend should render character analysis');
assert.match(novelsJs, /function renderCharacterRelationshipGraph/, 'frontend should render a relationship graph');
assert.match(novelsJs, /\/api\/novels\/\$\{novelId\}\/characters/, 'frontend should call the character data API');
assert.match(novelsJs, /\/api\/ai\/novels\/\$\{novelId\}\/characters\/analyze/, 'frontend should call the AI character analysis API');

assert.match(novelsCss, /\.novel-character-panel/, 'character panel should be styled');
assert.match(novelsCss, /\.novel-character-graph/, 'relationship graph should be styled');
assert.match(novelsCss, /\.novel-character-card/, 'character cards should be styled');
assert.match(novelsCss, /\.novel-relation-card/, 'relation cards should be styled');

console.log('character analysis UI checks passed');
