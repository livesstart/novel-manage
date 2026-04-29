const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');

const expectedScripts = [
    '/static/js/core.js',
    '/static/js/novels.js',
    '/static/js/reader.js',
    '/static/js/crawler.js',
    '/static/js/ai.js',
    '/static/js/batch.js',
    '/static/js/import.js',
    '/static/js/app.js',
];

let previousIndex = -1;
for (const scriptPath of expectedScripts) {
    const scriptTag = `<script src="${scriptPath}"></script>`;
    const currentIndex = template.indexOf(scriptTag);

    assert.notEqual(currentIndex, -1, `${scriptPath} should be loaded by the page template`);
    assert.ok(currentIndex > previousIndex, `${scriptPath} should be loaded after the previous frontend script`);
    assert.ok(fs.existsSync(path.join(root, scriptPath)), `${scriptPath} should exist on disk`);

    previousIndex = currentIndex;
}

console.log('frontend split checks passed');
