const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const novelsJs = fs.readFileSync(path.join(root, 'static/js/novels.js'), 'utf8');
const novelsCss = fs.readFileSync(path.join(root, 'static/css/novels.css'), 'utf8');

function readImportedCss() {
    const cssDir = path.join(root, 'static/css');
    const styleCss = fs.readFileSync(path.join(cssDir, 'style.css'), 'utf8');
    const imports = [...styleCss.matchAll(/@import url\('\.\/([^']+)'\);/g)]
        .map(match => match[1]);

    return imports
        .map(fileName => fs.readFileSync(path.join(cssDir, fileName), 'utf8'))
        .join('\n');
}

const css = readImportedCss();

const requiredTemplateIds = [
    'novel-detail-modal',
    'novel-detail-title',
    'novel-detail-author',
    'novel-detail-status',
    'novel-detail-category',
    'novel-detail-tags',
    'novel-detail-description',
    'novel-detail-progress',
    'novel-detail-last-read',
    'novel-detail-file-status',
    'novel-detail-file-path',
    'novel-detail-file-size',
    'novel-detail-file-updated',
    'novel-detail-chapter-count',
    'novel-detail-char-count',
    'btn-detail-read',
    'btn-detail-download',
    'btn-detail-edit',
    'btn-detail-check-file',
];

for (const id of requiredTemplateIds) {
    assert.match(template, new RegExp(`id="${id}"`), `template should include #${id}`);
}

assert.match(novelsJs, /onclick="openNovelDetail\(\$\{novel\.id\}\)"/, 'novel cards should expose a detail action');
assert.match(novelsJs, /async function openNovelDetail\(novelId\)/, 'frontend should load and open novel detail');
assert.match(novelsJs, /async function loadNovelDetailFileInfo\(novelId\)/, 'frontend should load file detail information');
assert.match(novelsJs, /\/api\/novels\/\$\{novelId\}\/check-file/, 'detail view should use the file check API');
assert.match(novelsJs, /\/api\/novels\/\$\{novelId\}\/read/, 'detail view should use the read API for chapter stats');
assert.match(novelsJs, /function renderNovelDetailTags/, 'detail view should render tags cleanly');
assert.match(novelsJs, /function formatFileSize/, 'detail view should format file sizes');
assert.match(novelsJs, /function formatDateTime/, 'detail view should format timestamps');

assert.match(novelsCss, /\.novel-detail-modal/, 'detail modal should be styled');
assert.match(novelsCss, /\.novel-detail-hero/, 'detail hero area should be styled');
assert.match(novelsCss, /\.novel-detail-metrics/, 'detail metrics should be styled');
assert.match(novelsCss, /\.novel-detail-file-card/, 'file information card should be styled');
assert.match(novelsCss, /\.novel-detail-status-pill/, 'file status pill should be styled');

assert.match(
    css,
    /\.modal-content\s*\{[^}]*display:\s*flex;[^}]*flex-direction:\s*column;[^}]*max-height:\s*min\(90vh,\s*calc\(100vh - 32px\)\);/s,
    'final modal styles should bound modal height and preserve a stable header/body/footer layout'
);

assert.match(
    css,
    /\.modal-body\s*\{[^}]*min-height:\s*0;[^}]*overflow-y:\s*auto;/s,
    'modal body should scroll so long detail character analysis remains reachable'
);

console.log('novel detail UI checks passed');
