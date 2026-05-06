const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const cssDir = path.join(root, 'static/css');
const styleCss = fs.readFileSync(path.join(cssDir, 'style.css'), 'utf8');

const expectedImports = [
    'base.css',
    'layout.css',
    'components.css',
    'novels.css',
    'forms.css',
    'import.css',
    'batch.css',
    'crawler.css',
    'reader.css',
    'ai.css',
    'characters.css',
    'admin.css',
    'overrides.css',
];

let previousIndex = -1;
for (const fileName of expectedImports) {
    const importLine = `@import url('./${fileName}');`;
    const currentIndex = styleCss.indexOf(importLine);

    assert.notEqual(currentIndex, -1, `${fileName} should be imported by style.css`);
    assert.ok(currentIndex > previousIndex, `${fileName} should be imported after the previous CSS file`);
    assert.ok(fs.existsSync(path.join(cssDir, fileName)), `${fileName} should exist on disk`);

    previousIndex = currentIndex;
}

const nonImportContent = styleCss
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .filter(line => !line.startsWith('@import'));

assert.deepEqual(nonImportContent, [], 'style.css should remain a small import-only entrypoint');

console.log('frontend CSS split checks passed');
