const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const appJs = fs.readFileSync(path.join(root, 'static/js/app.js'), 'utf8');

assert.match(
    appJs,
    /reading_progress/,
    'reader should consume reading_progress returned by the read API'
);

assert.match(
    appJs,
    /loadChapter\(startChapterIndex,\s*\{\s*scrollPercent:/,
    'reader should restore the saved chapter and scroll percentage when opened'
);

assert.match(
    appJs,
    /\/api\/novels\/\$\{readerState\.novelId\}\/reading-progress/,
    'reader should persist progress through the reading-progress API'
);

assert.match(
    appJs,
    /reader-content'\)\.addEventListener\('scroll',\s*scheduleSaveReadingProgress\)/,
    'reader should save progress when the reading pane scrolls'
);

console.log('reader progress UI checks passed');
