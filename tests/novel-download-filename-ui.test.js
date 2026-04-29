const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const novelsJs = fs.readFileSync(path.join(root, 'static/js/novels.js'), 'utf8');

const context = {
    console,
    URLSearchParams,
};
vm.createContext(context);
vm.runInContext(novelsJs, context);

assert.equal(
    typeof context.parseDownloadFilename,
    'function',
    'download filename parsing should be testable as a pure helper'
);

assert.equal(
    context.parseDownloadFilename(
        "attachment; filename=\"____.txt\"; filename*=UTF-8''%E6%97%A5%E5%9C%A8%E6%A0%A1%E5%9B%AD.txt",
        'fallback.txt'
    ),
    '\u65e5\u5728\u6821\u56ed.txt',
    'RFC 5987 filename* should preserve Chinese names instead of using the ASCII fallback'
);

assert.equal(
    context.parseDownloadFilename('attachment; filename="plain-title.txt"', 'fallback.txt'),
    'plain-title.txt',
    'plain filename should still work when filename* is absent'
);

assert.equal(
    context.parseDownloadFilename(null, 'fallback.txt'),
    'fallback.txt',
    'missing Content-Disposition should use the provided fallback filename'
);

console.log('novel download filename UI checks passed');
