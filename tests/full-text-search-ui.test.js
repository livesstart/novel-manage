const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const novelsJs = fs.readFileSync(path.join(root, 'static/js/novels.js'), 'utf8');
const appJs = fs.readFileSync(path.join(root, 'static/js/app.js'), 'utf8');
const novelsCss = fs.readFileSync(path.join(root, 'static/css/novels.css'), 'utf8');

assert.match(template, /id="full-text-search-toggle"/, 'template should expose the full-text toggle');
assert.match(template, /id="full-text-search-results"/, 'template should expose a full-text result container');

assert.match(appJs, /full-text-search-toggle'\)\.addEventListener\('change'/, 'app should bind the full-text toggle');
assert.match(novelsJs, /async function searchFullTextNovels\(query\)/, 'frontend should fetch full-text search results');
assert.match(novelsJs, /function renderFullTextSearchResults\(query, results\)/, 'frontend should render full-text results');
assert.match(novelsJs, /async function openFullTextSearchResult\(novelId, chapterIndex\)/, 'frontend should open a search hit');
assert.match(novelsJs, /\/api\/search\/fulltext\?\$\{params\}/, 'frontend should call the full-text API');
assert.match(novelsJs, /await openReader\(novelId\)/, 'search hits should open the reader');
assert.match(novelsJs, /await loadChapter\(Number\(chapterIndex\)\)/, 'search hits should jump to the matched chapter');

assert.match(novelsCss, /\.full-text-search-results/, 'full-text results should be styled');
assert.match(novelsCss, /\.full-text-search-result/, 'full-text result rows should be styled');
assert.match(novelsCss, /\.full-text-hit-snippet/, 'full-text snippets should be styled');
assert.match(
    novelsCss,
    /\.search-box input#full-text-search-toggle[\s\S]*width:\s*14px/,
    'full-text checkbox should not inherit the search input width'
);

console.log('full-text search UI checks passed');
