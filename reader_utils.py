"""Reader helpers for text encoding, chapter parsing, and parsed file caching."""
import io
import os
import re
from collections import OrderedDict


CHAPTER_PATTERNS = [
    r'^(第[\s]*[零一二三四五六七八九十百千万\d]+[\s]*[章回节集卷])',
    r'^(Chapter[\s]+\d+)',
    r'^(\d+[\.\s、]+[^\n]+)',
    r'^(第[\s]*[零一二三四五六七八九十百千万\d]+[\s]*[章回节集卷][：:].+)',
    r'^[【\[](第[\s]*[零一二三四五六七八九十百千万\d]+[\s]*[章回节集卷])[】\]]',
]

CHAPTER_REGEX = re.compile('|'.join(f'({pattern})' for pattern in CHAPTER_PATTERNS), re.IGNORECASE)
ENCODING_SAMPLE_SIZE = 256 * 1024
READER_FILE_CACHE_MAX_ITEMS = 6
_READER_FILE_CACHE = OrderedDict()


def detect_encoding(file_path, sample_size=ENCODING_SAMPLE_SIZE):
    """Detect the likely text encoding from a bounded byte sample."""
    import chardet
    with open(file_path, 'rb') as handle:
        raw_data = handle.read(sample_size)

    if not raw_data:
        return 'utf-8'

    if raw_data.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'

    try:
        raw_data.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        pass

    result = chardet.detect(raw_data)
    return result['encoding'] or 'utf-8'


def parse_chapters(content):
    """Parse text into chapters while avoiding repeated regex compilation."""
    chapters = []
    current_chapter = None
    current_content = []

    for line_num, line in enumerate(io.StringIO(content)):
        line = line.strip()
        if not line:
            continue

        match = CHAPTER_REGEX.match(line)
        if match:
            if current_chapter:
                current_chapter['content'] = '\n'.join(current_content)
                chapters.append(current_chapter)

            current_chapter = {
                'title': line,
                'content': '',
                'line_num': line_num
            }
            current_content = []
        elif current_chapter:
            current_content.append(line)

    if current_chapter:
        current_chapter['content'] = '\n'.join(current_content)
        chapters.append(current_chapter)

    if not chapters and content.strip():
        chapters = [{
            'title': '全文',
            'content': content.strip(),
            'line_num': 0
        }]

    return chapters


def _reader_file_signature(file_path):
    stat_result = os.stat(file_path)
    return (
        os.path.abspath(file_path),
        stat_result.st_size,
        getattr(stat_result, 'st_mtime_ns', int(stat_result.st_mtime * 1_000_000_000)),
    )


def clear_reader_file_cache():
    """Clear parsed reader file cache. Intended for tests and explicit maintenance."""
    _READER_FILE_CACHE.clear()


def get_cached_reader_file(file_path):
    """Read and parse a text novel once, then reuse it until the file changes."""
    signature = _reader_file_signature(file_path)
    cache_key = signature[0]
    cached = _READER_FILE_CACHE.get(cache_key)

    if cached and cached.get('signature') == signature:
        _READER_FILE_CACHE.move_to_end(cache_key)
        return cached

    encoding = detect_encoding(file_path)
    with open(file_path, 'r', encoding=encoding, errors='ignore') as handle:
        content = handle.read()

    parsed = {
        'signature': signature,
        'encoding': encoding,
        'total_chars': len(content),
        'chapters': parse_chapters(content),
    }

    _READER_FILE_CACHE[cache_key] = parsed
    _READER_FILE_CACHE.move_to_end(cache_key)

    while len(_READER_FILE_CACHE) > READER_FILE_CACHE_MAX_ITEMS:
        _READER_FILE_CACHE.popitem(last=False)

    return parsed
