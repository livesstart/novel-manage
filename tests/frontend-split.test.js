const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');

const expectedScripts = [
    '/static/js/core.js',
    '/static/js/novel-render.js',
    '/static/js/novel-detail.js',
    '/static/js/novel-download.js',
    '/static/js/novels.js',
    '/static/js/reader.js',
    '/static/js/crawler.js',
    '/static/js/ai.js',
    '/static/js/batch.js',
    '/static/js/import.js',
    '/static/js/characters.js',
    '/static/js/admin.js',
    '/static/js/app-bindings.js',
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

const maxLineCounts = new Map([
    ['static/js/novels.js', 700],
    ['static/js/app.js', 220],
]);

for (const [relativePath, maxLines] of maxLineCounts.entries()) {
    const source = fs.readFileSync(path.join(root, relativePath), 'utf8');
    const lineCount = source.split(/\r?\n/).length;
    assert.ok(
        lineCount <= maxLines,
        `${relativePath} should stay focused (${lineCount} lines > ${maxLines})`
    );
}

const appBindingsSource = fs.readFileSync(path.join(root, 'static/js/app-bindings.js'), 'utf8');
const expectedBindingFunctions = [
    'bindNavigationEvents',
    'bindNovelFilterEvents',
    'bindNovelManagementEvents',
    'bindBatchActionEvents',
    'bindBatchImportEvents',
    'bindReaderEvents',
    'bindCrawlerEvents',
    'bindAIConfigEvents',
];

for (const functionName of expectedBindingFunctions) {
    assert.match(
        appBindingsSource,
        new RegExp(`function ${functionName}\\(`),
        `app-bindings.js should expose ${functionName}() to keep event binding maintainable`
    );
}

console.log('frontend split checks passed');
