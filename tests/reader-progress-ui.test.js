const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const frontendJs = [
    'core.js',
    'novel-render.js',
    'novel-detail.js',
    'novel-download.js',
    'novels.js',
    'reader.js',
    'crawler.js',
    'ai.js',
    'batch.js',
    'import.js',
    'app-bindings.js',
    'app.js',
].map(fileName => fs.readFileSync(path.join(root, 'static/js', fileName), 'utf8')).join('\n');

assert.match(
    frontendJs,
    /reading_progress/,
    'reader should consume reading_progress returned by the read API'
);

assert.match(
    frontendJs,
    /loadChapter\(startChapterIndex,\s*\{\s*scrollPercent:/,
    'reader should restore the saved chapter and scroll percentage when opened'
);

assert.match(
    frontendJs,
    /\/api\/novels\/\$\{readerState\.novelId\}\/reading-progress/,
    'reader should persist progress through the reading-progress API'
);

assert.match(
    frontendJs,
    /reader-content'\)\.addEventListener\('scroll',\s*scheduleSaveReadingProgress\)/,
    'reader should save progress when the reading pane scrolls'
);

console.log('reader progress UI checks passed');
