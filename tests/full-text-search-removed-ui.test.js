const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const novelsJs = fs.readFileSync(path.join(root, 'static/js/novels.js'), 'utf8');
const appJs = fs.readFileSync(path.join(root, 'static/js/app.js'), 'utf8');
const novelsCss = fs.readFileSync(path.join(root, 'static/css/novels.css'), 'utf8');

assert.doesNotMatch(template, /id="full-text-search-toggle"/, 'template should not expose the full-text toggle');
assert.doesNotMatch(template, /id="full-text-search-results"/, 'template should not expose full-text results');

assert.doesNotMatch(appJs, /full-text-search-toggle/, 'app should not bind full-text toggle events');
assert.doesNotMatch(novelsJs, /searchFullTextNovels/, 'frontend should not call full-text search');
assert.doesNotMatch(novelsJs, /renderFullTextSearchResults/, 'frontend should not render full-text results');
assert.doesNotMatch(novelsJs, /\/api\/search\/fulltext/, 'frontend should not call the removed full-text API');
assert.doesNotMatch(novelsJs, /fullTextSearchPollTimer/, 'frontend should not keep full-text polling state');

assert.doesNotMatch(novelsCss, /\.full-text-search/, 'full-text search styles should be removed');
assert.doesNotMatch(novelsCss, /\.full-text-hit/, 'full-text hit styles should be removed');

console.log('full-text search removal UI checks passed');
