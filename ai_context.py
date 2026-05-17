"""Helpers for building whole-novel AI context."""
from reader_utils import get_cached_reader_file


DEFAULT_AI_CONTEXT_CHAR_BUDGET = 60000
MAX_SAMPLED_CONTEXT_SEGMENTS = 10
MIN_SAMPLED_SEGMENT_CHARS = 800
MAX_METADATA_FIELD_CHARS = 500
MAX_METADATA_TAGS = 12
MAX_METADATA_TAG_CHARS = 80
MAX_METADATA_TEXT_CHARS = 1400


def _clean_text(value):
    return str(value or '').strip()


def _truncate_text(value, max_chars):
    text = _clean_text(value)
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[:max_chars - 3].rstrip() + '...'


def _tag_names(novel):
    names = []
    for item in novel.get('tags') or []:
        if isinstance(item, dict):
            name = _truncate_text(item.get('name'), MAX_METADATA_TAG_CHARS)
        else:
            name = _truncate_text(item, MAX_METADATA_TAG_CHARS)
        if name:
            names.append(name)
        if len(names) >= MAX_METADATA_TAGS:
            break
    return names


def build_novel_metadata_text(novel):
    lines = [
        f"Title: {_truncate_text(novel.get('title'), MAX_METADATA_FIELD_CHARS) or 'Not provided'}",
        f"Author: {_truncate_text(novel.get('author'), MAX_METADATA_FIELD_CHARS) or 'Not provided'}",
        f"Description: {_truncate_text(novel.get('description'), MAX_METADATA_FIELD_CHARS) or 'Not provided'}",
    ]
    category = _truncate_text(novel.get('category_name'), MAX_METADATA_FIELD_CHARS)
    if category:
        lines.append(f"Category: {category}")
    tags = _tag_names(novel)
    if tags:
        lines.append(f"Tags: {', '.join(tags)}")
    return _truncate_text('\n'.join(lines), MAX_METADATA_TEXT_CHARS)


def _normalize_char_budget(char_budget):
    if char_budget is None:
        return DEFAULT_AI_CONTEXT_CHAR_BUDGET
    try:
        budget = int(char_budget)
    except (TypeError, ValueError):
        return DEFAULT_AI_CONTEXT_CHAR_BUDGET
    if budget > 0:
        return budget
    return DEFAULT_AI_CONTEXT_CHAR_BUDGET


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

    denominator = max(target_count - 1, 1)
    for position in range(target_count):
        indices.add(round((chapter_count - 1) * position / denominator))

    while len(indices) > target_count:
        removable = [index for index in indices if index not in {0, chapter_count - 1, focus_chapter_index}]
        if not removable:
            break
        indices.remove(min(removable, key=lambda index: abs(index - focus_chapter_index)))

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
    if index == chapter_count - 1:
        head_budget = max(1, per_segment_budget // 2)
        tail_budget = max(1, per_segment_budget - head_budget - 6)
        return f"{text[:head_budget].strip()}\n...\n{text[-tail_budget:].strip()}"
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
            'preserve_tail': index == len(chapters) - 1,
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


def _segment_header(segment):
    return f"[{segment['label']} | Chapter {segment['chapter_index'] + 1}] {segment['chapter_title']}\n"


def _trim_segment_text(segment, available):
    text = segment['text'].strip()
    if available <= 0:
        return ''
    if len(text) <= available:
        return text
    if segment.get('preserve_tail'):
        if available <= 10:
            return text[-available:].strip()
        head_budget = max(1, available // 2)
        tail_budget = max(1, available - head_budget - 5)
        return f"{text[:head_budget].strip()}\n...\n{text[-tail_budget:].strip()}"
    return text[:available].strip()


def _trim_segments_to_budget(segments, char_budget):
    content = _segments_to_text(segments)
    if len(content) <= char_budget:
        return segments, content

    retained_segments = list(segments)
    headers_len = sum(len(_segment_header(segment)) for segment in retained_segments)
    separators_len = max(0, len(retained_segments) - 1) * 2
    while retained_segments and headers_len + separators_len + len(retained_segments) > char_budget:
        removed = retained_segments.pop()
        headers_len -= len(_segment_header(removed))
        separators_len = max(0, len(retained_segments) - 1) * 2

    if retained_segments and headers_len + separators_len < char_budget:
        text_budget = char_budget - headers_len - separators_len
        per_segment_budget = text_budget // len(retained_segments)
        extra_chars = text_budget % len(retained_segments)
        trimmed_segments = []
        for index, segment in enumerate(retained_segments):
            trimmed = dict(segment)
            available = per_segment_budget + (1 if index < extra_chars else 0)
            trimmed['text'] = _trim_segment_text(segment, available)
            if trimmed['text']:
                trimmed_segments.append(trimmed)
        return trimmed_segments, _segments_to_text(trimmed_segments)

    trimmed_segments = []
    remaining = char_budget
    for segment in segments:
        header = _segment_header(segment)
        available = remaining - len(header) - 2
        if available <= 0:
            break
        trimmed = dict(segment)
        trimmed['text'] = _trim_segment_text(segment, available)
        if trimmed['text']:
            trimmed_segments.append(trimmed)
            remaining -= len(header) + len(trimmed['text']) + 2
    return trimmed_segments, _segments_to_text(trimmed_segments)


def _prioritize_segments_for_budget(segments, focus_chapter_index):
    if not isinstance(focus_chapter_index, int):
        return segments
    return sorted(
        segments,
        key=lambda segment: (
            segment['chapter_index'] != focus_chapter_index,
            segment['chapter_index'],
        ),
    )


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
    safe_budget = _normalize_char_budget(char_budget)

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
        sampled = _prioritize_segments_for_budget(sampled, focus_chapter_index)
        segments, content_text = _trim_segments_to_budget(sampled, safe_budget)
        is_full_text = False

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
        'is_truncated': False if is_full_text else source_chars > 0,
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
