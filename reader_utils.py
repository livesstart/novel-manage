"""Reader helpers for text encoding, chapter parsing, and parsed file caching."""
import html as html_lib
import io
import os
import posixpath
import re
import zipfile
from collections import OrderedDict
from html.parser import HTMLParser
from urllib.parse import unquote, urldefrag
import xml.etree.ElementTree as ET


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
EPUB_CONTAINER_PATH = 'META-INF/container.xml'
EPUB_HTML_EXTENSIONS = {'.xhtml', '.html', '.htm'}
EPUB_HTML_MEDIA_TYPES = {'application/xhtml+xml', 'text/html'}
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


class _EpubHtmlTextParser(HTMLParser):
    """Extract readable text and a chapter title from EPUB HTML content."""

    BLOCK_TAGS = {
        'address', 'article', 'aside', 'blockquote', 'br', 'dd', 'div', 'dl',
        'dt', 'figcaption', 'figure', 'footer', 'h1', 'h2', 'h3', 'h4', 'h5',
        'h6', 'header', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'pre', 'section',
        'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr', 'ul'
    }
    TITLE_TAGS = {'title', 'h1', 'h2', 'h3'}
    SKIP_TAGS = {'script', 'style'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines = []
        self.current_line = []
        self.in_body = False
        self.skip_depth = 0
        self.active_title_tag = None
        self.active_title_parts = []
        self.document_title = ''
        self.first_heading = ''

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'body':
            self.in_body = True
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if tag in self.TITLE_TAGS:
            self.active_title_tag = tag
            self.active_title_parts = []
        if self.in_body and tag in self.BLOCK_TAGS:
            self._flush_line()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if tag == self.active_title_tag:
            title = self._normalize_text(' '.join(self.active_title_parts))
            if title:
                if tag == 'title' and not self.document_title:
                    self.document_title = title
                elif tag != 'title' and not self.first_heading:
                    self.first_heading = title
            self.active_title_tag = None
            self.active_title_parts = []
        if self.in_body and tag in self.BLOCK_TAGS:
            self._flush_line()
        if tag == 'body':
            self._flush_line()
            self.in_body = False

    def handle_data(self, data):
        if self.skip_depth:
            return

        text = self._normalize_text(html_lib.unescape(data))
        if not text:
            return

        if self.active_title_tag:
            self.active_title_parts.append(text)

        if self.in_body:
            self._append_text(text)

    def _append_text(self, text):
        if self.current_line:
            self.current_line.append(' ')
        self.current_line.append(text)

    def _flush_line(self):
        line = self._normalize_text(''.join(self.current_line))
        if line:
            self.lines.append(line)
        self.current_line = []

    def get_title(self):
        return self.first_heading or self.document_title

    def get_text(self, title=''):
        self._flush_line()
        lines = list(self.lines)
        if title and lines and lines[0] == title:
            lines = lines[1:]
        return '\n'.join(lines).strip()

    @staticmethod
    def _normalize_text(text):
        return ' '.join((text or '').split())


def _xml_local_name(tag):
    return tag.rsplit('}', 1)[-1]


def _decode_epub_text(raw_data):
    for encoding in ('utf-8-sig', 'utf-16', 'utf-16le', 'utf-16be'):
        try:
            return raw_data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_data.decode('utf-8', errors='ignore')


def _normalize_epub_text(text):
    return ' '.join((text or '').split())


def _find_epub_rootfile_path(archive):
    try:
        container_xml = archive.read(EPUB_CONTAINER_PATH)
    except KeyError as exc:
        raise ValueError('EPUB missing META-INF/container.xml') from exc

    root = ET.fromstring(container_xml)
    for element in root.iter():
        if _xml_local_name(element.tag) == 'rootfile':
            full_path = (element.attrib.get('full-path') or '').strip()
            if full_path:
                return full_path

    raise ValueError('EPUB does not declare an OPF package file')


def _resolve_epub_href(opf_path, href):
    opf_dir = posixpath.dirname(opf_path)
    resolved = posixpath.normpath(posixpath.join(opf_dir, unquote(href or '')))
    return resolved.lstrip('/')


def _resolve_epub_reference(base_path, href):
    href_path, fragment = urldefrag(href or '')
    base_dir = posixpath.dirname(base_path)
    resolved = posixpath.normpath(posixpath.join(base_dir, unquote(href_path)))
    return resolved.lstrip('/'), unquote(fragment or '').strip()


def _is_epub_html_item(item):
    href = item.get('href') or ''
    href_path, _ = urldefrag(href)
    extension = posixpath.splitext(href_path)[1].lower()
    return item.get('media_type') in EPUB_HTML_MEDIA_TYPES or extension in EPUB_HTML_EXTENSIONS


def _parse_epub_opf(archive, opf_path):
    try:
        opf_xml = archive.read(opf_path)
    except KeyError as exc:
        raise ValueError('EPUB OPF package file is missing') from exc

    root = ET.fromstring(opf_xml)
    manifest = {}
    spine = []
    spine_toc_id = ''

    for element in root.iter():
        name = _xml_local_name(element.tag)
        if name == 'spine':
            spine_toc_id = element.attrib.get('toc') or ''
        elif name == 'item':
            item_id = element.attrib.get('id')
            href = element.attrib.get('href')
            if item_id and href:
                manifest[item_id] = {
                    'href': href,
                    'media_type': (element.attrib.get('media-type') or '').lower(),
                    'properties': (element.attrib.get('properties') or '').lower(),
                }
        elif name == 'itemref':
            idref = element.attrib.get('idref')
            if idref and element.attrib.get('linear', 'yes').lower() != 'no':
                spine.append(idref)

    html_paths = {
        _resolve_epub_href(opf_path, item['href'])
        for item in manifest.values()
        if _is_epub_html_item(item)
    }

    chapter_paths = []
    for idref in spine:
        item = manifest.get(idref)
        if not item:
            continue

        if not _is_epub_html_item(item):
            continue

        chapter_paths.append(_resolve_epub_href(opf_path, item['href']))

    toc_path = None
    toc_item = manifest.get(spine_toc_id)
    if toc_item:
        toc_path = _resolve_epub_href(opf_path, toc_item['href'])

    nav_paths = [
        _resolve_epub_href(opf_path, item['href'])
        for item in manifest.values()
        if 'nav' in item.get('properties', '').split()
    ]

    return {
        'spine_paths': chapter_paths,
        'toc_path': toc_path,
        'nav_paths': nav_paths,
        'html_paths': html_paths,
    }


def _make_epub_toc_ref(base_path, href, title, html_paths):
    path, fragment = _resolve_epub_reference(base_path, href)
    extension = posixpath.splitext(path)[1].lower()
    if path not in html_paths and extension not in EPUB_HTML_EXTENSIONS:
        return None

    return {
        'path': path,
        'fragment': fragment,
        'title': _normalize_epub_text(title),
    }


def _dedupe_epub_toc_refs(refs):
    deduped = []
    seen = set()
    for ref in refs:
        key = (ref['path'], ref['fragment'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def _direct_epub_children(element, child_name):
    return [child for child in list(element) if _xml_local_name(child.tag) == child_name]


def _epub_ncx_navpoint_label(nav_point):
    for label in _direct_epub_children(nav_point, 'navLabel'):
        parts = [
            text_node.text or ''
            for text_node in label.iter()
            if _xml_local_name(text_node.tag) == 'text'
        ]
        text = _normalize_epub_text(' '.join(parts))
        if text:
            return text
    return ''


def _epub_ncx_navpoint_src(nav_point):
    for content in _direct_epub_children(nav_point, 'content'):
        src = (content.attrib.get('src') or '').strip()
        if src:
            return src
    return ''


def _parse_epub_ncx_toc(archive, toc_path, html_paths):
    if not toc_path:
        return []

    try:
        root = ET.fromstring(archive.read(toc_path))
    except (KeyError, ET.ParseError):
        return []

    def visit_nav_point(nav_point):
        child_refs = []
        for child in _direct_epub_children(nav_point, 'navPoint'):
            child_refs.extend(visit_nav_point(child))
        if child_refs:
            return child_refs

        src = _epub_ncx_navpoint_src(nav_point)
        if not src:
            return []

        ref = _make_epub_toc_ref(
            toc_path,
            src,
            _epub_ncx_navpoint_label(nav_point),
            html_paths
        )
        return [ref] if ref else []

    refs = []
    for nav_map in root.iter():
        if _xml_local_name(nav_map.tag) != 'navMap':
            continue
        for nav_point in _direct_epub_children(nav_map, 'navPoint'):
            refs.extend(visit_nav_point(nav_point))

    return _dedupe_epub_toc_refs(refs)


def _is_epub_toc_nav(element):
    if _xml_local_name(element.tag) != 'nav':
        return False
    for key, value in element.attrib.items():
        if _xml_local_name(key) == 'type' and 'toc' in (value or '').lower().split():
            return True
    return False


def _parse_epub_nav_toc(archive, nav_path, html_paths):
    refs = []
    if not nav_path:
        return refs

    try:
        root = ET.fromstring(archive.read(nav_path))
    except (KeyError, ET.ParseError):
        return refs

    nav_roots = [element for element in root.iter() if _is_epub_toc_nav(element)]
    if not nav_roots:
        nav_roots = [root]

    for nav_root in nav_roots:
        for element in nav_root.iter():
            if _xml_local_name(element.tag) != 'a':
                continue
            href = (element.attrib.get('href') or '').strip()
            if not href:
                continue
            ref = _make_epub_toc_ref(nav_path, href, ''.join(element.itertext()), html_paths)
            if ref:
                refs.append(ref)

    return _dedupe_epub_toc_refs(refs)


def _parse_epub_toc_refs(archive, package_info):
    refs = _parse_epub_ncx_toc(
        archive,
        package_info.get('toc_path'),
        package_info.get('html_paths') or set()
    )
    if refs:
        return refs

    for nav_path in package_info.get('nav_paths') or []:
        refs = _parse_epub_nav_toc(archive, nav_path, package_info.get('html_paths') or set())
        if refs:
            return refs

    return []


def _find_html_fragment_offset(raw_html, fragment):
    if not fragment:
        return None

    escaped = re.escape(fragment)
    patterns = [
        rf'<[^>]+\s(?:id|name)\s*=\s*["\']{escaped}["\'][^>]*>',
        rf'<[^>]+\s(?:id|name)\s*=\s*{escaped}(?=[\s>/])[^>]*>',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_html, flags=re.IGNORECASE)
        if match:
            return match.start()
    return None


def _slice_epub_html_for_toc_ref(raw_html, current_ref, next_ref):
    start = _find_html_fragment_offset(raw_html, current_ref.get('fragment'))
    if start is None:
        start = 0

    end = None
    if next_ref and next_ref.get('path') == current_ref.get('path'):
        next_start = _find_html_fragment_offset(raw_html, next_ref.get('fragment'))
        if next_start is not None and next_start > start:
            end = next_start

    segment = raw_html[start:end]
    if current_ref.get('fragment'):
        return f'<body>{segment}</body>'
    return segment


def _extract_epub_html_chapter(raw_html, fallback_title):
    parser = _EpubHtmlTextParser()
    parser.feed(raw_html)
    parser.close()

    title = parser.get_title() or fallback_title
    content = parser.get_text(title)
    return title, content


def _read_epub_spine_chapters(archive, chapter_paths):
    chapters = []
    for index, chapter_path in enumerate(chapter_paths):
        try:
            raw_html = _decode_epub_text(archive.read(chapter_path))
        except KeyError:
            continue

        fallback_title = posixpath.splitext(posixpath.basename(chapter_path))[0] or f'Chapter {index + 1}'
        title, content = _extract_epub_html_chapter(raw_html, fallback_title)
        if not title and not content:
            continue

        chapters.append({
            'title': title or fallback_title,
            'content': content,
            'line_num': index
        })
    return chapters


def _read_epub_toc_chapters(archive, toc_refs):
    chapters = []
    html_cache = {}

    for index, ref in enumerate(toc_refs):
        chapter_path = ref['path']
        try:
            raw_html = html_cache[chapter_path]
        except KeyError:
            try:
                raw_html = _decode_epub_text(archive.read(chapter_path))
            except KeyError:
                continue
            html_cache[chapter_path] = raw_html

        next_ref = toc_refs[index + 1] if index + 1 < len(toc_refs) else None
        segment = _slice_epub_html_for_toc_ref(raw_html, ref, next_ref)
        parsed_title, content = _extract_epub_html_chapter(
            segment,
            ref.get('title') or posixpath.splitext(posixpath.basename(chapter_path))[0] or f'Chapter {index + 1}'
        )
        title = ref.get('title') or parsed_title
        if not title and not content:
            continue

        chapters.append({
            'title': title,
            'content': content,
            'line_num': index
        })

    return chapters


def _read_epub_reader_file(file_path, signature):
    with zipfile.ZipFile(file_path) as archive:
        opf_path = _find_epub_rootfile_path(archive)
        package_info = _parse_epub_opf(archive, opf_path)
        toc_refs = _parse_epub_toc_refs(archive, package_info)
        chapters = _read_epub_toc_chapters(archive, toc_refs) if toc_refs else []
        if not chapters:
            chapters = _read_epub_spine_chapters(archive, package_info['spine_paths'])

    if not chapters:
        raise ValueError('EPUB contains no readable chapters')

    return {
        'signature': signature,
        'format': 'epub',
        'encoding': 'utf-8',
        'total_chars': sum(len(chapter['content']) for chapter in chapters),
        'chapters': chapters,
    }


def get_cached_reader_file(file_path):
    """Read and parse a text novel once, then reuse it until the file changes."""
    signature = _reader_file_signature(file_path)
    cache_key = signature[0]
    cached = _READER_FILE_CACHE.get(cache_key)

    if cached and cached.get('signature') == signature:
        _READER_FILE_CACHE.move_to_end(cache_key)
        return cached

    extension = os.path.splitext(file_path)[1].lower()
    if extension == '.epub':
        parsed = _read_epub_reader_file(file_path, signature)
    else:
        encoding = detect_encoding(file_path)
        with open(file_path, 'r', encoding=encoding, errors='ignore') as handle:
            content = handle.read()

        parsed = {
            'signature': signature,
            'format': 'txt',
            'encoding': encoding,
            'total_chars': len(content),
            'chapters': parse_chapters(content),
        }

    _READER_FILE_CACHE[cache_key] = parsed
    _READER_FILE_CACHE.move_to_end(cache_key)

    while len(_READER_FILE_CACHE) > READER_FILE_CACHE_MAX_ITEMS:
        _READER_FILE_CACHE.popitem(last=False)

    return parsed
