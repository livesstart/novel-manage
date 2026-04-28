const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const novelsView = template.match(/<div class="view" id="view-novels">([\s\S]*?)<!-- 分类管理视图 -->/);

assert.ok(novelsView, 'novels view markup should be present');
assert.doesNotMatch(
    novelsView[1],
    /class="hero-panel"|本地书库工作台|更清爽地整理/,
    'novels list view should not render the top workbench hero card'
);

console.log('novels view hero removal check passed');
