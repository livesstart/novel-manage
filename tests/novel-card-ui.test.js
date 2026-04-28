const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const appJs = fs.readFileSync(path.join(root, 'static/js/app.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'static/css/style.css'), 'utf8');

assert.match(
    appJs,
    /<label class="novel-select-control"/,
    'novel cards should render a custom selection control wrapper'
);

assert.match(
    appJs,
    /aria-label="批量选择/,
    'selection control should have an accessible label'
);

assert.match(
    appJs,
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
