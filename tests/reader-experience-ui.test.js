const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const readerJs = fs.readFileSync(path.join(root, 'static/js/reader.js'), 'utf8');
const appJs = fs.readFileSync(path.join(root, 'static/js/app.js'), 'utf8');
const readerCss = fs.readFileSync(path.join(root, 'static/css/reader.css'), 'utf8');

assert.match(template, /id="reader-toc-toggle"/, 'reader should expose a table-of-contents toggle');
assert.match(template, /id="reader-settings-toggle"/, 'reader should expose a settings toggle');
assert.match(template, /id="reader-immersive-toggle"/, 'reader should expose an immersive mode toggle');
assert.match(template, /id="reader-settings-panel"/, 'reader should render a settings panel');
assert.match(template, /id="reader-theme-select"/, 'reader settings should include theme selection');
assert.match(template, /id="reader-line-height"/, 'reader settings should include line height control');
assert.match(template, /id="reader-width"/, 'reader settings should include content width control');
assert.match(template, /id="reader-spacing"/, 'reader settings should include paragraph spacing control');
assert.match(template, /id="reader-progress-track"/, 'reader should render chapter progress track');
assert.match(template, /id="reader-scroll-percent"/, 'reader should render chapter scroll percentage');

assert.match(readerJs, /READER_SETTINGS_STORAGE_KEY/, 'reader settings should have a stable localStorage key');
assert.match(readerJs, /localStorage\.setItem\(READER_SETTINGS_STORAGE_KEY/, 'reader should persist reading preferences');
assert.match(readerJs, /function applyReaderSettings/, 'reader should apply persisted reading preferences');
assert.match(readerJs, /function updateReaderViewportProgress/, 'reader should update chapter progress while scrolling');
assert.match(readerJs, /function scrollReaderByPage/, 'reader should support page-wise keyboard scrolling');
assert.match(readerJs, /function toggleReaderImmersiveMode/, 'reader should support immersive mode');
assert.match(readerJs, /function toggleReaderToc/, 'reader should support table-of-contents toggle');

assert.match(appJs, /reader-settings-toggle'\)\.addEventListener\('click',\s*toggleReaderSettingsPanel\)/, 'app should bind settings toggle');
assert.match(appJs, /reader-immersive-toggle'\)\.addEventListener\('click',\s*toggleReaderImmersiveMode\)/, 'app should bind immersive toggle');
assert.match(appJs, /reader-toc-toggle'\)\.addEventListener\('click',\s*toggleReaderToc\)/, 'app should bind TOC toggle');
assert.match(appJs, /scrollReaderByPage\(1\)/, 'keyboard shortcuts should scroll down by page');
assert.match(appJs, /scrollReaderByPage\(-1\)/, 'keyboard shortcuts should scroll up by page');

assert.match(readerCss, /\.reader-settings-panel/, 'reader settings panel should be styled');
assert.match(readerCss, /\.reader-progress-track/, 'reader progress track should be styled');
assert.match(readerCss, /\.reader-modal\.theme-sepia/, 'reader should include a sepia theme');
assert.match(readerCss, /\.reader-modal\.theme-green/, 'reader should include an eye-care theme');
assert.match(readerCss, /\.reader-modal\.immersive/, 'reader should include immersive layout styles');

console.log('reader experience UI checks passed');
