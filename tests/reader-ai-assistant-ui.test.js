const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
const readerJs = fs.readFileSync(path.join(root, 'static/js/reader.js'), 'utf8');
const appJs = fs.readFileSync(path.join(root, 'static/js/app.js'), 'utf8');
const readerCss = fs.readFileSync(path.join(root, 'static/css/reader.css'), 'utf8');

assert.match(template, /id="reader-ai-toggle"/, 'reader should expose an AI assistant toolbar button');
assert.match(template, /id="reader-ai-panel"/, 'reader should render an AI assistant panel');
assert.match(template, /id="reader-ai-status"/, 'reader assistant should render context status');
assert.match(template, /id="reader-ai-messages"/, 'reader assistant should render messages');
assert.match(template, /id="reader-ai-input"/, 'reader assistant should include a text input');
assert.match(template, /id="reader-ai-send"/, 'reader assistant should include a send button');
assert.match(template, /id="reader-ai-clear"/, 'reader assistant should include a clear button');
assert.match(template, /id="reader-ai-close"/, 'reader assistant should include a close button');

assert.match(readerJs, /isAssistantOpen:\s*false/, 'reader state should track assistant panel visibility');
assert.match(readerJs, /assistantMessages:\s*\[\]/, 'reader state should track assistant messages');
assert.match(readerJs, /function resetReaderAssistantState\(\)/, 'reader should reset assistant state');
assert.match(readerJs, /function toggleReaderAssistantPanel\(\)/, 'reader should toggle assistant panel');
assert.match(readerJs, /function renderReaderAssistantMessages\(\)/, 'reader should render assistant messages');
assert.match(readerJs, /async function sendReaderAssistantQuestion\(\)/, 'reader should send assistant questions');
assert.match(readerJs, /\/api\/ai\/novels\/\$\{requestNovelId\}\/reader-assistant/, 'reader should call the reader assistant API with the request novel snapshot');
assert.match(readerJs, /formatReaderAssistantContextStatus/, 'reader should format context status');
assert.match(readerJs, /closeReaderAssistantPanel\(\)/, 'reader should close assistant when needed');

assert.match(appJs, /reader-ai-toggle'\)\.addEventListener\('click',\s*toggleReaderAssistantPanel\)/, 'app should bind assistant toggle');
assert.match(appJs, /reader-ai-send'\)\.addEventListener\('click',\s*sendReaderAssistantQuestion\)/, 'app should bind assistant send');
assert.match(appJs, /reader-ai-clear'\)\.addEventListener\('click',\s*clearReaderAssistantMessages\)/, 'app should bind assistant clear');
assert.match(appJs, /reader-ai-close'\)\.addEventListener\('click',\s*closeReaderAssistantPanel\)/, 'app should bind assistant close');

assert.match(readerCss, /\.reader-ai-panel/, 'reader assistant panel should be styled');
assert.match(readerCss, /\.reader-ai-message\.user/, 'reader assistant user messages should be styled');
assert.match(readerCss, /\.reader-ai-message\.assistant/, 'reader assistant responses should be styled');
assert.match(readerCss, /@media \(max-width:\s*768px\)[\s\S]*\.reader-ai-panel/, 'reader assistant should have mobile styles');
assert.match(
    readerCss,
    /@media \(max-width:\s*1024px\)[\s\S]*\.reader-ai-panel\s*\{[\s\S]*position:\s*fixed/,
    'reader assistant should overlay instead of squeezing tablet/narrow desktop reader content'
);
assert.match(
    appJs,
    /function isReaderEditableShortcutTarget\(target\)[\s\S]*contentEditable[\s\S]*if \(isReaderEditableShortcutTarget\(e\.target\)\) return;[\s\S]*e\.key\.toLowerCase\(\) === 'f'/,
    'reader Ctrl/Cmd+F shortcut should ignore editable targets before opening reader search'
);

async function assertStaleReaderAssistantResponseIsIgnored() {
    const elements = new Map();
    const makeElement = () => ({
        value: '',
        textContent: '',
        innerHTML: '',
        disabled: false,
        scrollHeight: 0,
        scrollTop: 0,
        focusCalled: false,
        focus() {
            this.focusCalled = true;
        },
        classList: {
            toggle() {},
            add() {},
            remove() {}
        },
        setAttribute() {}
    });

    [
        'reader-ai-input',
        'reader-ai-panel',
        'reader-ai-toggle',
        'reader-ai-status',
        'reader-ai-error',
        'reader-ai-send',
        'reader-ai-messages',
        'reader-chapter-title'
    ].forEach(id => elements.set(id, makeElement()));

    elements.get('reader-ai-input').value = 'What does this scene reveal?';
    elements.get('reader-chapter-title').textContent = 'Chapter One';

    let resolveAssistantRequest;
    const sandbox = {
        console: { warn() {}, error() {} },
        localStorage: {
            getItem() { return null; },
            setItem() {}
        },
        window: {
            setTimeout,
            clearTimeout,
            matchMedia() {
                return { matches: false };
            }
        },
        document: {
            getElementById(id) {
                return elements.get(id) || null;
            },
            querySelector() {
                return null;
            },
            querySelectorAll() {
                return [];
            }
        },
        api: {
            post() {
                return new Promise(resolve => {
                    resolveAssistantRequest = resolve;
                });
            }
        },
        escapeHtml(value) {
            return String(value);
        }
    };

    vm.createContext(sandbox);
    vm.runInContext(`${readerJs}\nthis.__readerTest = { readerState, resetReaderAssistantState, sendReaderAssistantQuestion };`, sandbox);

    const { readerState, resetReaderAssistantState, sendReaderAssistantQuestion } = sandbox.__readerTest;
    readerState.novelId = 101;
    readerState.currentChapter = 0;

    const pendingRequest = sendReaderAssistantQuestion();
    assert.equal(typeof resolveAssistantRequest, 'function', 'assistant request should be pending before session changes');

    readerState.novelId = 202;
    resetReaderAssistantState();

    resolveAssistantRequest({
        success: true,
        data: {
            answer: 'This answer belongs to the previous novel.',
            context: { is_full_text: true, included_chars: 1200 }
        }
    });
    await pendingRequest;

    assert.equal(readerState.assistantMessages.length, 0, 'stale assistant answer should not appear in the new reader session');
    assert.equal(readerState.assistantContext, null, 'stale assistant context should not replace the new reader session context');
    assert.equal(readerState.assistantError, '', 'stale assistant response should not set an error in the new reader session');
    assert.equal(readerState.assistantSending, false, 'new reader session should remain idle after stale request settles');
}

assertStaleReaderAssistantResponseIsIgnored()
    .then(() => {
        console.log('reader AI assistant UI checks passed');
    })
    .catch(err => {
        console.error(err);
        process.exitCode = 1;
    });
