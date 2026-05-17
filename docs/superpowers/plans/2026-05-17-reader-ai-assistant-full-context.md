# Reader AI Assistant Full Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reader AI assistant and migrate existing novel analysis so both use whole-novel-first AI context with full-text or whole-book sampled fallback.

**Architecture:** Create a small backend `ai_context.py` module that builds structured novel AI context from the existing reader parser and cache. Wire `ai_routes.py` to use that module for character, setting, writing-style, and reader-assistant prompts. Add a right-side reader assistant panel in the existing reader modal, with transient in-memory chat state and static UI tests.

**Tech Stack:** Python 3, Flask, SQLite, `unittest`, native JavaScript, static Node assertion tests, existing `reader_utils.get_cached_reader_file`.

---

## File Structure

- Create `ai_context.py`: pure helper functions for metadata text, chapter extraction, full-text detection, long-book sampling, and context summaries.
- Create `tests/reader_ai_context.test.py`: backend tests for short full-text context, long sampled context, and focus chapter priority.
- Create `tests/reader_ai_assistant.test.py`: backend route tests for reader-assistant success and validation errors.
- Create `tests/reader-ai-assistant-ui.test.js`: static frontend tests for reader assistant markup, JavaScript functions, event bindings, and CSS selectors.
- Modify `ai_routes.py`: import `ai_context`, migrate existing analysis prompt construction, add reader-assistant route and message helpers.
- Modify `tests/character_analysis.test.py`: assert character analysis sees text beyond the old 12000-character prefix.
- Modify `tests/novel_setting_analysis.test.py`: assert setting analysis sees text beyond the old 12000-character prefix.
- Modify `tests/writing_style_analysis.test.py`: assert writing-style analysis sees text beyond the old 12000-character prefix.
- Modify `templates/index.html`: add reader AI toolbar button and assistant panel.
- Modify `static/js/reader.js`: add reader assistant state, rendering, send, clear, and panel controls.
- Modify `static/js/app.js`: bind reader assistant controls.
- Modify `static/css/reader.css`: style desktop and mobile reader assistant panel.

## Task 1: Whole-Novel AI Context Helper

**Files:**
- Create: `ai_context.py`
- Create: `tests/reader_ai_context.test.py`

- [ ] **Step 1: Write the failing context helper tests**

Create `tests/reader_ai_context.test.py` with this content:

```python
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import reader_utils


class ReaderAIContextTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        reader_utils.clear_reader_file_cache()

    def tearDown(self):
        reader_utils.clear_reader_file_cache()
        self.tmpdir.cleanup()

    def write_book(self, name, content):
        path = Path(self.tmpdir.name) / name
        path.write_text(content, encoding='utf-8')
        return path

    def resolve_path(self, file_path):
        path = Path(file_path)
        if path.exists():
            return str(path), [str(path)]
        return None, [str(path)]

    def is_readable(self, file_path):
        return Path(file_path).suffix.lower() == '.txt'

    def test_short_book_uses_complete_context(self):
        import ai_context

        book_path = self.write_book(
            'short.txt',
            'Chapter 1\nOpening clue.\nChapter 2\nFinal answer.'
        )
        novel = {
            'title': 'Short Context Book',
            'author': 'Context Author',
            'description': 'A compact book.',
            'category_name': 'Mystery',
            'tags': [{'name': 'clue'}, {'name': 'short'}],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=2000,
        )

        self.assertTrue(context['is_full_text'])
        self.assertFalse(context['is_truncated'])
        self.assertIn('Title: Short Context Book', context['metadata_text'])
        self.assertIn('Tags: clue, short', context['metadata_text'])
        self.assertIn('Opening clue.', context['content_text'])
        self.assertIn('Final answer.', context['content_text'])
        self.assertEqual(context['chapter_count'], 2)

    def test_long_book_samples_start_middle_and_end(self):
        import ai_context

        chapters = []
        for index in range(1, 13):
            marker = f'Middle clue {index}.'
            if index == 1:
                marker = 'Opening clue.'
            if index == 12:
                marker = 'Ending clue.'
            chapters.append(f'Chapter {index}\n{marker}\n' + ('filler text ' * 80))
        book_path = self.write_book('long.txt', '\n'.join(chapters))
        novel = {
            'title': 'Long Context Book',
            'author': 'Context Author',
            'description': 'A long book.',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=1800,
        )

        self.assertFalse(context['is_full_text'])
        self.assertTrue(context['is_truncated'])
        self.assertIn('Opening clue.', context['content_text'])
        self.assertIn('Ending clue.', context['content_text'])
        self.assertRegex(context['content_text'], r'Middle clue (4|5|6|7|8|9)\\.')
        self.assertGreaterEqual(len(context['segments']), 4)
        self.assertLessEqual(context['included_chars'], 1800)

    def test_focus_chapter_is_prioritized_in_sampled_context(self):
        import ai_context

        chapters = []
        for index in range(1, 16):
            marker = f'Normal chapter {index}.'
            if index == 9:
                marker = 'Focused chapter secret.'
            chapters.append(f'Chapter {index}\n{marker}\n' + ('padding ' * 100))
        book_path = self.write_book('focused.txt', '\n'.join(chapters))
        novel = {
            'title': 'Focused Context Book',
            'author': '',
            'description': '',
            'category_name': '',
            'tags': [],
            'file_path': str(book_path),
        }

        context = ai_context.build_novel_ai_context(
            novel,
            resolve_novel_file_path=self.resolve_path,
            is_text_readable_file=self.is_readable,
            char_budget=1600,
            focus_chapter_index=8,
        )

        self.assertFalse(context['is_full_text'])
        self.assertIn('Focused chapter secret.', context['content_text'])
        self.assertTrue(any(segment['chapter_index'] == 8 for segment in context['segments']))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the new tests and verify they fail for the missing module**

Run:

```powershell
python tests\reader_ai_context.test.py
```

Expected: `ModuleNotFoundError: No module named 'ai_context'`.

- [ ] **Step 3: Implement the context helper**

Create `ai_context.py` with this content:

```python
"""Helpers for building whole-novel AI context."""
from reader_utils import get_cached_reader_file


DEFAULT_AI_CONTEXT_CHAR_BUDGET = 60000
MAX_SAMPLED_CONTEXT_SEGMENTS = 10
MIN_SAMPLED_SEGMENT_CHARS = 800


def _clean_text(value):
    return str(value or '').strip()


def _tag_names(novel):
    names = []
    for item in novel.get('tags') or []:
        if isinstance(item, dict):
            name = _clean_text(item.get('name'))
        else:
            name = _clean_text(item)
        if name:
            names.append(name)
    return names


def build_novel_metadata_text(novel):
    lines = [
        f"Title: {_clean_text(novel.get('title')) or 'Not provided'}",
        f"Author: {_clean_text(novel.get('author')) or 'Not provided'}",
        f"Description: {_clean_text(novel.get('description')) or 'Not provided'}",
    ]
    category = _clean_text(novel.get('category_name'))
    if category:
        lines.append(f"Category: {category}")
    tags = _tag_names(novel)
    if tags:
        lines.append(f"Tags: {', '.join(tags)}")
    return '\n'.join(lines)


def _load_reader_chapters(novel, *, resolve_novel_file_path, is_text_readable_file):
    file_path = novel.get('file_path')
    if not file_path:
        return []

    actual_path, _ = resolve_novel_file_path(file_path)
    if not actual_path or not is_text_readable_file(actual_path):
        return []

    try:
        return get_cached_reader_file(actual_path).get('chapters') or []
    except Exception:
        return []


def _chapter_block(chapter, index, text):
    title = _clean_text(chapter.get('title')) or f'Chapter {index + 1}'
    return f"[Chapter {index + 1}] {title}\n{text.strip()}"


def _full_content_segments(chapters):
    segments = []
    for index, chapter in enumerate(chapters):
        text = _clean_text(chapter.get('content'))
        if not text:
            continue
        segments.append({
            'label': 'Full text',
            'chapter_index': index,
            'chapter_title': _clean_text(chapter.get('title')) or f'Chapter {index + 1}',
            'text': text,
        })
    return segments


def _sample_indices(chapter_count, focus_chapter_index=None):
    if chapter_count <= 0:
        return []
    if chapter_count == 1:
        return [0]

    target_count = min(MAX_SAMPLED_CONTEXT_SEGMENTS, chapter_count)
    indices = {0, chapter_count - 1}

    if isinstance(focus_chapter_index, int) and 0 <= focus_chapter_index < chapter_count:
        indices.add(focus_chapter_index)

    if target_count > 1:
        denominator = max(target_count - 1, 1)
        for position in range(target_count):
            indices.add(round((chapter_count - 1) * position / denominator))

    return sorted(indices)


def _segment_label(index, chapter_count, focus_chapter_index):
    if index == focus_chapter_index:
        return 'Focus chapter'
    if index == 0:
        return 'Opening sample'
    if index == chapter_count - 1:
        return 'Ending sample'
    return 'Middle sample'


def _sample_chapter_text(chapter, index, chapter_count, focus_chapter_index, per_segment_budget):
    text = _clean_text(chapter.get('content'))
    if len(text) <= per_segment_budget:
        return text
    if index == chapter_count - 1 and index != focus_chapter_index:
        return text[-per_segment_budget:]
    return text[:per_segment_budget]


def _sample_content_segments(chapters, *, char_budget, focus_chapter_index=None):
    indices = _sample_indices(len(chapters), focus_chapter_index)
    if not indices:
        return []

    per_segment_budget = max(MIN_SAMPLED_SEGMENT_CHARS, char_budget // len(indices) - 120)
    segments = []
    for index in indices:
        chapter = chapters[index]
        sampled_text = _sample_chapter_text(
            chapter,
            index,
            len(chapters),
            focus_chapter_index,
            per_segment_budget,
        )
        if not sampled_text:
            continue
        segments.append({
            'label': _segment_label(index, len(chapters), focus_chapter_index),
            'chapter_index': index,
            'chapter_title': _clean_text(chapter.get('title')) or f'Chapter {index + 1}',
            'text': sampled_text,
        })
    return segments


def _segments_to_text(segments):
    blocks = []
    for segment in segments:
        title = segment['chapter_title']
        label = segment['label']
        chapter_number = segment['chapter_index'] + 1
        blocks.append(f"[{label} | Chapter {chapter_number}] {title}\n{segment['text'].strip()}")
    return '\n\n'.join(blocks).strip()


def _trim_segments_to_budget(segments, char_budget):
    content = _segments_to_text(segments)
    if len(content) <= char_budget:
        return segments, content

    trimmed_segments = []
    remaining = char_budget
    for segment in segments:
        header = f"[{segment['label']} | Chapter {segment['chapter_index'] + 1}] {segment['chapter_title']}\n"
        available = remaining - len(header) - 2
        if available <= 0:
            break
        trimmed = dict(segment)
        trimmed['text'] = segment['text'][:available].strip()
        if trimmed['text']:
            trimmed_segments.append(trimmed)
            remaining -= len(header) + len(trimmed['text']) + 2
    return trimmed_segments, _segments_to_text(trimmed_segments)


def build_novel_ai_context(
    novel,
    *,
    resolve_novel_file_path,
    is_text_readable_file,
    char_budget=DEFAULT_AI_CONTEXT_CHAR_BUDGET,
    focus_chapter_index=None,
):
    chapters = _load_reader_chapters(
        novel,
        resolve_novel_file_path=resolve_novel_file_path,
        is_text_readable_file=is_text_readable_file,
    )
    source_chars = sum(len(_clean_text(chapter.get('content'))) for chapter in chapters)
    metadata_text = build_novel_metadata_text(novel)
    safe_budget = max(1000, int(char_budget or DEFAULT_AI_CONTEXT_CHAR_BUDGET))

    full_segments = _full_content_segments(chapters)
    full_content_text = _segments_to_text(full_segments)

    if full_content_text and len(full_content_text) <= safe_budget:
        segments = full_segments
        content_text = full_content_text
        is_full_text = True
    else:
        sampled = _sample_content_segments(
            chapters,
            char_budget=safe_budget,
            focus_chapter_index=focus_chapter_index,
        )
        segments, content_text = _trim_segments_to_budget(sampled, safe_budget)
        is_full_text = False if content_text else source_chars == 0

    included_chars = len(content_text)
    if content_text:
        scope_note = (
            'The following novel context is complete full text.'
            if is_full_text
            else 'The following novel context is sampled across the whole book, not complete full text.'
        )
        context_text = f"{metadata_text}\n\n{scope_note}\n\nNovel content context:\n{content_text}"
    else:
        context_text = f"{metadata_text}\n\nNovel content context: Not available."

    return {
        'metadata_text': metadata_text,
        'content_text': content_text,
        'context_text': context_text,
        'is_full_text': is_full_text,
        'is_truncated': source_chars > included_chars,
        'source_chars': source_chars,
        'included_chars': included_chars,
        'chapter_count': len(chapters),
        'segments': segments,
    }


def summarize_novel_ai_context(context):
    return {
        'is_full_text': bool(context.get('is_full_text')),
        'is_truncated': bool(context.get('is_truncated')),
        'included_chars': int(context.get('included_chars') or 0),
        'source_chars': int(context.get('source_chars') or 0),
        'chapter_count': int(context.get('chapter_count') or 0),
        'segment_count': len(context.get('segments') or []),
    }
```

- [ ] **Step 4: Run the context helper tests and verify they pass**

Run:

```powershell
python tests\reader_ai_context.test.py
```

Expected: `Ran 3 tests` and `OK`.

- [ ] **Step 5: Commit the context helper**

```powershell
git add ai_context.py tests\reader_ai_context.test.py
git commit -m "feat: add whole-novel ai context helper"
```

## Task 2: Migrate Existing Analysis Routes To Whole-Novel Context

**Files:**
- Modify: `ai_routes.py`
- Modify: `tests/character_analysis.test.py`
- Modify: `tests/novel_setting_analysis.test.py`
- Modify: `tests/writing_style_analysis.test.py`

- [ ] **Step 1: Add failing assertions to the character analysis test**

In `tests/character_analysis.test.py`, update `self.book_path.write_text(...)` in `setUp` so the file contains a marker beyond the old 12000-character prefix:

```python
self.book_path.write_text(
    'Chapter 1\nLin found the star key.\n'
    + ('prefix filler text\n' * 900)
    + 'Chapter 2\nShen confirmed the late-book alliance marker.\n',
    encoding='utf-8'
)
```

In `test_character_analysis_is_generated_and_persisted`, replace the old context assertion with:

```python
self.assertIn('Novel content context', self.fake_client.messages[1]['content'])
self.assertIn('Shen confirmed the late-book alliance marker.', self.fake_client.messages[1]['content'])
```

- [ ] **Step 2: Add failing assertions to the setting analysis test**

In `tests/novel_setting_analysis.test.py`, update `self.book_path.write_text(...)` in `setUp`:

```python
self.book_path.write_text(
    'Chapter 1\nThe star key glowed under the full moon.\n'
    + ('setting filler text\n' * 900)
    + 'Chapter 2\nThe Watchers guard the late-book ruin gate.\n',
    encoding='utf-8'
)
```

In `test_setting_analysis_is_generated_and_persisted`, replace the old context assertion with:

```python
self.assertIn('Novel content context', self.fake_client.messages[1]['content'])
self.assertIn('The Watchers guard the late-book ruin gate.', self.fake_client.messages[1]['content'])
```

- [ ] **Step 3: Add failing assertions to the writing-style analysis test**

In `tests/writing_style_analysis.test.py`, update `self.book_path.write_text(...)` in `setUp`:

```python
self.book_path.write_text(
    'Chapter 1\nThe prose opens with clipped observation.\n'
    + ('style filler text\n' * 900)
    + 'Chapter 2\nThe late style marker keeps the same restrained rhythm.\n',
    encoding='utf-8'
)
```

In `test_writing_style_analysis_is_generated_and_persisted`, replace the old context assertion with:

```python
self.assertIn('Novel content context', self.fake_client.messages[1]['content'])
self.assertIn('The late style marker keeps the same restrained rhythm.', self.fake_client.messages[1]['content'])
```

- [ ] **Step 4: Run the migrated analysis tests and verify they fail**

Run:

```powershell
python tests\character_analysis.test.py
python tests\novel_setting_analysis.test.py
python tests\writing_style_analysis.test.py
```

Expected: each changed test fails because `self.fake_client.messages[1]['content']` still contains the old front-only excerpt and does not contain the late marker.

- [ ] **Step 5: Import the context helper and add shared route helpers**

In `ai_routes.py`, add this import after the existing `ai_client` import block:

```python
from ai_context import (
    DEFAULT_AI_CONTEXT_CHAR_BUDGET,
    build_novel_ai_context,
    summarize_novel_ai_context,
)
```

Inside `register_ai_routes`, after `extract_text_excerpt`, add:

```python
    def build_ai_context_for_novel(novel, *, focus_chapter_index=None, char_budget=DEFAULT_AI_CONTEXT_CHAR_BUDGET):
        return build_novel_ai_context(
            novel,
            resolve_novel_file_path=resolve_novel_file_path,
            is_text_readable_file=is_text_readable_file,
            char_budget=char_budget,
            focus_chapter_index=focus_chapter_index,
        )


    def has_usable_novel_ai_context(novel, novel_context):
        return bool(
            novel.get('title')
            or novel.get('description')
            or novel_context.get('content_text')
        )
```

- [ ] **Step 6: Change the three analysis prompt builders to accept context objects**

Update the function signatures:

```python
    def build_character_analysis_messages(novel, novel_context):
```

```python
    def build_setting_analysis_messages(novel, novel_context):
```

```python
    def build_writing_style_analysis_messages(novel, novel_context):
```

In each function, replace the existing `context_blocks = [...]` and `if content_excerpt:` block with:

```python
        context_blocks = [novel_context.get('context_text') or 'Novel content context: Not available.']
```

Leave the rest of each task-specific prompt intact.

- [ ] **Step 7: Migrate character analysis route**

In `analyze_novel_characters`, replace:

```python
        content_excerpt = extract_text_excerpt(novel.get('file_path'), max_chars=12000)
        if not novel.get('title') and not novel.get('description') and not content_excerpt:
            return jsonify({'success': False, 'message': '请先填写书名，或提供可读取的 TXT 文件'}), 400
```

with:

```python
        novel_context = build_ai_context_for_novel(novel)
        if not has_usable_novel_ai_context(novel, novel_context):
            return jsonify({'success': False, 'message': '请先填写书名，或提供可读取的 TXT/EPUB 文件'}), 400
```

Replace:

```python
        messages = build_character_analysis_messages(novel, content_excerpt)
```

with:

```python
        messages = build_character_analysis_messages(novel, novel_context)
```

Replace every `source_excerpt_chars=len(content_excerpt)` in this route with:

```python
source_excerpt_chars=novel_context['included_chars']
```

Replace:

```python
            analysis['used_excerpt'] = bool(content_excerpt)
```

with:

```python
            analysis['used_excerpt'] = bool(novel_context.get('content_text'))
            analysis['context'] = summarize_novel_ai_context(novel_context)
```

- [ ] **Step 8: Migrate setting analysis route**

Apply the same replacements in `analyze_novel_settings`:

```python
        novel_context = build_ai_context_for_novel(novel)
        if not has_usable_novel_ai_context(novel, novel_context):
            return jsonify({'success': False, 'message': '请先填写书名，或提供可读取的 TXT/EPUB 文件'}), 400
```

```python
        messages = build_setting_analysis_messages(novel, novel_context)
```

Use `source_excerpt_chars=novel_context['included_chars']` in success and failure paths.

Set the success response additions:

```python
            analysis['used_excerpt'] = bool(novel_context.get('content_text'))
            analysis['context'] = summarize_novel_ai_context(novel_context)
```

- [ ] **Step 9: Migrate writing-style analysis route**

Apply the same replacements in `analyze_novel_writing_style`:

```python
        novel_context = build_ai_context_for_novel(novel)
        if not has_usable_novel_ai_context(novel, novel_context):
            return jsonify({'success': False, 'message': '请先填写书名，或提供可读取的 TXT/EPUB 文件'}), 400
```

```python
        messages = build_writing_style_analysis_messages(novel, novel_context)
```

Use `source_excerpt_chars=novel_context['included_chars']` in success and failure paths.

Set the success response additions:

```python
            analysis['used_excerpt'] = bool(novel_context.get('content_text'))
            analysis['context'] = summarize_novel_ai_context(novel_context)
```

- [ ] **Step 10: Run the migrated analysis tests and context tests**

Run:

```powershell
python tests\reader_ai_context.test.py
python tests\character_analysis.test.py
python tests\novel_setting_analysis.test.py
python tests\writing_style_analysis.test.py
```

Expected: all tests pass.

- [ ] **Step 11: Commit the analysis migration**

```powershell
git add ai_routes.py tests\character_analysis.test.py tests\novel_setting_analysis.test.py tests\writing_style_analysis.test.py
git commit -m "feat: use whole-novel context for analysis"
```

## Task 3: Reader Assistant Backend API

**Files:**
- Modify: `ai_routes.py`
- Create: `tests/reader_ai_assistant.test.py`

- [ ] **Step 1: Write failing reader assistant route tests**

Create `tests/reader_ai_assistant.test.py` with this content:

```python
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import ai_routes
import app as novel_app


class FakeReaderAssistantClient:
    def __init__(self):
        self.messages = None

    def chat(self, messages, stream=False):
        self.messages = messages
        return 'The answer uses the current novel context.'


class ReaderAIAssistantTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_database = novel_app.DATABASE
        self.original_testing = novel_app.app.config.get('TESTING')
        self.original_get_ai_client = ai_routes.get_ai_client
        novel_app.DATABASE = os.path.join(self.tmpdir.name, 'test-novels.db')
        novel_app.app.config['TESTING'] = True
        novel_app.init_db()

        self.book_path = Path(self.tmpdir.name) / 'reader-assistant.txt'
        self.book_path.write_text(
            'Chapter 1\nOpening reader clue.\n'
            + ('reader filler text\n' * 900)
            + 'Chapter 2\nLate reader assistant context marker.\n',
            encoding='utf-8'
        )

        conn = sqlite3.connect(novel_app.DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO novels (title, author, description, file_path, status) VALUES (?, ?, ?, ?, ?)',
            ('Reader Assistant Book', 'Assistant Author', 'A book for reader assistant tests.', str(self.book_path), 1),
        )
        self.novel_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.fake_client = FakeReaderAssistantClient()
        ai_routes.get_ai_client = lambda: self.fake_client
        self.client = novel_app.app.test_client()

    def tearDown(self):
        novel_app.DATABASE = self.original_database
        novel_app.app.config['TESTING'] = self.original_testing
        ai_routes.get_ai_client = self.original_get_ai_client
        self.tmpdir.cleanup()

    def test_reader_assistant_answers_with_novel_and_current_chapter_context(self):
        response = self.client.post(
            f'/api/ai/novels/{self.novel_id}/reader-assistant',
            json={
                'question': 'What does the late marker imply?',
                'chapter_index': 1,
                'chapter_title': 'Chapter 2',
                'conversation': [
                    {'role': 'user', 'content': 'Summarize the clue.'},
                    {'role': 'assistant', 'content': 'The clue appears late.'},
                ],
            },
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['data']['answer'], 'The answer uses the current novel context.')
        self.assertIn('context', payload['data'])
        self.assertIn('Late reader assistant context marker.', self.fake_client.messages[1]['content'])
        self.assertIn('Current chapter: Chapter 2', self.fake_client.messages[-1]['content'])
        self.assertIn('What does the late marker imply?', self.fake_client.messages[-1]['content'])

    def test_reader_assistant_rejects_empty_question(self):
        response = self.client.post(
            f'/api/ai/novels/{self.novel_id}/reader-assistant',
            json={'question': '   '},
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload['success'])

    def test_reader_assistant_requires_ai_client(self):
        ai_routes.get_ai_client = lambda: None

        response = self.client.post(
            f'/api/ai/novels/{self.novel_id}/reader-assistant',
            json={'question': 'Can you answer?'},
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload['success'])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the reader assistant route tests and verify they fail**

Run:

```powershell
python tests\reader_ai_assistant.test.py
```

Expected: success test returns `404` because `/api/ai/novels/<novel_id>/reader-assistant` does not exist yet.

- [ ] **Step 3: Add reader assistant message helpers**

Inside `register_ai_routes`, after `has_usable_novel_ai_context`, add:

```python
    READER_ASSISTANT_QUESTION_MAX_CHARS = 2000
    READER_ASSISTANT_HISTORY_MAX_MESSAGES = 6
    READER_ASSISTANT_HISTORY_MAX_CHARS = 1200


    def normalize_reader_assistant_question(value):
        return re.sub(r'\s+', ' ', str(value or '')).strip()[:READER_ASSISTANT_QUESTION_MAX_CHARS]


    def normalize_reader_assistant_history(items):
        normalized = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            role = item.get('role')
            if role not in {'user', 'assistant'}:
                continue
            content = re.sub(r'\s+', ' ', str(item.get('content') or '')).strip()
            if not content:
                continue
            normalized.append({'role': role, 'content': content[:READER_ASSISTANT_HISTORY_MAX_CHARS]})
        return normalized[-READER_ASSISTANT_HISTORY_MAX_MESSAGES:]


    def build_reader_assistant_messages(novel_context, *, question, chapter_index=None, chapter_title='', conversation=None):
        messages = [
            {
                'role': 'system',
                'content': (
                    '你是阅读器内的小说 AI 助手。只根据当前提供的小说上下文回答。'
                    '如果上下文无法确认答案，请直接说明无法确认，不要编造剧情、人物关系或结局。'
                ),
            },
            {
                'role': 'user',
                'content': novel_context.get('context_text') or 'Novel content context: Not available.',
            },
        ]
        messages.extend(normalize_reader_assistant_history(conversation))

        chapter_line = ''
        if chapter_index is not None or chapter_title:
            chapter_label = chapter_title or f'Chapter {chapter_index + 1}'
            chapter_line = f'Current chapter: {chapter_label}\n'

        messages.append({
            'role': 'user',
            'content': f"{chapter_line}Question: {question}",
        })
        return messages
```

- [ ] **Step 4: Add the reader assistant route**

Inside `register_ai_routes`, place this route after `/api/ai/chat` and before the analysis read routes:

```python
    @app.route('/api/ai/novels/<int:novel_id>/reader-assistant', methods=['POST'])
    def reader_assistant_chat(novel_id):
        data = request.get_json(silent=True) or {}
        question = normalize_reader_assistant_question(data.get('question'))
        if not question:
            return jsonify({'success': False, 'message': '问题不能为空'}), 400

        novel = get_novel_detail_record(novel_id)
        if not novel:
            return jsonify({'success': False, 'message': '小说不存在'}), 404

        client = get_ai_client()
        if not client:
            return jsonify({'success': False, 'message': '请先在 AI 配置中激活可用模型'}), 400

        try:
            chapter_index = data.get('chapter_index')
            chapter_index = int(chapter_index) if chapter_index is not None else None
        except (TypeError, ValueError):
            chapter_index = None

        novel_context = build_ai_context_for_novel(novel, focus_chapter_index=chapter_index)
        messages = build_reader_assistant_messages(
            novel_context,
            question=question,
            chapter_index=chapter_index,
            chapter_title=str(data.get('chapter_title') or '').strip(),
            conversation=data.get('conversation') if isinstance(data.get('conversation'), list) else [],
        )

        try:
            answer = client.chat(messages, stream=False)
            return jsonify({
                'success': True,
                'data': {
                    'answer': answer,
                    'context': summarize_novel_ai_context(novel_context),
                },
            })
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
```

- [ ] **Step 5: Run backend assistant tests and analysis tests**

Run:

```powershell
python tests\reader_ai_assistant.test.py
python tests\reader_ai_context.test.py
python tests\character_analysis.test.py
python tests\novel_setting_analysis.test.py
python tests\writing_style_analysis.test.py
```

Expected: all tests pass.

- [ ] **Step 6: Commit the reader assistant API**

```powershell
git add ai_routes.py tests\reader_ai_assistant.test.py
git commit -m "feat: add reader ai assistant api"
```

## Task 4: Reader Assistant Frontend

**Files:**
- Create: `tests/reader-ai-assistant-ui.test.js`
- Modify: `templates/index.html`
- Modify: `static/js/reader.js`
- Modify: `static/js/app.js`
- Modify: `static/css/reader.css`

- [ ] **Step 1: Write the failing static UI test**

Create `tests/reader-ai-assistant-ui.test.js` with this content:

```javascript
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

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
assert.match(readerJs, /\/api\/ai\/novels\/\$\{readerState\.novelId\}\/reader-assistant/, 'reader should call the reader assistant API');
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

console.log('reader AI assistant UI checks passed');
```

- [ ] **Step 2: Run the static UI test and verify it fails**

Run:

```powershell
node tests\reader-ai-assistant-ui.test.js
```

Expected: assertion failure for missing `reader-ai-toggle`.

- [ ] **Step 3: Add the reader toolbar button and panel markup**

In `templates/index.html`, inside `.reader-controls`, insert this button after `reader-search-toggle`:

```html
                    <button class="btn-icon" id="reader-ai-toggle" title="AI 助手" aria-expanded="false">
                        <i class="fas fa-robot"></i>
                    </button>
```

Inside `.reader-body`, after the existing `.reader-main` closing `</div>` and before the `.reader-body` closing `</div>`, insert:

```html
                <aside class="reader-ai-panel hidden" id="reader-ai-panel" aria-label="AI 助手">
                    <div class="reader-ai-header">
                        <div>
                            <span class="reader-ai-kicker">AI 助手</span>
                            <strong>当前小说上下文</strong>
                        </div>
                        <button class="btn-icon" id="reader-ai-close" title="关闭 AI 助手">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="reader-ai-status" id="reader-ai-status">打开后将以当前小说为上下文回答</div>
                    <div class="reader-ai-messages" id="reader-ai-messages"></div>
                    <div class="reader-ai-error hidden" id="reader-ai-error"></div>
                    <div class="reader-ai-compose">
                        <textarea id="reader-ai-input" rows="3" aria-label="向 AI 询问这本小说" autocomplete="off"></textarea>
                        <div class="reader-ai-actions">
                            <button class="btn btn-secondary" id="reader-ai-clear" type="button">
                                <i class="fas fa-eraser"></i>
                                清空
                            </button>
                            <button class="btn btn-primary" id="reader-ai-send" type="button">
                                <i class="fas fa-paper-plane"></i>
                                发送
                            </button>
                        </div>
                    </div>
                </aside>
```

- [ ] **Step 4: Add reader assistant state**

In `static/js/reader.js`, add these fields to `readerState`:

```javascript
    isAssistantOpen: false,
    assistantMessages: [],
    assistantSending: false,
    assistantContext: null,
    assistantError: ''
```

In `openReader(novelId)`, after resetting search state, add:

```javascript
    resetReaderAssistantState();
```

- [ ] **Step 5: Add reader assistant JavaScript functions**

In `static/js/reader.js`, before `toggleReaderImmersiveMode`, add:

```javascript
function formatReaderAssistantContextStatus(context) {
    if (!context) return '打开后将以当前小说为上下文回答';
    if (context.is_full_text) {
        return `已使用完整小说上下文（${context.included_chars || 0} 字）`;
    }
    return `小说较长，已使用全书抽样上下文（${context.segment_count || 0} 段 / ${context.included_chars || 0} 字）`;
}

function resetReaderAssistantState() {
    readerState.isAssistantOpen = false;
    readerState.assistantMessages = [];
    readerState.assistantSending = false;
    readerState.assistantContext = null;
    readerState.assistantError = '';
    renderReaderAssistantPanel();
}

function renderReaderAssistantMessages() {
    const container = document.getElementById('reader-ai-messages');
    if (!container) return;

    if (!readerState.assistantMessages.length) {
        container.innerHTML = '<div class="reader-ai-empty">可以询问剧情、人物动机、设定或当前章节疑问。</div>';
        return;
    }

    container.innerHTML = readerState.assistantMessages.map(message => `
        <div class="reader-ai-message ${message.role}">
            <div class="reader-ai-message-role">${message.role === 'user' ? '你' : 'AI'}</div>
            <div class="reader-ai-message-content">${escapeHtml(message.content)}</div>
        </div>
    `).join('');
    container.scrollTop = container.scrollHeight;
}

function renderReaderAssistantPanel() {
    const panel = document.getElementById('reader-ai-panel');
    const toggle = document.getElementById('reader-ai-toggle');
    const status = document.getElementById('reader-ai-status');
    const error = document.getElementById('reader-ai-error');
    const send = document.getElementById('reader-ai-send');
    const input = document.getElementById('reader-ai-input');

    if (panel) panel.classList.toggle('hidden', !readerState.isAssistantOpen);
    if (toggle) toggle.setAttribute('aria-expanded', String(readerState.isAssistantOpen));
    if (status) status.textContent = formatReaderAssistantContextStatus(readerState.assistantContext);
    if (send) send.disabled = readerState.assistantSending;
    if (input) input.disabled = readerState.assistantSending;

    if (error) {
        error.textContent = readerState.assistantError;
        error.classList.toggle('hidden', !readerState.assistantError);
    }

    renderReaderAssistantMessages();
}

function openReaderAssistantPanel() {
    readerState.isAssistantOpen = true;
    closeReaderSearchPanel();
    closeReaderSettingsPanel();
    renderReaderAssistantPanel();
    document.getElementById('reader-ai-input')?.focus();
}

function closeReaderAssistantPanel() {
    readerState.isAssistantOpen = false;
    renderReaderAssistantPanel();
}

function toggleReaderAssistantPanel() {
    if (readerState.isAssistantOpen) {
        closeReaderAssistantPanel();
    } else {
        openReaderAssistantPanel();
    }
}

function clearReaderAssistantMessages() {
    readerState.assistantMessages = [];
    readerState.assistantError = '';
    renderReaderAssistantPanel();
    document.getElementById('reader-ai-input')?.focus();
}

function buildReaderAssistantConversationPayload() {
    return readerState.assistantMessages
        .filter(message => ['user', 'assistant'].includes(message.role))
        .slice(-6)
        .map(message => ({
            role: message.role,
            content: message.content
        }));
}

async function sendReaderAssistantQuestion() {
    const input = document.getElementById('reader-ai-input');
    const question = (input?.value || '').trim();
    if (!question || readerState.assistantSending || !readerState.novelId) return;

    readerState.assistantMessages.push({ role: 'user', content: question });
    readerState.assistantSending = true;
    readerState.assistantError = '';
    if (input) input.value = '';
    renderReaderAssistantPanel();

    try {
        const res = await api.post(`/api/ai/novels/${readerState.novelId}/reader-assistant`, {
            question,
            chapter_index: readerState.currentChapter,
            chapter_title: document.getElementById('reader-chapter-title')?.textContent || '',
            conversation: buildReaderAssistantConversationPayload()
        });

        if (res.success) {
            readerState.assistantContext = res.data.context || null;
            readerState.assistantMessages.push({
                role: 'assistant',
                content: res.data.answer || 'AI 未返回内容'
            });
        } else {
            readerState.assistantError = res.message || 'AI 助手请求失败';
        }
    } catch (err) {
        readerState.assistantError = err.message || 'AI 助手请求失败';
    } finally {
        readerState.assistantSending = false;
        renderReaderAssistantPanel();
        document.getElementById('reader-ai-input')?.focus();
    }
}
```

In `setReaderImmersiveMode(enabled)`, inside the `if (readerState.isImmersive)` block, add:

```javascript
        closeReaderAssistantPanel();
```

- [ ] **Step 6: Bind reader assistant events**

In `static/js/app.js`, after the existing reader search bindings, add:

```javascript
    document.getElementById('reader-ai-toggle').addEventListener('click', toggleReaderAssistantPanel);
    document.getElementById('reader-ai-close').addEventListener('click', closeReaderAssistantPanel);
    document.getElementById('reader-ai-send').addEventListener('click', sendReaderAssistantQuestion);
    document.getElementById('reader-ai-clear').addEventListener('click', clearReaderAssistantMessages);
    document.getElementById('reader-ai-input').addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            sendReaderAssistantQuestion();
        }
    });
```

- [ ] **Step 7: Add reader assistant CSS**

In `static/css/reader.css`, after `.reader-main`, add:

```css
.reader-ai-panel {
    flex: 0 0 360px;
    width: 360px;
    border-left: 1px solid var(--border-color);
    background: var(--card-bg);
    display: flex;
    flex-direction: column;
    min-width: 0;
}

.reader-ai-panel.hidden {
    display: none;
}

.reader-ai-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 16px;
    border-bottom: 1px solid var(--border-color);
}

.reader-ai-kicker {
    display: block;
    margin-bottom: 2px;
    font-size: 12px;
    color: var(--text-secondary);
}

.reader-ai-status {
    padding: 10px 16px;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-secondary);
    font-size: 13px;
    line-height: 1.5;
}

.reader-ai-messages {
    flex: 1;
    overflow-y: auto;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.reader-ai-empty {
    color: var(--text-secondary);
    font-size: 14px;
    line-height: 1.6;
}

.reader-ai-message {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-width: 100%;
}

.reader-ai-message-role {
    color: var(--text-secondary);
    font-size: 12px;
}

.reader-ai-message-content {
    border-radius: var(--radius);
    padding: 10px 12px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
}

.reader-ai-message.user .reader-ai-message-content {
    align-self: flex-end;
    max-width: 88%;
    background: var(--primary-color);
    color: white;
}

.reader-ai-message.assistant .reader-ai-message-content {
    background: var(--bg-color);
    color: var(--text-primary);
}

.reader-ai-error {
    margin: 0 16px 12px;
    padding: 10px 12px;
    border-radius: var(--radius);
    background: rgba(239, 68, 68, 0.1);
    color: #b91c1c;
    font-size: 13px;
    line-height: 1.5;
}

.reader-ai-error.hidden {
    display: none;
}

.reader-ai-compose {
    padding: 12px 16px 16px;
    border-top: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.reader-ai-compose textarea {
    width: 100%;
    min-height: 84px;
    resize: vertical;
    border: 1px solid var(--border-color);
    border-radius: var(--radius);
    padding: 10px 12px;
    color: var(--text-primary);
    background: var(--card-bg);
    font: inherit;
    line-height: 1.5;
}

.reader-ai-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
}

.reader-modal.dark-theme .reader-ai-panel,
.reader-modal.dark-theme .reader-ai-compose textarea {
    background: #1f1f1f;
    border-color: #333;
}

.reader-modal.dark-theme .reader-ai-message.assistant .reader-ai-message-content {
    background: #242424;
}
```

Inside the existing `@media (max-width: 768px)` block, add:

```css
    .reader-ai-panel {
        position: fixed;
        top: 60px;
        right: 0;
        bottom: 60px;
        z-index: 11;
        width: min(100vw, 380px);
        box-shadow: -18px 0 40px rgba(15, 23, 42, 0.18);
    }
```

- [ ] **Step 8: Run frontend static tests**

Run:

```powershell
node tests\reader-ai-assistant-ui.test.js
node tests\reader-experience-ui.test.js
node tests\reader-progress-ui.test.js
```

Expected: all three Node tests pass.

- [ ] **Step 9: Run backend regression tests touched by this feature**

Run:

```powershell
python tests\reader_ai_context.test.py
python tests\reader_ai_assistant.test.py
python tests\character_analysis.test.py
python tests\novel_setting_analysis.test.py
python tests\writing_style_analysis.test.py
```

Expected: all five Python test files pass.

- [ ] **Step 10: Commit the frontend assistant**

```powershell
git add templates\index.html static\js\reader.js static\js\app.js static\css\reader.css tests\reader-ai-assistant-ui.test.js
git commit -m "feat: add reader ai assistant panel"
```

## Task 5: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Check git status**

Run:

```powershell
git status --short
```

Expected: only pre-existing unrelated untracked files remain, or a clean worktree if those files were handled outside this task.

- [ ] **Step 2: Run focused backend and frontend verification**

Run:

```powershell
python tests\reader_ai_context.test.py
python tests\reader_ai_assistant.test.py
python tests\character_analysis.test.py
python tests\novel_setting_analysis.test.py
python tests\writing_style_analysis.test.py
python tests\reader_progress.test.py
python tests\reader_epub.test.py
node tests\reader-ai-assistant-ui.test.js
node tests\reader-experience-ui.test.js
node tests\reader-progress-ui.test.js
node tests\frontend-split.test.js
```

Expected: every command exits with code 0.

- [ ] **Step 3: Start the app for manual browser verification**

Run:

```powershell
python app.py
```

Expected: Flask starts on `http://localhost:5000`.

- [ ] **Step 4: Use the in-app browser to verify the reader assistant layout**

Open `http://localhost:5000`, open any readable novel, click the reader AI assistant button, and verify:

- The AI panel opens on the right on desktop.
- The input, send, clear, close, and status controls are visible.
- The reading text and bottom navigation do not overlap the assistant panel.
- Entering immersive mode closes the assistant panel.
- If no active AI config exists, sending a question shows a clear error in the panel.

- [ ] **Step 5: Stop the app and commit any small verification fixes**

If verification required fixes, run the focused tests again and commit:

```powershell
git add ai_context.py ai_routes.py templates\index.html static\js\reader.js static\js\app.js static\css\reader.css tests\reader_ai_context.test.py tests\reader_ai_assistant.test.py tests\reader-ai-assistant-ui.test.js tests\character_analysis.test.py tests\novel_setting_analysis.test.py tests\writing_style_analysis.test.py
git commit -m "fix: polish reader ai assistant verification"
```

Expected: a commit is created only if verification fixes were needed.

## Self-Review Notes

- Spec coverage: Tasks cover shared whole-novel context, short full-text mode, long sampled mode, focus chapter priority, migration of character/setting/writing-style analysis, reader assistant backend API, reader assistant frontend UI, and verification.
- Scope: This plan does not add vector search, persistent chat history, or multi-pass deep analysis, matching the approved spec.
- Type consistency: The context object uses `context_text`, `content_text`, `is_full_text`, `is_truncated`, `source_chars`, `included_chars`, `chapter_count`, and `segments` consistently across helper, routes, tests, and frontend response status.
- Test order: Each behavior has a failing test before production code changes.
