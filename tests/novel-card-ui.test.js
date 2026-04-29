const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const novelsJs = fs.readFileSync(path.join(root, 'static/js/novels.js'), 'utf8');

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

assert.match(
    novelsJs,
    /<label class="novel-select-control"/,
    'novel cards should render a custom selection control wrapper'
);

assert.match(
    novelsJs,
    /aria-label="批量选择/,
    'selection control should have an accessible label'
);

assert.match(
    novelsJs,
    /class="novel-select-indicator"/,
    'selection control should render a styled visual indicator'
);

assert.match(
    css,
    /\.novel-select-control\s*\{/,
    'custom selection control should be styled'
);

assert.match(
    css,
    /\.novel-select-checkbox:checked\s*\+\s*\.novel-select-indicator/,
    'checked state should drive the visual indicator'
);

assert.match(
    css,
    /\.novel-select-indicator::after/,
    'visual indicator should include a check mark state'
);

console.log('novel card UI checks passed');
