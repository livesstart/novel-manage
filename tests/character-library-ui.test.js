const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const appJs = fs.readFileSync(path.join(root, 'static/js/app.js'), 'utf8');
const charactersJs = fs.readFileSync(path.join(root, 'static/js/characters.js'), 'utf8');
const styleCss = fs.readFileSync(path.join(root, 'static/css/style.css'), 'utf8');
const charactersCss = fs.readFileSync(path.join(root, 'static/css/characters.css'), 'utf8');

assert.match(template, /data-view="characters"/, 'sidebar should include character library nav');
assert.match(template, /id="view-characters"/, 'template should include character library view');
assert.match(template, /id="character-library-search"/, 'character library should include search input');
assert.match(template, /id="character-library-novel-filter"/, 'character library should include novel filter');
assert.match(template, /id="character-library-role-filter"/, 'character library should include role filter');
assert.match(template, /id="character-library-tag-filter"/, 'character library should include tag filter');
assert.match(template, /id="character-library-sort"/, 'character library should include sort control');
assert.match(template, /id="btn-character-create"/, 'character library should include create button');
assert.match(template, /id="btn-character-ai-generate"/, 'character library should include per-novel AI generation button');
assert.match(template, /id="character-library-grid"/, 'character library should include card grid');
assert.match(template, /id="character-drawer"/, 'character library should include detail drawer');
assert.match(template, /id="character-relation-list"/, 'character drawer should include relation list');

assert.match(styleCss, /characters\.css/, 'style entry should import character library css');
assert.match(template, /\/static\/js\/characters\.js/, 'template should load character library script');

assert.match(appJs, /loadCharacterLibrary\(\)/, 'app should load character library when switching views');
assert.match(charactersJs, /const characterState/, 'characters module should define character state');
assert.match(charactersJs, /async function loadCharacterLibrary/, 'characters module should load character library');
assert.match(charactersJs, /function renderCharacterFilters/, 'characters module should render filters');
assert.match(charactersJs, /function renderCharacterCards/, 'characters module should render cards');
assert.match(charactersJs, /function collectCharacterFormData/, 'characters module should collect drawer form data');
assert.match(charactersJs, /function renderCharacterRelations/, 'characters module should render relation list');
assert.match(charactersJs, /async function openCharacterDrawer/, 'characters module should open drawer');
assert.match(charactersJs, /async function saveCharacter/, 'characters module should save characters');
assert.match(charactersJs, /async function deleteCharacter/, 'characters module should delete characters');
assert.match(charactersJs, /async function completeCharacterWithAI/, 'characters module should call AI completion');
assert.match(charactersJs, /async function saveCharacterRelation/, 'characters module should save relations');
assert.match(charactersJs, /async function deleteCharacterRelation/, 'characters module should delete relations');
assert.match(charactersJs, /\/api\/characters/, 'characters module should call character API');
assert.match(charactersJs, /\/api\/character-relations/, 'characters module should call relation API');

assert.match(charactersCss, /\.character-library-shell/, 'character CSS should style page shell');
assert.match(charactersCss, /\.character-library-card/, 'character CSS should style cards');
assert.match(charactersCss, /\.character-drawer/, 'character CSS should style drawer');
assert.match(charactersCss, /\.character-relation-editor/, 'character CSS should style relation editor');

console.log('character library UI checks passed');
