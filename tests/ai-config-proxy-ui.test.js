const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const aiJs = fs.readFileSync(path.join(root, 'static/js/ai.js'), 'utf8');

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
    template,
    /id="ai-config-use-proxy"/,
    'AI config modal should expose a proxy enable toggle'
);

assert.match(
    template,
    /id="ai-config-proxy-url"/,
    'AI config modal should expose a proxy URL input'
);

assert.match(
    aiJs,
    /use_proxy:\s*document\.getElementById\('ai-config-use-proxy'\)\.checked/,
    'AI config form collection should include use_proxy'
);

assert.match(
    aiJs,
    /proxy_url:\s*document\.getElementById\('ai-config-proxy-url'\)\.value\.trim\(\)/,
    'AI config form collection should include proxy_url'
);

assert.match(
    css,
    /#view-ai-config\s+\.ai-config-actions\s+\.btn-icon-only\s*\{[\s\S]*?justify-content:\s*center;/,
    'AI config delete icon button should center its icon'
);

console.log('AI config proxy UI checks passed');
